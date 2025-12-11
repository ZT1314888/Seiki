"""add organization scoping for inventory"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm, text


# revision identifiers, used by Alembic.
revision: str = "7b2f4c9dcbf0"
down_revision: Union[str, None] = "af8a8b3c33d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("organization_type", sa.String(length=50), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_organizations_owner_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_organizations_owner_user_id",
        "organizations",
        ["owner_user_id"],
        unique=True,
    )

    op.add_column(
        "users",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"], unique=False)

    op.add_column(
        "invitations",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_invitations_organization_id", "invitations", ["organization_id"], unique=False
    )

    op.add_column(
        "billboard",
        sa.Column("organization_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_billboard_organization_id", "billboard", ["organization_id"], unique=False
    )

    bind = op.get_bind()
    session = orm.Session(bind=bind)

    try:
        owners = session.execute(
            text(
                """
                SELECT id, COALESCE(company_name, CONCAT('Org ', id)) AS name, organization_type
                FROM users
                WHERE role = 'owner' OR role IS NULL
                """
            )
        ).fetchall()

        for owner in owners:
            org_id = session.execute(
                text(
                    """
                    INSERT INTO organizations (name, organization_type, owner_user_id, created_at, updated_at)
                    VALUES (:name, :org_type, :owner_id, NOW(), NOW())
                    RETURNING id
                    """
                ),
                {
                    "name": owner.name,
                    "org_type": owner.organization_type,
                    "owner_id": owner.id,
                },
            ).scalar_one()

            session.execute(
                text("UPDATE users SET organization_id = :org_id WHERE id = :user_id"),
                {"org_id": org_id, "user_id": owner.id},
            )

        users_without_org = session.execute(
            text(
                """
                SELECT id, email, COALESCE(company_name, CONCAT('Org ', id)) AS name, organization_type
                FROM users
                WHERE organization_id IS NULL
                """
            )
        ).fetchall()

        for user in users_without_org:
            org_id = session.execute(
                text(
                    """
                    SELECT u.organization_id
                    FROM invitations i
                    JOIN users u ON u.id = i.inviter_user_id
                    WHERE lower(i.email) = lower(:email)
                    ORDER BY i.created_at DESC
                    LIMIT 1
                    """
                ),
                {"email": user.email},
            ).scalar_one_or_none()

            if org_id is None:
                org_id = session.execute(
                    text(
                        """
                        INSERT INTO organizations (name, organization_type, owner_user_id, created_at, updated_at)
                        VALUES (:name, :org_type, :owner_id, NOW(), NOW())
                        RETURNING id
                        """
                    ),
                    {
                        "name": user.name,
                        "org_type": user.organization_type,
                        "owner_id": user.id,
                    },
                ).scalar_one()

            session.execute(
                text("UPDATE users SET organization_id = :org_id WHERE id = :user_id"),
                {"org_id": org_id, "user_id": user.id},
            )

        session.execute(
            text(
                """
                UPDATE invitations AS i
                SET organization_id = u.organization_id
                FROM users AS u
                WHERE i.inviter_user_id = u.id
                """
            )
        )

        session.execute(
            text(
                """
                UPDATE billboard AS b
                SET organization_id = u.organization_id
                FROM users AS u
                WHERE b.user_id = u.id
                """
            )
        )

        session.commit()
    finally:
        session.close()

    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "invitations",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "billboard",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "fk_users_organization_id_organizations",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_invitations_organization_id_organizations",
        "invitations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_billboard_organization_id_organizations",
        "billboard",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_billboard_organization_id_organizations",
        "billboard",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_invitations_organization_id_organizations",
        "invitations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_users_organization_id_organizations",
        "users",
        type_="foreignkey",
    )

    op.drop_index("ix_billboard_organization_id", table_name="billboard")
    op.drop_column("billboard", "organization_id")

    op.drop_index("ix_invitations_organization_id", table_name="invitations")
    op.drop_column("invitations", "organization_id")

    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_index("ix_organizations_owner_user_id", table_name="organizations")
    op.drop_table("organizations")
