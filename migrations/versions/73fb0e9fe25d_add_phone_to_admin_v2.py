from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "73fb0e9fe25d"
# 直接接在初始化迁移之后
down_revision: Union[str, None] = "e69999560f4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add phone column to admins table"""
    op.add_column(
        "admins",
        sa.Column("phone", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    """Remove phone column from admins table"""
    op.drop_column("admins", "phone")