"""add conract_href first class contract property

Revision ID: 3473ff14af7e
Revises: 10aaa4625220
Create Date: 2015-05-21 21:44:13.410505

"""

# revision identifiers, used by Alembic.
revision = '3473ff14af7e'
down_revision = '10aaa4625220'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('contract', sa.Column('contract_href', sa.Text(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('contract', 'contract_href')
    ### end Alembic commands ###
