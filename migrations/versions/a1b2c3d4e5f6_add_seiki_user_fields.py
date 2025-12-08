from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "73fb0e9fe25d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Seiki-specific fields to users table."""
    op.add_column(
        "users",
        sa.Column("phone", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("company_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("organization_type", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    """Remove Seiki-specific fields from users table."""
    op.drop_column("users", "organization_type")
    op.drop_column("users", "company_name")
    op.drop_column("users", "phone")
