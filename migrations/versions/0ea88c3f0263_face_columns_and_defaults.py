"""face_columns_and_defaults

Revision ID: 0ea88c3f0263
Revises: af8a8b3c33d5
Create Date: 2025-12-10 06:19:33.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0ea88c3f0263"
down_revision: Union[str, None] = "af8a8b3c33d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("billboard", "billboard_code", new_column_name="face_id")

    op.drop_index("ix_billboard_billboard_code", table_name="billboard")
    op.create_index(
        op.f("ix_billboard_face_id"),
        "billboard",
        ["face_id"],
        unique=True,
    )

    op.add_column(
        "billboard",
        sa.Column(
            "billboard_type_source",
            sa.String(length=50),
            nullable=False,
            server_default="preset",
        ),
    )
    op.add_column(
        "billboard",
        sa.Column(
            "avg_daily_gross_contacts",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "billboard",
        sa.Column(
            "daily_frequency",
            sa.Float(),
            nullable=False,
            server_default="2.15",
        ),
    )


def downgrade() -> None:
    op.drop_column("billboard", "daily_frequency")
    op.drop_column("billboard", "avg_daily_gross_contacts")
    op.drop_column("billboard", "billboard_type_source")

    op.drop_index(op.f("ix_billboard_face_id"), table_name="billboard")
    op.create_index(
        "ix_billboard_billboard_code",
        "billboard",
        ["billboard_code"],
        unique=True,
    )

    op.alter_column("billboard", "face_id", new_column_name="billboard_code")
