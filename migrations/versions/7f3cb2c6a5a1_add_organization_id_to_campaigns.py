"""add organization_id to campaigns

Revision ID: 7f3cb2c6a5a1
Revises: 0c9d8f5b6123
Create Date: 2025-12-11 10:32:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f3cb2c6a5a1"
down_revision: Union[str, None] = "0c9d8f5b6123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])
    op.create_foreign_key(
        "fk_campaigns_organization_id_organizations",
        "campaigns",
        "organizations",
        ["organization_id"],
        ["id"],
    )

    connection = op.get_bind()
    campaigns_table = sa.table(
        "campaigns",
        sa.column("id", sa.Integer),
        sa.column("organization_id", sa.Integer),
        sa.column("user_id", sa.Integer),
    )
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("organization_id", sa.Integer),
    )

    update_join = (
        campaigns_table.update()
        .values(organization_id=users_table.c.organization_id)
        .where(campaigns_table.c.user_id == users_table.c.id)
    )
    connection.execute(update_join)

    op.alter_column("campaigns", "organization_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_campaigns_organization_id_organizations", "campaigns", type_="foreignkey")
    op.drop_index("ix_campaigns_organization_id", table_name="campaigns")
    op.drop_column("campaigns", "organization_id")
