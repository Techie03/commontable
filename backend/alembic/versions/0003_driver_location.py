"""Driver live location (contract section 4).

Adds the last known position to the driver profile: latitude, longitude,
heading, speed, and the server timestamp of the latest ping. All nullable;
only the latest ping is kept, no route history is stored.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "drivers", sa.Column("last_latitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "drivers", sa.Column("last_longitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "drivers", sa.Column("last_heading", sa.Float(), nullable=True)
    )
    op.add_column(
        "drivers", sa.Column("last_speed", sa.Float(), nullable=True)
    )
    op.add_column(
        "drivers",
        sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("drivers", "last_location_at")
    op.drop_column("drivers", "last_speed")
    op.drop_column("drivers", "last_heading")
    op.drop_column("drivers", "last_longitude")
    op.drop_column("drivers", "last_latitude")
