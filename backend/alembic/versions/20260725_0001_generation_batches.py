"""add durable independent generation batch parent/member tables

Revision ID: 20260725_0001
Revises:
Create Date: 2026-07-25
"""
from alembic import op
import sqlalchemy as sa


revision = "20260725_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_job_id", sa.String(length=64), nullable=False),
        sa.Column(
            "batch_seed_mode",
            sa.String(length=32),
            nullable=False,
            server_default="independent",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("batch_total", sa.Integer(), nullable=False),
        sa.Column(
            "batch_completed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "batch_failed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("current_batch_index", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_generation_batch_status",
        ),
        sa.CheckConstraint(
            "batch_total > 0", name="ck_generation_batch_total"
        ),
        sa.CheckConstraint(
            "batch_completed >= 0 AND batch_failed >= 0",
            name="ck_generation_batch_counts",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_job_id"),
    )
    op.create_index(
        "ix_generation_batches_public_job_id",
        "generation_batches",
        ["public_job_id"],
        unique=True,
    )
    op.create_index(
        "ix_generation_batches_status",
        "generation_batches",
        ["status"],
        unique=False,
    )
    op.create_table(
        "generation_batch_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_job_id", sa.String(length=64), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_generation_batch_member_status",
        ),
        sa.CheckConstraint(
            "batch_index >= 0",
            name="ck_generation_batch_member_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["public_job_id"],
            ["generation_batches.public_job_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id"),
        sa.UniqueConstraint(
            "public_job_id",
            "batch_index",
            name="uq_generation_batch_member_ordinal",
        ),
        sa.UniqueConstraint(
            "public_job_id",
            "seed",
            name="uq_generation_batch_member_seed",
        ),
    )
    op.create_index(
        "ix_generation_batch_members_public_job_id",
        "generation_batch_members",
        ["public_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_generation_batch_members_execution_id",
        "generation_batch_members",
        ["execution_id"],
        unique=True,
    )
    op.create_index(
        "ix_generation_batch_members_status",
        "generation_batch_members",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_batch_members_status",
        table_name="generation_batch_members",
    )
    op.drop_index(
        "ix_generation_batch_members_execution_id",
        table_name="generation_batch_members",
    )
    op.drop_index(
        "ix_generation_batch_members_public_job_id",
        table_name="generation_batch_members",
    )
    op.drop_table("generation_batch_members")
    op.drop_index(
        "ix_generation_batches_status", table_name="generation_batches"
    )
    op.drop_index(
        "ix_generation_batches_public_job_id",
        table_name="generation_batches",
    )
    op.drop_table("generation_batches")
