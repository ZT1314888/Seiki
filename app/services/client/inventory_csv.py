import csv
import io
from typing import Any

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import transaction
from app.exceptions.http_exceptions import APIException
from app.models.user import User
from app.repositories.inventory import InventoryRepository
from app.schemas.client.inventory import (
    BillboardCSVRow,
    BillboardCSVUploadResult,
    FaceStatus,
    FaceType,
    FaceTypeSource,
    IndoorOption,
)
from app.utils.h3_helpers import latlng_to_h3


class BillboardCSVService:
    """Service layer for processing billboard CSV uploads."""

    _CSV_CONTENT_TYPES = {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
    }

    def __init__(self, repository: InventoryRepository, db: AsyncSession):
        self._repository = repository
        self._db = db

    async def import_csv(
        self,
        file: UploadFile,
        current_user: User,
    ) -> BillboardCSVUploadResult:
        self._ensure_csv_file(file)
        text_stream = await self._read_file(file)
        reader = csv.DictReader(text_stream, delimiter=";")
        if not reader.fieldnames:
            raise APIException(status_code=400, message="CSV header is missing")

        total_rows = 0
        parsed_rows: list[tuple[int, BillboardCSVRow]] = []
        errors: list[str] = []
        seen_face_ids: set[str] = set()

        for line_num, row in enumerate(reader, start=2):
            if self._is_empty_row(row):
                continue
            total_rows += 1
            try:
                parsed = BillboardCSVRow(**row)
            except ValidationError as exc:
                errors.append(self._format_validation_error(line_num, exc))
                continue

            if parsed.face_id in seen_face_ids:
                errors.append(f"Row {line_num}: face_id '{parsed.face_id}' duplicated in file")
                continue
            seen_face_ids.add(parsed.face_id)
            parsed_rows.append((line_num, parsed))

        if total_rows == 0:
            raise APIException(status_code=400, message="CSV contains no data rows")

        existing_ids = await self._repository.get_existing_face_ids(
            [row.face_id for _, row in parsed_rows],
            current_user.organization_id,
        )

        payloads: list[dict[str, Any]] = []
        for line_num, row in parsed_rows:
            if row.face_id in existing_ids:
                errors.append(f"Row {line_num}: face_id '{row.face_id}' already exists")
                continue
            try:
                payloads.append(self._build_face_payload(row))
            except ValueError as exc:
                errors.append(f"Row {line_num}: {exc}")

        created_count = 0
        if payloads:
            async with transaction(self._db):
                await self._repository.bulk_create_faces(
                    payloads,
                    current_user.id,
                    current_user.organization_id,
                )
            created_count = len(payloads)

        skipped_count = total_rows - created_count
        return BillboardCSVUploadResult(
            total_rows=total_rows,
            created_count=created_count,
            skipped_count=skipped_count,
            errors=errors,
        )

    async def _read_file(self, file: UploadFile) -> io.StringIO:
        raw_content = await file.read()
        if not raw_content:
            raise APIException(status_code=400, message="Uploaded CSV is empty")
        try:
            text = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise APIException(status_code=400, message="CSV must be UTF-8 encoded") from exc
        return io.StringIO(text)

    def _ensure_csv_file(self, file: UploadFile) -> None:
        content_type = (file.content_type or "").lower()
        if content_type not in self._CSV_CONTENT_TYPES:
            raise APIException(status_code=400, message="Only CSV uploads are supported")

    @staticmethod
    def _is_empty_row(row: dict[str, Any]) -> bool:
        return not any((value or "").strip() for value in row.values())

    def _build_face_payload(self, row: BillboardCSVRow) -> dict[str, Any]:
        billboard_type, type_source = self._normalize_billboard_type(row.billboard_type)
        is_indoor = self._normalize_is_indoor(row.is_indoor)
        h3_index = latlng_to_h3(row.latitude, row.longitude)
        return {
            "face_id": row.face_id,
            "billboard_type": billboard_type,
            "billboard_type_source": type_source,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "h3_index": h3_index,
            "height_from_ground": row.height_from_ground,
            "loop_timing": None,
            "address": row.address,
            "is_indoor": is_indoor,
            "azimuth_from_north": row.azimuth_from_north,
            "width": row.width,
            "height": row.height,
            "media_owner_name": row.media_owner_name,
            "network_name": row.network_name,
            "status": FaceStatus.ACTIVE.value,
            "avg_daily_gross_contacts": 0,
            "daily_frequency": 2.15,
        }

    def _normalize_billboard_type(self, value: str) -> tuple[str, str]:
        slug = value.strip().lower().replace(" ", "-")
        allowed_types = {face_type.value for face_type in FaceType}
        if slug in allowed_types:
            return slug, FaceTypeSource.PRESET.value
        return slug, FaceTypeSource.OTHER.value

    def _normalize_is_indoor(self, value: str) -> str:
        normalized = value.strip().lower()
        truthy = {"yes", "y", "true", "1"}
        falsy = {"no", "n", "false", "0"}
        if normalized in truthy:
            return IndoorOption.YES.value
        if normalized in falsy:
            return IndoorOption.NO.value
        raise ValueError("is_indoor must be Yes/No or boolean-equivalent value")

    @staticmethod
    def _format_validation_error(line_num: int, exc: ValidationError) -> str:
        details = ", ".join(error["msg"] for error in exc.errors())
        return f"Row {line_num}: {details}"
