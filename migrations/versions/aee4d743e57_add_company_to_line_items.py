"""add company to line items

Revision ID: aee4d743e57
Revises: 29562eda8fbc
Create Date: 2015-06-02 21:58:20.455144

"""

# revision identifiers, used by Alembic.
revision = 'aee4d743e57'
down_revision = '29562eda8fbc'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('line_item', sa.Column('company_id', sa.Integer(), nullable=True))
    op.add_column('line_item', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.create_foreign_key(None, 'line_item', 'company', ['company_id'], ['id'])
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'line_item', type_='foreignkey')
    op.drop_column('line_item', 'company_name')
    op.drop_column('line_item', 'company_id')
    ### end Alembic commands ###
