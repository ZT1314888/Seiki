"""scope face_id uniqueness per organization

Revision ID: 4f0b05afbf04
Revises: b82da4202ac2
Create Date: 2025-12-11 08:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f0b05afbf04"
down_revision: Union[str, None] = "b82da4202ac2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_billboard_face_id", table_name="billboard")
    op.create_index("ix_billboard_face_id", "billboard", ["face_id"], unique=False)
    op.create_unique_constraint(
        "uq_billboard_org_face_id",
        "billboard",
        ["organization_id", "face_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_billboard_org_face_id", "billboard", type_="unique")
    op.drop_index("ix_billboard_face_id", table_name="billboard")
    op.create_index("ix_billboard_face_id", "billboard", ["face_id"], unique=True)
