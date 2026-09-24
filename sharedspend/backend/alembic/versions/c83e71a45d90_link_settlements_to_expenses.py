"""Link settlement obligations and payment transactions to their source expense.

Revision ID: c83e71a45d90
Revises: 7b6c2a4d91ef
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c83e71a45d90"
down_revision: Union[str, None] = "7b6c2a4d91ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("settlement_records") as batch:
            batch.add_column(sa.Column("original_transaction_id", sa.String(36), nullable=True))
            batch.add_column(sa.Column("original_description", sa.String(255), nullable=True))
            batch.add_column(sa.Column("original_amount", sa.Numeric(12, 2), nullable=True))
            batch.add_column(sa.Column("original_transaction_date", sa.Date(), nullable=True))
            batch.create_foreign_key(
                "fk_settlement_original_transaction",
                "transactions",
                ["original_transaction_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_unique_constraint(
                "uq_settlement_original_debtor",
                ["group_id", "original_transaction_id", "from_user_id"],
            )

        with op.batch_alter_table("transactions") as batch:
            batch.add_column(sa.Column("settlement_record_id", sa.String(36), nullable=True))
            batch.create_foreign_key(
                "fk_transaction_settlement_record",
                "settlement_records",
                ["settlement_record_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_unique_constraint(
                "uq_transaction_settlement_record", ["settlement_record_id"]
            )
        return

    op.add_column(
        "settlement_records",
        sa.Column(
            "original_transaction_id",
            sa.String(36),
            sa.ForeignKey("transactions.id", name="fk_settlement_original_transaction", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "settlement_records", sa.Column("original_description", sa.String(255), nullable=True)
    )
    op.add_column(
        "settlement_records", sa.Column("original_amount", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "settlement_records", sa.Column("original_transaction_date", sa.Date(), nullable=True)
    )
    op.create_unique_constraint(
        "uq_settlement_original_debtor",
        "settlement_records",
        ["group_id", "original_transaction_id", "from_user_id"],
    )
    op.add_column(
        "transactions",
        sa.Column(
            "settlement_record_id",
            sa.String(36),
            sa.ForeignKey("settlement_records.id", name="fk_transaction_settlement_record", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_transaction_settlement_record", "transactions", ["settlement_record_id"]
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("transactions") as batch:
            batch.drop_constraint("uq_transaction_settlement_record", type_="unique")
            batch.drop_constraint("fk_transaction_settlement_record", type_="foreignkey")
            batch.drop_column("settlement_record_id")

        with op.batch_alter_table("settlement_records") as batch:
            batch.drop_constraint("uq_settlement_original_debtor", type_="unique")
            batch.drop_constraint("fk_settlement_original_transaction", type_="foreignkey")
            batch.drop_column("original_transaction_date")
            batch.drop_column("original_amount")
            batch.drop_column("original_description")
            batch.drop_column("original_transaction_id")
        return

    op.drop_constraint("uq_transaction_settlement_record", "transactions", type_="unique")
    op.drop_constraint("fk_transaction_settlement_record", "transactions", type_="foreignkey")
    op.drop_column("transactions", "settlement_record_id")
    op.drop_constraint("uq_settlement_original_debtor", "settlement_records", type_="unique")
    op.drop_constraint("fk_settlement_original_transaction", "settlement_records", type_="foreignkey")
    op.drop_column("settlement_records", "original_transaction_date")
    op.drop_column("settlement_records", "original_amount")
    op.drop_column("settlement_records", "original_description")
    op.drop_column("settlement_records", "original_transaction_id")
