"""Add pgvector semantic_cache_entries table for persistent L2 semantic caching.

Revision ID: 0002_pgvector_semantic_cache
Revises: 0001_initial_schema
Create Date: 2026-09-28 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '0002_pgvector_semantic_cache'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Enable pgvector extension on PostgreSQL
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create semantic_cache_entries table
    op.create_table(
        'semantic_cache_entries',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('scope_hash', sa.String(length=64), nullable=False),
        sa.Column('exact_request_hash', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=True),
        sa.Column('project_id', sa.String(length=64), nullable=True),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='unknown'),
        sa.Column('model', sa.String(length=128), nullable=False, server_default='unknown'),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('input_text', sa.Text(), nullable=True),
        sa.Column('namespace', sa.String(length=128), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ttl_seconds', sa.Integer(), nullable=True, server_default='86400'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 3. Create standard indexes
    op.create_index('ix_semantic_cache_scope_hash', 'semantic_cache_entries', ['scope_hash'], unique=False)
    op.create_index('ix_semantic_cache_exact_request_hash', 'semantic_cache_entries', ['exact_request_hash'], unique=True)
    op.create_index('ix_semantic_cache_tenant_id', 'semantic_cache_entries', ['tenant_id'], unique=False)
    op.create_index('ix_semantic_cache_project_id', 'semantic_cache_entries', ['project_id'], unique=False)
    op.create_index('ix_semantic_cache_namespace', 'semantic_cache_entries', ['namespace'], unique=False)
    op.create_index('ix_semantic_cache_expires_at', 'semantic_cache_entries', ['expires_at'], unique=False)
    op.create_index('ix_semantic_scope_created', 'semantic_cache_entries', ['scope_hash', 'created_at'], unique=False)
    op.create_index('ix_semantic_tenant_scope', 'semantic_cache_entries', ['tenant_id', 'scope_hash'], unique=False)

    # 4. Create HNSW Vector Index on PostgreSQL
    if is_postgres:
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_semantic_cache_embedding_hnsw
            ON semantic_cache_entries
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_semantic_cache_embedding_hnsw")

    op.drop_table('semantic_cache_entries')
