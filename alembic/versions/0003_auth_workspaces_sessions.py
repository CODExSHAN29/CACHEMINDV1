"""Add users, tenant_memberships, and sessions for real authentication and multi-tenant workspaces.

Revision ID: 0003_auth_workspaces_sessions
Revises: 0002_pgvector_semantic_cache
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_auth_workspaces_sessions'
down_revision: Union[str, None] = '0002_pgvector_semantic_cache'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Tenant Memberships Table
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant_membership'),
    )
    op.create_index('ix_tenant_memberships_user_id', 'tenant_memberships', ['user_id'], unique=False)
    op.create_index('ix_tenant_memberships_tenant_id', 'tenant_memberships', ['tenant_id'], unique=False)

    # 3. Sessions Table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('active_tenant_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['active_tenant_id'], ['tenants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sessions_session_token_hash', 'sessions', ['session_token_hash'], unique=True)
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'], unique=False)
    op.create_index('ix_sessions_active_tenant_id', 'sessions', ['active_tenant_id'], unique=False)
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'], unique=False)


def downgrade() -> None:
    op.drop_table('sessions')
    op.drop_table('tenant_memberships')
    op.drop_table('users')
