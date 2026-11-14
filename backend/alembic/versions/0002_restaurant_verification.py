"""Restaurant verification fields (contract section 7).

Adds the evidence collected at signup (owner name, business address)
and the admin verification state (status, notes, timestamp). Existing
rows get verification_status "unverified"; census and seed rows have
no evidence and are never approved.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurants", sa.Column("owner_name", sa.String(255), nullable=True)
    )
    op.add_column(
        "restaurants",
        sa.Column("business_address", sa.String(500), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column(
            "verification_status",
            sa.String(20),
            nullable=False,
            server_default="unverified",
        ),
    )
    op.add_column(
        "restaurants",
        sa.Column("verification_notes", sa.String(2000), nullable=True),
    )
    op.add_column(
        "restaurants",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("restaurants", "verified_at")
    op.drop_column("restaurants", "verification_notes")
    op.drop_column("restaurants", "verification_status")
    op.drop_column("restaurants", "business_address")
    op.drop_column("restaurants", "owner_name")
