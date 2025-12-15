"""add campaign_id to media_plans

Revision ID: 5a8cda0f9b3b
Revises: f1a2b3c4d5e6
Create Date: 2025-12-15 01:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5a8cda0f9b3b"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media_plans",
        sa.Column("campaign_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_media_plans_campaign_id"), "media_plans", ["campaign_id"]
    )
    op.create_foreign_key(
        "media_plans_campaign_id_fkey",
        "media_plans",
        "campaigns",
        ["campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "media_plans_campaign_id_fkey",
        "media_plans",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_media_plans_campaign_id"), table_name="media_plans")
    op.drop_column("media_plans", "campaign_id")
