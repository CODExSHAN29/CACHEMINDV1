"""Add active_project_id to sessions table.

Revision ID: 0004_session_active_project_id
Revises: 0003_auth_workspaces_sessions
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_session_active_project_id'
down_revision: Union[str, None] = '0003_auth_workspaces_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.add_column(
            sa.Column('active_project_id', sa.String(length=64), nullable=True),
        )
        batch_op.create_foreign_key(
            'fk_sessions_active_project_id_projects',
            'projects',
            ['active_project_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_index(
            'ix_sessions_active_project_id',
            ['active_project_id'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.drop_index('ix_sessions_active_project_id')
        batch_op.drop_constraint('fk_sessions_active_project_id_projects', type_='foreignkey')
        batch_op.drop_column('active_project_id')
