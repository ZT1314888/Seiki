"""inventory_face_user_scope

Revision ID: 9b8dc2a6e2d8
Revises: 0ea88c3f0263
Create Date: 2025-12-10 08:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9b8dc2a6e2d8"
down_revision: Union[str, None] = "0ea88c3f0263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EMAIL = "deseyh@mailto.plus"


def upgrade() -> None:
    op.add_column(
        "billboard",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_billboard_user_id"),
        "billboard",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_billboard_user_id_users",
        source_table="billboard",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )

    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email"),
        {"email": _OWNER_EMAIL},
    )
    owner_id = result.scalar()
    if owner_id is None:
        raise RuntimeError(
            f"Unable to assign billboard ownership: user '{_OWNER_EMAIL}' not found"
        )

    bind.execute(
        sa.text("UPDATE billboard SET user_id = :owner_id WHERE user_id IS NULL"),
        {"owner_id": owner_id},
    )

    op.alter_column(
        "billboard",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "billboard",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_constraint("fk_billboard_user_id_users", "billboard", type_="foreignkey")
    op.drop_index(op.f("ix_billboard_user_id"), table_name="billboard")
    op.drop_column("billboard", "user_id")
