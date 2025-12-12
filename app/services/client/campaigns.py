from __future__ import annotations

import asyncio
import csv
import shutil
import tempfile
from dataclasses import dataclass
from itertools import cycle
from math import ceil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from random import Random
import re
from typing import Any, Callable, Dict, List, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pyecharts import options as opts
from pyecharts.charts import Bar, Pie
from pyecharts.render import make_snapshot
from snapshot_selenium import snapshot as snapshot_engine
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exceptions.http_exceptions import APIException
from app.models.campaign import Campaign
from app.models.geo import GeoDivision
from app.models.inventory import InventoryBillboard
from app.models.user import User
from app.schemas.client.campaigns import (
    CampaignCreateRequest,
    CampaignKPIData,
    CampaignResponse,
    GeoFilterResponse,
    GeoDivisionResponse,
)

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class CampaignPDFExport:
    path: str
    filename: str
    cleanup: Callable[[], None]


@dataclass
class CampaignCSVExport:
    path: str
    filename: str
    cleanup: Callable[[], None]


_PRIMARY_COLOR = colors.HexColor("#111827")
_ACCENT_PURPLE = colors.HexColor("#7C3AED")
_ACCENT_PINK = colors.HexColor("#EC4899")
_ACCENT_BLUE = colors.HexColor("#0EA5E9")
_ACCENT_GREEN = colors.HexColor("#10B981")
_CARD_BACKGROUND = colors.HexColor("#F9FAFB")
_BORDER_COLOR = colors.HexColor("#E5E7EB")
_MUTED_TEXT = colors.HexColor("#6B7280")
_CHART_COLORS = ["#7C3AED", "#6366F1", "#EC4899", "#0EA5E9", "#F59E0B", "#10B981", "#F97316"]


class GeoFilterService:
    async def list_governorates(
        self,
        db: AsyncSession,
        country_code: str = "KSA",
        current_user: User | None = None,
    ) -> GeoFilterResponse:
        query = (
            select(GeoDivision)
            .where(GeoDivision.country_code == country_code)
            .order_by(GeoDivision.division_name_en.asc())
        )
        result = await db.execute(query)
        divisions: List[GeoDivision] = result.scalars().all()

        items = [GeoDivisionResponse.model_validate(obj) for obj in divisions]

        return GeoFilterResponse(
            items=items,
            total=len(items),
        )


_KPI_FIELDS = (
    "billboard_kpi_data",
    "kpi_full_data",
    "audience_breakdown",
)


