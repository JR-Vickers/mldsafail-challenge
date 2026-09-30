"""Bind hosted MLWE submissions and results to an immutable epoch.

Historical integer scores remain unchanged; MLWE stores its native ratio.
"""
from alembic import op
import sqlalchemy as sa

revision = "d6e80c850001"
down_revision = "c95d5045d633"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("submissions") as batch:
        for name, length in (("epoch_id", 64), ("evaluator_fingerprint", 128),
                             ("hidden_suite_version", 64), ("worker_class", 64)):
            batch.add_column(sa.Column(name, sa.String(length), nullable=True))
        batch.add_column(sa.Column("solver_path", sa.String(200), nullable=True))
    with op.batch_alter_table("experiment_results") as batch:
        batch.alter_column("score", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("mlwe_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("epoch_id", sa.String(64), nullable=True))


def downgrade():
    # Do not silently destroy MLWE results to restore the historical schema.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM experiment_results WHERE score IS NULL")).scalar():
        raise RuntimeError("MLWE results must be retained; restore the previous release database backup")
    with op.batch_alter_table("experiment_results") as batch:
        batch.drop_column("epoch_id")
        batch.drop_column("mlwe_score")
        batch.alter_column("score", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("submissions") as batch:
        for name in ("epoch_id", "evaluator_fingerprint", "hidden_suite_version", "worker_class", "solver_path"):
            batch.drop_column(name)
