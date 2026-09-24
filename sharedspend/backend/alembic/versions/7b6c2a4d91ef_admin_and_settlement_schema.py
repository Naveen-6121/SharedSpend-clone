"""Add global admin and complete the settlement schema.

Revision ID: 7b6c2a4d91ef
Revises: 229e3412032a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b6c2a4d91ef"
down_revision: Union[str, None] = "229e3412032a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_context().as_sql:
        # Offline SQL targets a fresh database because schema introspection is
        # unavailable while generating a script.
        op.add_column(
            "users",
            sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
        op.add_column(
            "transactions",
            sa.Column(
                "add_to_settlement", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
        )
        op.create_table(
            "settlement_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("from_user_id", sa.String(length=36), nullable=False),
            sa.Column("to_user_id", sa.String(length=36), nullable=False),
            sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column(
                "status",
                sa.Enum("PENDING", "SETTLED", name="settlement_status"),
                server_default="PENDING",
                nullable=False,
            ),
            sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
            sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" not in user_columns:
            op.add_column(
                "users",
                sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
            )

    if "transactions" in tables:
        transaction_columns = {
            column["name"] for column in inspector.get_columns("transactions")
        }
        if "add_to_settlement" not in transaction_columns:
            op.add_column(
                "transactions",
                sa.Column(
                    "add_to_settlement", sa.Boolean(), server_default=sa.false(), nullable=False
                ),
            )

    if "settlement_records" not in tables:
        status_type = sa.Enum("PENDING", "SETTLED", name="settlement_status")
        op.create_table(
            "settlement_records",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("from_user_id", sa.String(length=36), nullable=False),
            sa.Column("to_user_id", sa.String(length=36), nullable=False),
            sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
            sa.Column("status", status_type, server_default="PENDING", nullable=False),
            sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
            sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "settlement_records" in tables:
        count = bind.execute(sa.text("SELECT count(*) FROM settlement_records")).scalar_one()
        if count:
            raise RuntimeError("Refusing to remove settlement_records while it contains data")
        op.drop_table("settlement_records")

    if "transactions" in tables:
        columns = {column["name"] for column in inspector.get_columns("transactions")}
        if "add_to_settlement" in columns:
            with op.batch_alter_table("transactions") as batch:
                batch.drop_column("add_to_settlement")

    if "users" in tables:
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_admin" in columns:
            with op.batch_alter_table("users") as batch:
                batch.drop_column("is_admin")
