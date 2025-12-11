"""add h3 index to billboard

Revision ID: 0c9d8f5b6123
Revises: 4f0b05afbf04
Create Date: 2025-12-11 09:31:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import h3


# revision identifiers, used by Alembic.
revision: str = "0c9d8f5b6123"
down_revision: Union[str, None] = "4f0b05afbf04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_H3_RESOLUTION = 9


def upgrade() -> None:
    op.add_column("billboard", sa.Column("h3_index", sa.String(length=20), nullable=True))
    op.create_index("ix_billboard_h3_index", "billboard", ["h3_index"], unique=False)

    bind = op.get_bind()
    billboard_table = sa.table(
        "billboard",
        sa.column("id", sa.Integer),
        sa.column("latitude", sa.Float),
        sa.column("longitude", sa.Float),
    )

    select_stmt = sa.select(billboard_table.c.id, billboard_table.c.latitude, billboard_table.c.longitude)
    result = bind.execute(select_stmt)
    update_stmt = sa.text("UPDATE billboard SET h3_index = :h3_index WHERE id = :id")

    for row in result:
        lat = row.latitude
        lng = row.longitude
        if lat is None or lng is None:
            continue
        h3_index = h3.latlng_to_cell(lat, lng, DEFAULT_H3_RESOLUTION)
        bind.execute(update_stmt, {"h3_index": h3_index, "id": row.id})


def downgrade() -> None:
    op.drop_index("ix_billboard_h3_index", table_name="billboard")
    op.drop_column("billboard", "h3_index")
