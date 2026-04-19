"""init_tables

Revision ID: ded3c329e543
Revises:
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "ded3c329e543"
down_revision = None
branch_labels = None
depends_on = None

VECTOR_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2


def upgrade() -> None:
    # pgvector расширение
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("tier", sa.String(16), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "user_servers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("ssh_user", sa.String(64), nullable=False),
        sa.Column("ssh_pass_enc", sa.Text, nullable=False),
        sa.Column("bot_token_enc", sa.Text, nullable=False),
        sa.Column("claude_auth_enc", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("user_servers.id"), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("log", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "configurations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("business_type", sa.String(64), nullable=False),
        sa.Column("tasks", sa.Text, nullable=False),
        sa.Column("agents", sa.Text, nullable=False),
        sa.Column("skills", sa.Text, nullable=False),
        sa.Column("success_score", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_configurations_business_type", "configurations", ["business_type"])

    # Векторная колонка через raw SQL (pgvector тип)
    op.execute(f"ALTER TABLE configurations ADD COLUMN embedding vector({VECTOR_DIM})")
    op.execute(
        "CREATE INDEX ix_configurations_embedding "
        "ON configurations USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)"
    )


def downgrade() -> None:
    op.drop_table("configurations")
    op.drop_table("deployments")
    op.drop_table("user_servers")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
