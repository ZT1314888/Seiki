"""create media plans table

Revision ID: f1a2b3c4d5e6
Revises: 7f3cb2c6a5a1
Create Date: 2025-12-12 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "7f3cb2c6a5a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("budget", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False, server_default="publish"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_media_plans_id"), "media_plans", ["id"])
    op.create_index(op.f("ix_media_plans_organization_id"), "media_plans", ["organization_id"])
    op.create_index(op.f("ix_media_plans_user_id"), "media_plans", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_media_plans_user_id"), table_name="media_plans")
    op.drop_index(op.f("ix_media_plans_organization_id"), table_name="media_plans")
    op.drop_index(op.f("ix_media_plans_id"), table_name="media_plans")
    op.drop_table("media_plans")
