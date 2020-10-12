"""Init

Revision ID: 53f17192bf18
Revises: 
Create Date: 2020-10-13 00:04:24.176911

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql.ddl import CreateSequence, DropSequence


# revision identifiers, used by Alembic.
revision = '53f17192bf18'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("create extension if not exists \"uuid-ossp\";"))

    op.create_table(
        "devices",
        sa.Column("id", UUID(), nullable=False, server_default=sa.func.uuid_generate_v4()),
        sa.Column("user_id", sa.BIGINT(), nullable=False),
        sa.Column("name", sa.TEXT(), nullable=False),
        sa.Column("pkey", sa.TEXT(), nullable=False),
        sa.Column("cert_req", sa.TEXT(), nullable=False),
        sa.Column("cert", sa.TEXT(), nullable=False),
        sa.Column("cert_sn", sa.BIGINT(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("current_timestamp")),
        sa.Column("removed", sa.BOOLEAN(), nullable=False, server_default=sa.literal(False)),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cert_sn")
    )

    op.create_index(
        "uniq_devices_user_id_name",
        "devices",
        ("user_id", "name"),
        unique=True,
        postgresql_where=sa.text("not removed")
    )

    op.execute(CreateSequence(sa.Sequence("certs_sn", start=2971215073, increment=233, minvalue=1, cycle=True)))


def downgrade():
    op.execute(DropSequence(sa.Sequence("certs_sn")))
    op.drop_table("devices")
