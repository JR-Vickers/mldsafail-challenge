"""Protect browser token creation against replay and concurrent submissions."""
from alembic import op
import sqlalchemy as sa

revision = "e7b90d960002"
down_revision = "d6e80c850001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("api_tokens") as batch:
        batch.add_column(sa.Column("creation_request_key", sa.String(64), nullable=True))
        batch.create_unique_constraint("uq_api_token_creation_request", ["user_id", "creation_request_key"])


def downgrade():
    with op.batch_alter_table("api_tokens") as batch:
        batch.drop_constraint("uq_api_token_creation_request", type_="unique")
        batch.drop_column("creation_request_key")
