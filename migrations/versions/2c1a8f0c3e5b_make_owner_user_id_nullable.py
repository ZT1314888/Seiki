"""make owner_user_id nullable

Revision ID: 2c1a8f0c3e5b
Revises: 7b2f4c9dcbf0
Create Date: 2025-12-11 08:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2c1a8f0c3e5b"
down_revision: Union[str, None] = "7b2f4c9dcbf0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "organizations",
        "owner_user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("DELETE FROM organizations WHERE owner_user_id IS NULL")
    op.alter_column(
        "organizations",
        "owner_user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
