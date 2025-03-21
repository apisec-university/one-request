"""empty message

Revision ID: a6d1fcb365a5
Revises: 2573b8f7bd48
Create Date: 2024-12-01 21:14:12.684238

"""
import sqlmodel
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6d1fcb365a5"
down_revision: Union[str, None] = "2573b8f7bd48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("booking", schema=None) as batch_op:
        batch_op.drop_column("paid")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.create_unique_constraint("unique_name", ["name"])

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_constraint("unique_name", type_="unique")

    with op.batch_alter_table("booking", schema=None) as batch_op:
        batch_op.add_column(sa.Column("paid", sa.BOOLEAN(), nullable=False))

    # ### end Alembic commands ###
