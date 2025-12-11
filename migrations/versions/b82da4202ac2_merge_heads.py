"""merge heads

Revision ID: b82da4202ac2
Revises: 9b8dc2a6e2d8, b4dd0d1d2441, 2c1a8f0c3e5b
Create Date: 2025-12-11 08:28:48.977884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b82da4202ac2'
down_revision: Union[str, None] = ('9b8dc2a6e2d8', 'b4dd0d1d2441', '2c1a8f0c3e5b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