class CampaignService:
    @staticmethod
    def _generate_kpi_summary(campaign: Campaign) -> Dict[str, float | int]:
        seed = f"{campaign.id}-{campaign.start_date.isoformat()}-{campaign.end_date.isoformat()}"
        rng = Random(seed)
        coverage = round(rng.uniform(35.0, 95.0), 2)
        frequency = round(rng.uniform(1.0, 5.0), 2)
        gross_contacts = rng.randint(50_000, 500_000)
        net_contacts = int(gross_contacts * rng.uniform(0.45, 0.85))
        return {
            "coverage_percent": coverage,
            "frequency": frequency,
            "gross_contacts": gross_contacts,
            "net_contacts": net_contacts,
        }

    def _build_response(self, campaign: Campaign) -> CampaignResponse:
        summary = self._generate_kpi_summary(campaign)
        response = CampaignResponse.model_validate(campaign)
        sanitized = response.model_copy(update={field: None for field in _KPI_FIELDS})
        return sanitized.model_copy(update={"kpi_data": CampaignKPIData(**summary)})

    @staticmethod
    def _ensure_future_datetime(target: datetime, now_beijing: datetime, field_name: str) -> None:
        target_local = target.astimezone(_BEIJING_TZ)
        if target_local < now_beijing:
            raise APIException(
                status_code=400,
                message=f"{field_name} must be today or a future time in Beijing timezone",
            )

    @staticmethod
    def _compute_status_from_datetimes(
        start_date: datetime,
        end_date: datetime,
        now_beijing: datetime,
    ) -> str:
        start_local = start_date.astimezone(_BEIJING_TZ)
        end_local = end_date.astimezone(_BEIJING_TZ)
        if now_beijing < start_local:
            return "upcoming"
        if start_local <= now_beijing <= end_local:
            return "active"
        return "completed"

    def _determine_status(self, payload: CampaignCreateRequest, now_beijing: datetime) -> str:
        return self._compute_status_from_datetimes(payload.start_date, payload.end_date, now_beijing)

    async def _ensure_billboards_belong_to_org(
        self,
        db: AsyncSession,
        billboard_ids: Sequence[int],
        organization_id: int,
    ) -> None:
        if not billboard_ids:
            return
        result = await db.execute(
            select(InventoryBillboard.id, InventoryBillboard.organization_id).where(
                InventoryBillboard.id.in_(billboard_ids)
            )
        )
        rows = result.all()
        existing_ids = {row[0] for row in rows}
        missing = set(billboard_ids) - existing_ids
        if missing:
            raise APIException(
                status_code=400,
                message=f"Billboard IDs not found: {sorted(missing)}",
            )

        unauthorized = sorted([row[0] for row in rows if row[1] != organization_id])
        if unauthorized:
            raise APIException(
                status_code=403,
                message=f"Billboard IDs do not belong to your organization: {unauthorized}",
            )

    async def refresh_campaign_statuses_for_org(
        self,
        db: AsyncSession,
        organization_id: int,
    ) -> int:
        now_beijing = datetime.now(_BEIJING_TZ)
        result = await db.execute(
            select(Campaign).where(
                Campaign.organization_id == organization_id,
                Campaign.status != "draft",
            )
        )
        campaigns = result.scalars().all()
        updated = 0
        for campaign in campaigns:
            next_status = self._compute_status_from_datetimes(
                campaign.start_date,
                campaign.end_date,
                now_beijing,
            )
            if next_status != campaign.status:
                campaign.status = next_status
                updated += 1
        if updated:
            try:
                await db.flush()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        return updated

    async def refresh_all_campaign_statuses(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(Campaign.organization_id)
            .where(Campaign.status != "draft")
            .distinct()
        )
        org_ids = [row[0] for row in result.all()]
        total = 0
        for org_id in org_ids:
            total += await self.refresh_campaign_statuses_for_org(db, org_id)
        return total

    def _slugify_filename(self, name: str) -> str:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", name or "").strip("-").lower()
        return slug or "campaign-report"

    def _prepare_report_payload(self, campaign: Campaign) -> Dict[str, Any]:
        def _to_number(value: Any) -> float:
            if value is None:
                return 0.0
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, (int, float)):
                return float(value)
            return 0.0

        def _format_datetime(value: datetime) -> str:
            if value is None:
                return "-"
            return value.astimezone(_BEIJING_TZ).strftime("%Y-%m-%d %H:%M")

        def _format_hour_range(values: List[int] | None) -> str:
            if not values or len(values) != 2:
                return "-"
            start, end = values
            return f"{start:02d}:00 – {end:02d}:00"

        def _format_list(data: List[Any]) -> str:
            if not data:
                return "-"
            return ", ".join(str(item) for item in data)

        kpi_source: Dict[str, Any] = {}
        if isinstance(campaign.kpi_full_data, dict):
            kpi_source = campaign.kpi_full_data
        elif isinstance(campaign.kpi_data, dict):
            kpi_source = campaign.kpi_data

        kpis = {
            "net_contacts": _to_number(kpi_source.get("net_contacts")),
            "gross_contacts": _to_number(kpi_source.get("gross_contacts")),
            "frequency": _to_number(kpi_source.get("frequency")),
            "coverage": _to_number(
                kpi_source.get("coverage") or kpi_source.get("coverage_percent")
            ),
            "cpm": _to_number(kpi_source.get("cpm")),
            "attention_index": _to_number(kpi_source.get("attention_index")),
        }

        breakdown = campaign.audience_breakdown or {}
        gender_data = breakdown.get("gender_data") or breakdown.get("gender") or {}
        age_data = breakdown.get("age_data") or breakdown.get("age") or {}
        spc_data = breakdown.get("spc_data") or breakdown.get("spc") or {}
        geo_data = breakdown.get("geo_data") or breakdown.get("geo") or {}
        mobility_data = breakdown.get("mobility_data") or breakdown.get("mobility") or {}

        def _normalize_chart_data(data: Dict[str, Any]) -> Dict[str, float]:
            normalized: Dict[str, float] = {}
            for key, value in data.items():
                number = _to_number(value)
                if number > 0:
                    normalized[key] = number
            return normalized

        city_names: List[str] = []
        for city in campaign.cities or []:
            if isinstance(city, dict):
                city_names.append(
                    city.get("division_name_en")
                    or city.get("division_name")
                    or city.get("name")
                    or "-"
                )
            else:
                city_names.append(str(city))

        overview = {
            "duration": f"{_format_datetime(campaign.start_date)} — {_format_datetime(campaign.end_date)}",
            "budget": f"€{_to_number(campaign.budget):,.2f}",
            "countries": _format_list(campaign.countries or []),
            "cities": _format_list(city_names),
        }

        metadata = {
            "day_type": campaign.time_unit or "-",
            "week": campaign.week_1st or "-",
            "hour_range": _format_hour_range(campaign.hour_range),
            "gender": campaign.gender or "-",
            "age": _format_list(campaign.age_groups),
            "spc": campaign.spc_category or "-",
            "mobility": _format_list(campaign.mobility_modes),
            "poi": _format_list(campaign.poi_categories),
        }

        return {
            "name": campaign.name,
            "description": campaign.description or "",
            "start": _format_datetime(campaign.start_date),
            "end": _format_datetime(campaign.end_date),
            "budget": _to_number(campaign.budget),
            "countries": campaign.countries or [],
            "cities": campaign.cities or [],
            "overview": overview,
            "metadata": metadata,
            "kpis": kpis,
            "charts": {
                "gender": _normalize_chart_data(gender_data),
                "age": _normalize_chart_data(age_data),
                "spc": _normalize_chart_data(spc_data),
                "geo": _normalize_chart_data(geo_data),
                "mobility": _normalize_chart_data(mobility_data),
            },
        }

    def _snapshot_chart(self, chart, output_path: Path) -> None:
        html_path = output_path.with_suffix(".html")
        chart.render(str(html_path))
        make_snapshot(snapshot_engine, str(html_path), str(output_path))
        try:
            html_path.unlink(missing_ok=True)  # type: ignore[arg-type]
        except TypeError:
            if html_path.exists():
                html_path.unlink()

    def _render_gender_chart(self, data: Dict[str, float], output_path: Path) -> None:
        if not data:
            return
        pie = (
            Pie()
            .add(
                "",
                [list(item) for item in data.items()],
                radius=["35%", "60%"],
            )
            .set_colors(_CHART_COLORS)
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Gender Distribution", pos_left="center", title_textstyle_opts=opts.TextStyleOpts(color="#111827")),
                legend_opts=opts.LegendOpts(orient="horizontal", pos_bottom="0"),
            )
            .set_series_opts(
                label_opts=opts.LabelOpts(formatter="{b}: {d}%")
            )
        )
        self._snapshot_chart(pie, output_path)

    def _render_bar_chart(
        self,
        data: Dict[str, float],
        title: str,
        series_name: str,
        output_path: Path,
    ) -> None:
        if not data:
            return
        categories = list(data.keys())
        values = list(data.values())
        bar = (
            Bar()
            .add_xaxis(categories)
            .add_yaxis(series_name, values, category_gap="40%")
            .set_global_opts(
                title_opts=opts.TitleOpts(title=title, pos_left="center", title_textstyle_opts=opts.TextStyleOpts(color="#111827")),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=25)),
                yaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(formatter="{value}")),
            )
            .set_colors(_CHART_COLORS)
        )
        self._snapshot_chart(bar, output_path)

    def _generate_chart_images(self, charts: Dict[str, Dict[str, float]], chart_dir: Path) -> Dict[str, Path]:
        chart_dir.mkdir(parents=True, exist_ok=True)
        paths: Dict[str, Path] = {}

        gender_path = chart_dir / "gender.png"
        self._render_gender_chart(charts.get("gender", {}), gender_path)
        if gender_path.exists():
            paths["gender"] = gender_path

        age_path = chart_dir / "age.png"
        self._render_bar_chart(charts.get("age", {}), "Age Groups", "Age Distribution", age_path)
        if age_path.exists():
            paths["age"] = age_path

        spc_path = chart_dir / "spc.png"
        self._render_bar_chart(charts.get("spc", {}), "SPC Distribution", "SPC", spc_path)
        if spc_path.exists():
            paths["spc"] = spc_path

        geo_path = chart_dir / "geo.png"
        self._render_bar_chart(charts.get("geo", {}), "Geographic Provenance", "City", geo_path)
        if geo_path.exists():
            paths["geo"] = geo_path

        mobility_path = chart_dir / "mobility.png"
        self._render_bar_chart(
            charts.get("mobility", {}),
            "Mobility Modes",
            "Mobility",
            mobility_path,
        )
        if mobility_path.exists():
            paths["mobility"] = mobility_path

        return paths

    def _build_pdf_document(
        self,
        pdf_path: Path,
        payload: Dict[str, Any],
        chart_paths: Dict[str, Path],
    ) -> None:
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40,
        )
        styles = getSampleStyleSheet()
        body_style = styles["BodyText"]
        body_style.textColor = _PRIMARY_COLOR
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Heading2"],
            textColor=_PRIMARY_COLOR,
            fontSize=14,
            spaceAfter=6,
        )
        section_style = ParagraphStyle(
            "Section",
            parent=styles["Heading3"],
            textColor=_PRIMARY_COLOR,
            fontSize=12,
            spaceBefore=12,
            spaceAfter=4,
        )
        muted_style = ParagraphStyle(
            "Muted",
            parent=body_style,
            textColor=_MUTED_TEXT,
            fontSize=9,
        )
        title_style = ParagraphStyle(
            "HeroTitle",
            parent=styles["Title"],
            textColor=colors.white,
            fontSize=20,
            leading=26,
        )
        hero_sub_style = ParagraphStyle(
            "HeroSub",
            parent=body_style,
            textColor=colors.white,
            fontSize=10,
            leading=14,
        )

        story: List[Any] = []

        # Hero header
        hero = Table(
            [
                [
                    Paragraph("<b>Seiki Campaign Report</b>", title_style),
                    Paragraph("Professional export generated by Seiki Smart OOH Platform", hero_sub_style),
                ],
                [
                    Paragraph(
                        f"<b>{payload['name']}</b>",
                        ParagraphStyle("CampaignTitle", parent=title_style, fontSize=18),
                    ),
                    Paragraph(
                        f"Duration: {payload['overview']['duration']}<br/>Budget: {payload['overview']['budget']}",
                        hero_sub_style,
                    ),
                ],
            ],
            colWidths=[3.5 * inch, 2.5 * inch],
        )
        hero.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E1B4B")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                    ("BOX", (0, 0), (-1, -1), 0, colors.white),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(hero)
        story.append(Spacer(1, 0.2 * inch))

        if payload["description"]:
            story.append(Paragraph(payload["description"], body_style))
            story.append(Spacer(1, 0.15 * inch))

        # Overview tables
        overview_rows = [
            ("Timeframe", payload["overview"]["duration"]),
            ("Budget", payload["overview"]["budget"]),
            ("Countries", payload["overview"]["countries"]),
            ("Cities", payload["overview"]["cities"]),
        ]
        metadata_rows = [
            ("Day Type", payload["metadata"]["day_type"]),
            ("Week", payload["metadata"]["week"]),
            ("Hour Range", payload["metadata"]["hour_range"]),
            ("Gender", payload["metadata"]["gender"]),
            ("Age", payload["metadata"]["age"]),
            ("SPC", payload["metadata"]["spc"]),
            ("Mobility", payload["metadata"]["mobility"]),
            ("POI Categories", payload["metadata"]["poi"]),
        ]

        overview_table = self._build_key_value_table(overview_rows, cols=2)
        metadata_table = self._build_key_value_table(metadata_rows, cols=3)

        story.append(overview_table)
        story.append(Spacer(1, 0.2 * inch))
        story.append(metadata_table)
        story.append(Spacer(1, 0.25 * inch))

        story.append(Paragraph("Key Performance Indicators", subtitle_style))
        story.append(Spacer(1, 0.05 * inch))
        story.extend(self._build_kpi_cards(payload["kpis"]))
        story.append(Spacer(1, 0.2 * inch))

        story.append(Paragraph("Audience Breakdown", subtitle_style))
        story.append(Spacer(1, 0.1 * inch))
        self._append_chart_rows(story, chart_paths, ["gender", "age", "spc"])

        story.append(Paragraph("Context Breakdown", subtitle_style))
        story.append(Spacer(1, 0.1 * inch))
        self._append_chart_rows(story, chart_paths, ["geo", "mobility"])

        story.append(Spacer(1, 0.2 * inch))
        footer = Paragraph(
            f"Generated PDF of Campaign Details<br/>{payload['name']} | Generated from Seiki Platform",
            muted_style,
        )
        story.append(footer)

        doc.build(story)

    def _build_key_value_table(self, rows: List[tuple[str, str]], cols: int = 2) -> Table:
        data: List[List[Any]] = []
        chunk: List[Any] = []
        for key, value in rows:
            cell = [
                Paragraph(f"<b>{key}</b>", ParagraphStyle("Key", textColor=_PRIMARY_COLOR, fontSize=9)),
                Paragraph(value or "-", ParagraphStyle("Value", textColor=_PRIMARY_COLOR, fontSize=10)),
            ]
            chunk.append(cell)
            if len(chunk) == cols:
                data.append(chunk)
                chunk = []
        if chunk:
            while len(chunk) < cols:
                chunk.append([Spacer(0, 0), Spacer(0, 0)])
            data.append(chunk)

        table = Table(data, colWidths=[(6.2 / cols) * inch] * cols)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _CARD_BACKGROUND),
                    ("BOX", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table

    def _build_kpi_cards(self, kpis: Dict[str, float]) -> List[Any]:
        items = [
            ("Net Contacts", f"{kpis['net_contacts']:,.0f}", _ACCENT_BLUE),
            ("Gross Contacts", f"{kpis['gross_contacts']:,.0f}", _ACCENT_GREEN),
            ("Frequency", f"{kpis['frequency']:.2f}", _ACCENT_PINK),
            ("Coverage", f"{kpis['coverage']:.2f}%", _ACCENT_PURPLE),
            ("CPM", f"€{kpis['cpm']:,.2f}", _ACCENT_BLUE),
            ("Attention Index", f"{kpis['attention_index']:.2f}", _ACCENT_PINK),
        ]

        cards: List[Any] = []
        row: List[Any] = []
        for idx, (label, value, accent) in enumerate(items, 1):
            card = Table(
                [
                    [Paragraph(label, ParagraphStyle("KpiLabel", textColor=_MUTED_TEXT, fontSize=9))],
                    [Paragraph(value, ParagraphStyle("KpiValue", textColor=_PRIMARY_COLOR, fontSize=16, leading=18, spaceAfter=4))],
                ],
                colWidths=[2.6 * inch],
            )
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _CARD_BACKGROUND),
                        ("BOX", (0, 0), (-1, -1), 0.8, _BORDER_COLOR),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                        ("LINEBEFORE", (0, 0), (-1, 0), 4, accent),
                    ]
                )
            )
            row.append(card)
            if len(row) == 3:
                cards.append(Table([row], colWidths=[2.6 * inch] * 3, hAlign="LEFT"))
                cards.append(Spacer(1, 0.1 * inch))
                row = []
        if row:
            while len(row) < 3:
                row.append(Spacer(0, 0))
            cards.append(Table([row], colWidths=[2.6 * inch] * 3, hAlign="LEFT"))
        return cards

    def _append_chart_rows(
        self,
        story: List[Any],
        chart_paths: Dict[str, Path],
        keys: List[str],
    ) -> None:
        row: List[Any] = []
        for key in keys:
            chart_path = chart_paths.get(key)
            if not chart_path:
                continue
            img = Image(str(chart_path))
            img.drawHeight = 2.8 * inch
            img.drawWidth = 3.1 * inch
            card = Table([[img]], colWidths=[3.2 * inch])
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.7, _BORDER_COLOR),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            row.append(card)
            if len(row) == 2:
                story.append(Table([row], colWidths=[3.2 * inch, 3.2 * inch]))
                story.append(Spacer(1, 0.15 * inch))
                row = []
        if row:
            while len(row) < 2:
                row.append(Spacer(0, 0))
            story.append(Table([row], colWidths=[3.2 * inch, 3.2 * inch]))
            story.append(Spacer(1, 0.15 * inch))

    async def export_campaign_pdf(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignPDFExport:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")
        if campaign.status != "completed":
            raise APIException(status_code=400, message="Only completed campaigns can be exported")

        payload = self._prepare_report_payload(campaign)
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"campaign_{campaign.id}_pdf_"))
        charts_dir = tmp_dir / "charts"
        pdf_path = tmp_dir / "report.pdf"

        def cleanup() -> None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        def _generate() -> None:
            chart_paths = self._generate_chart_images(payload["charts"], charts_dir)
            self._build_pdf_document(pdf_path, payload, chart_paths)

        await asyncio.to_thread(_generate)

        filename = f"{self._slugify_filename(payload['name'])}-{campaign.id}.pdf"
        return CampaignPDFExport(path=str(pdf_path), filename=filename, cleanup=cleanup)

    async def export_campaign_csv(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignCSVExport:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")
        if campaign.status != "completed":
            raise APIException(status_code=400, message="Only completed campaigns can be exported")

        payload = self._prepare_report_payload(campaign)
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"campaign_{campaign.id}_csv_"))
        csv_path = tmp_dir / "campaign.csv"

        def cleanup() -> None:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        date_range = payload["overview"]["duration"].replace("—", "-").strip()
        kpis = payload["kpis"]
        row = [
            campaign.name,
            str(campaign.id),
            date_range,
            f"{kpis['net_contacts']:,.0f}",
            f"{kpis['gross_contacts']:,.0f}",
            f"{kpis['net_contacts']:,.0f}",
            f"{kpis['gross_contacts']:,.0f}",
            f"{kpis['coverage']:.2f}",
            f"{kpis['gross_contacts']:,.0f}",
            f"{kpis['frequency']:.2f}",
            f"{float(kpis['coverage']) * float(kpis['frequency']) / 100:.2f}",
        ]

        with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            writer.writerow(
                [
                    "campaign_name",
                    "campaign_id",
                    "date_range",
                    "contacts",
                    "cumulative_contacts",
                    "contacts_on_target_population",
                    "cumulative_contacts_on_target_population",
                    "cumulative_coverage",
                    "cumulative_audience",
                    "avg_frequency",
                    "cumulative_GRP",
                ]
            )
            writer.writerow(row)

        filename = f"{self._slugify_filename(payload['name'])}-{campaign.id}.csv"
        return CampaignCSVExport(path=str(csv_path), filename=filename, cleanup=cleanup)

    async def _normalize_cities(
        self,
        db: AsyncSession,
        cities: List["CitySelection"],
    ) -> List[Dict[str, str]]:
        if not cities:
            return []
        requested_ids = [city.division_id for city in cities]
        result = await db.execute(
            select(GeoDivision).where(GeoDivision.division_id.in_(requested_ids))
        )
        divisions = result.scalars().all()
        division_map = {division.division_id: division for division in divisions}
        missing = [division_id for division_id in requested_ids if division_id not in division_map]
        if missing:
            raise APIException(
                status_code=400,
                message=f"Invalid city selections (not found in geo table): {missing}",
            )
        normalized = [
            {
                "division_id": city_id,
                "division_name_en": division_map[city_id].division_name_en,
            }
            for city_id in requested_ids
        ]
        return normalized

    async def _ensure_unique_campaign(
        self,
        db: AsyncSession,
        payload: CampaignCreateRequest,
        current_user: User,
        exclude_campaign_id: int | None = None,
    ) -> None:
        existing_stmt = select(Campaign.id).where(
            Campaign.user_id == current_user.id,
            Campaign.name == payload.name,
            Campaign.start_date == payload.start_date,
            Campaign.end_date == payload.end_date,
            Campaign.status != "draft",
        )
        if exclude_campaign_id is not None:
            existing_stmt = existing_stmt.where(Campaign.id != exclude_campaign_id)

        result = await db.execute(existing_stmt)
        exists = result.scalar_one_or_none()
        if exists:
            raise APIException(
                status_code=400,
                message="Campaign with the same name and schedule already exists",
            )

    async def create_campaign(
        self,
        db: AsyncSession,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> CampaignResponse:
        if current_user.role == "operator":
            raise APIException(status_code=403, message="Operators cannot create campaigns")

        is_draft = payload.save_as_draft

        if not payload.inventory_ids:
            raise APIException(status_code=400, message="At least one inventory must be selected")

        if not is_draft and not payload.billboard_ids:
            raise APIException(status_code=400, message="At least one billboard must be selected")

        if payload.billboard_ids:
            await self._ensure_billboards_belong_to_org(
                db,
                payload.billboard_ids,
                current_user.organization_id,
            )

        if not is_draft:
            await self._ensure_unique_campaign(db, payload, current_user)
        normalized_cities = await self._normalize_cities(db, payload.cities)

        now_beijing = datetime.now(_BEIJING_TZ)
        self._ensure_future_datetime(payload.start_date, now_beijing, "start_date")
        self._ensure_future_datetime(payload.end_date, now_beijing, "end_date")

        if payload.end_date < payload.start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        computed_status = "draft" if is_draft else self._determine_status(payload, now_beijing)

        campaign = Campaign(
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            name=payload.name,
            description=payload.description,
            budget=Decimal(str(payload.budget)),
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=computed_status,
            time_unit=payload.time_unit,
            week_1st=payload.week_1st,
            selected_dates=None,
            kpi_start_date=None,
            kpi_end_date=None,
            hour_range=payload.hour_range,
            countries=payload.countries,
            cities=normalized_cities,
            gender=payload.gender,
            age_groups=payload.age_groups,
            spc_category=payload.spc_category,
            mobility_modes=payload.mobility_modes,
            poi_categories=payload.poi_categories,
            billboard_ids=payload.billboard_ids,
            inventory_ids=payload.inventory_ids,
            billboards_tree=None,
            billboard_kpi_data=None,
            kpi_data=None,
            kpi_full_data=None,
            audience_breakdown=None,
            customize_kpis=None,
            operator_first_name=current_user.first_name,
            operator_last_name=current_user.last_name,
        )

        db.add(campaign)
        try:
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(campaign)

        return self._build_response(campaign)

    async def delete_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> None:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        if campaign.status != "draft":
            raise APIException(status_code=400, message="Only draft campaigns can be deleted")

        try:
            await db.delete(campaign)
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def edit_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        payload: CampaignCreateRequest,
        current_user: User,
    ) -> CampaignResponse:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == current_user.organization_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        if campaign.status != "draft":
            raise APIException(status_code=400, message="Only draft campaigns can be edited")

        is_draft = payload.save_as_draft

        if not payload.inventory_ids:
            raise APIException(status_code=400, message="At least one inventory must be selected")
        if not is_draft and not payload.billboard_ids:
            raise APIException(status_code=400, message="At least one billboard must be selected")

        if payload.billboard_ids:
            await self._ensure_billboards_belong_to_org(
                db,
                payload.billboard_ids,
                current_user.organization_id,
            )

        normalized_cities = await self._normalize_cities(db, payload.cities)
        now_beijing = datetime.now(_BEIJING_TZ)

        if not is_draft:
            await self._ensure_unique_campaign(db, payload, current_user, exclude_campaign_id=campaign.id)
            self._ensure_future_datetime(payload.start_date, now_beijing, "start_date")
            self._ensure_future_datetime(payload.end_date, now_beijing, "end_date")
            if payload.end_date < payload.start_date:
                raise APIException(status_code=400, message="end_date cannot be earlier than start_date")
            next_status = self._determine_status(payload, now_beijing)
        else:
            next_status = "draft"

        campaign.name = payload.name
        campaign.description = payload.description
        campaign.budget = Decimal(str(payload.budget))
        campaign.start_date = payload.start_date
        campaign.end_date = payload.end_date
        campaign.status = next_status
        campaign.time_unit = payload.time_unit
        campaign.week_1st = payload.week_1st
        campaign.selected_dates = None
        campaign.kpi_start_date = None
        campaign.kpi_end_date = None
        campaign.hour_range = payload.hour_range
        campaign.countries = payload.countries
        campaign.cities = normalized_cities
        campaign.gender = payload.gender
        campaign.age_groups = payload.age_groups
        campaign.spc_category = payload.spc_category
        campaign.mobility_modes = payload.mobility_modes
        campaign.poi_categories = payload.poi_categories
        campaign.billboard_ids = payload.billboard_ids
        campaign.inventory_ids = payload.inventory_ids
        campaign.billboards_tree = None
        campaign.billboard_kpi_data = None
        campaign.kpi_data = None
        campaign.kpi_full_data = None
        campaign.audience_breakdown = None
        campaign.customize_kpis = None
        campaign.operator_first_name = current_user.first_name
        campaign.operator_last_name = current_user.last_name

        try:
            await db.flush()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(campaign)

        return self._build_response(campaign)

    async def list_campaigns(
        self,
        db: AsyncSession,
        current_user: User,
        page: int = 1,
        per_page: int = 10,
        search: str | None = None,
        status_filter: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Dict[str, Any]:
        if page < 1 or per_page < 1:
            raise APIException(status_code=400, message="Invalid page or per_page parameter")

        await self.refresh_campaign_statuses_for_org(db, current_user.organization_id)

        query = select(Campaign).where(Campaign.organization_id == current_user.organization_id)
        if search:
            like_value = f"%{search}%"
            query = query.where(
                or_(
                    Campaign.name.ilike(like_value),
                    Campaign.description.ilike(like_value),
                )
            )
        if status_filter:
            allowed_status = {"upcoming", "active", "completed"}
            normalized_status = status_filter.lower()
            if normalized_status not in allowed_status:
                raise APIException(status_code=400, message="Invalid status filter")
            query = query.where(Campaign.status == normalized_status)
        if start_date:
            if start_date.tzinfo is None:
                raise APIException(status_code=400, message="start_date must include timezone info")
            query = query.where(Campaign.start_date >= start_date)
        if end_date:
            if end_date.tzinfo is None:
                raise APIException(status_code=400, message="end_date must include timezone info")
            query = query.where(Campaign.end_date <= end_date)
        if start_date and end_date and end_date < start_date:
            raise APIException(status_code=400, message="end_date cannot be earlier than start_date")

        total_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(total_query)
        last_page = ceil(total / per_page) if per_page > 0 else 0

        if last_page and page > last_page:
            raise APIException(status_code=404, message="Page not found")

        result = await db.execute(
            query.order_by(Campaign.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        )
        campaigns = result.scalars().all()
        items = [self._build_response(c) for c in campaigns]

        return {
            "items": items,
            "total": total,
            "per_page": per_page,
            "current_page": page,
            "last_page": last_page,
            "has_more": page < last_page,
        }

    async def get_campaign_detail(
        self,
        db: AsyncSession,
        campaign_id: int,
        current_user: User,
    ) -> CampaignResponse:
        await self.refresh_campaign_statuses_for_org(db, current_user.organization_id)

        query = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == current_user.organization_id,
        )
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise APIException(status_code=404, message="Campaign not found")

        return self._build_response(campaign)


geo_filter_service = GeoFilterService()
campaign_service = CampaignService()
