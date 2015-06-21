"""rearchitect stage flow

Revision ID: 22cc439cd89
Revises: 21c0f59b5214
Create Date: 2015-06-16 17:14:04.100635

"""

# revision identifiers, used by Alembic.
revision = '22cc439cd89'
down_revision = '21c0f59b5214'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('contract_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contract_id', sa.Integer(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['contract_id'], ['contract.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contract_note_id'), 'contract_note', ['id'], unique=False)
    op.create_table('contract_stage',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('contract_id', sa.Integer(), nullable=False),
    sa.Column('stage_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(), autoincrement=False, nullable=True),
    sa.Column('entered', sa.DateTime(), nullable=True),
    sa.Column('exited', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['contract_id'], ['contract.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['stage_id'], ['stage.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('contract_id', 'stage_id')
    )
    op.execute(sa.schema.CreateSequence(sa.schema.Sequence('autoincr_contract_stage_id')))
    op.create_index(op.f('ix_contract_stage_contract_id'), 'contract_stage', ['contract_id'], unique=False)
    op.create_index(op.f('ix_contract_stage_id'), 'contract_stage', ['id'], unique=True)
    op.create_index(op.f('ix_contract_stage_stage_id'), 'contract_stage', ['stage_id'], unique=False)
    op.create_index(op.f('ix_contrage_stage_combined_id'), 'contract_stage', ['contract_id', 'stage_id'])
    op.create_table('contract_stage_action_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contract_stage_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.Text(), nullable=True),
    sa.Column('taken_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['contract_stage_id'], ['contract_stage.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contract_stage_action_item_contract_stage_id'), 'contract_stage_action_item', ['contract_stage_id'], unique=False)
    op.create_index(op.f('ix_contract_stage_action_item_id'), 'contract_stage_action_item', ['id'], unique=False)
    op.add_column(u'contract', sa.Column('assigned_to', sa.Integer(), nullable=True))
    op.add_column(u'contract', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.schema.DefaultClause('false')))
    op.add_column(u'contract', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.create_foreign_key('contract_assigned_to_fkey', 'contract', 'users', ['assigned_to'], ['id'])
    op.create_foreign_key('contract_stage_id_fk', 'contract', 'stage', ['current_stage_id'], ['id'])
    op.create_foreign_key('contract_contract_parent_id_fk', 'contract', 'contract', ['parent_id'], ['id'])
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('contract_assigned_to_fkey', 'contract', type_='foreignkey')
    op.drop_column(u'contract', 'is_archived')
    op.drop_column(u'contract', 'assigned_to')
    op.drop_index(op.f('ix_contract_stage_action_item_id'), table_name='contract_stage_action_item')
    op.drop_index(op.f('ix_contract_stage_action_item_contract_stage_id'), table_name='contract_stage_action_item')
    op.drop_table('contract_stage_action_item')
    op.drop_index(op.f('ix_contract_stage_stage_id'), table_name='contract_stage')
    op.drop_index(op.f('ix_contract_stage_id'), table_name='contract_stage')
    op.drop_index(op.f('ix_contract_stage_contract_id'), table_name='contract_stage')
    op.drop_table('contract_stage')
    op.drop_index(op.f('ix_contract_note_id'), table_name='contract_note')
    op.drop_table('contract_note')
    op.execute(sa.schema.DropSequence(sa.schema.Sequence('autoincr_contract_stage_id')))
    op.drop_constraint('contract_stage_id_fk', 'contract', type_='foreignkey')
    op.drop_constraint('contract_contract_parent_id_fk', 'contract', type_='foreignkey')
    op.drop_column(u'contract', 'parent_id')
    ### end Alembic commands ###
