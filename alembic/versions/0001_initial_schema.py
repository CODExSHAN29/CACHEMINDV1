"""Initial CacheMind database schema: tenants, projects, api_keys, and request_logs.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-28 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tenants Table
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # 2. Projects Table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_tenant_id', 'projects', ['tenant_id'], unique=False)

    # 3. API Keys Table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=32), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, server_default='Default Key'),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='admin'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_api_keys_project_id', 'api_keys', ['project_id'], unique=False)
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)

    # 4. Request Logs Table
    op.create_table(
        'request_logs',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('requested_model', sa.String(length=128), nullable=False),
        sa.Column('actual_model', sa.String(length=128), nullable=False),
        sa.Column('cache_status', sa.String(length=32), nullable=False),
        sa.Column('exact_request_hash', sa.String(length=64), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=True),
        sa.Column('guardrail_status', sa.Boolean(), nullable=True),
        sa.Column('guardrail_failed_check', sa.String(length=255), nullable=True),
        sa.Column('gateway_latency_ms', sa.Float(), nullable=False),
        sa.Column('upstream_latency_ms', sa.Float(), nullable=True),
        sa.Column('exact_cache_lookup_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('upstream_called', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_request_logs_request_id', 'request_logs', ['request_id'], unique=True)
    op.create_index('ix_request_logs_project_created', 'request_logs', ['project_id', 'created_at'], unique=False)
    op.create_index('ix_request_logs_tenant_created', 'request_logs', ['tenant_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('request_logs')
    op.drop_table('api_keys')
    op.drop_table('projects')
    op.drop_table('tenants')
