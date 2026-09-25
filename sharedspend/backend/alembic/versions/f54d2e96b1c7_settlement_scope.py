from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f54d2e96b1c7"
down_revision: Union[str, None] = "c83e71a45d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("transactions") as batch:
            batch.add_column(sa.Column("settlement_group_id", sa.String(36), nullable=True))
            batch.add_column(
                sa.Column("settlement_participant_ids", sa.JSON(), nullable=True)
            )
            batch.create_foreign_key(
                "fk_transaction_settlement_group", "groups", ["settlement_group_id"], ["id"],
                ondelete="SET NULL",
            )
    else:
        op.add_column(
            "transactions", sa.Column("settlement_group_id", sa.String(36), nullable=True)
        )
        op.create_foreign_key(
            "fk_transaction_settlement_group", "transactions", "groups",
            ["settlement_group_id"], ["id"], ondelete="SET NULL",
        )
        op.add_column(
            "transactions", sa.Column("settlement_participant_ids", sa.JSON(), nullable=True)
        )

    if op.get_context().as_sql:
        return

    # Preserve legacy flagged expenses only where their group association is
    # unambiguous. Rows shared by several groups remain unassigned for review.
    bind = op.get_bind()
    tx = sa.table(
        "transactions",
        sa.column("id", sa.String),
        sa.column("payer_id", sa.String),
        sa.column("recorded_by_id", sa.String),
        sa.column("type", sa.String),
        sa.column("add_to_settlement", sa.Boolean),
        sa.column("settlement_group_id", sa.String),
        sa.column("settlement_participant_ids", sa.JSON),
    )
    members = sa.table(
        "group_members", sa.column("group_id", sa.String), sa.column("user_id", sa.String)
    )
    rows = bind.execute(
        sa.select(tx.c.id, tx.c.payer_id, tx.c.recorded_by_id).where(
            # PostgreSQL stores transaction_type as a native enum. Cast it so
            # the migration predicate compares like types on PostgreSQL and SQLite.
            sa.cast(tx.c.type, sa.String) == "PERSONAL",
            tx.c.add_to_settlement.is_(True),
        )
    ).all()
    for row in rows:
        own_groups = set(bind.execute(
            sa.select(members.c.group_id).where(members.c.user_id == row.recorded_by_id)
        ).scalars())
        payer_groups = set(bind.execute(
            sa.select(members.c.group_id).where(members.c.user_id == row.payer_id)
        ).scalars())
        common = own_groups & payer_groups
        if len(common) != 1:
            continue
        group_id = next(iter(common))
        participants = list(bind.execute(
            sa.select(members.c.user_id).where(members.c.group_id == group_id)
        ).scalars())
        bind.execute(
            tx.update().where(tx.c.id == row.id).values(
                settlement_group_id=group_id, settlement_participant_ids=participants
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("transactions") as batch:
            batch.drop_column("settlement_participant_ids")
            batch.drop_constraint("fk_transaction_settlement_group", type_="foreignkey")
            batch.drop_column("settlement_group_id")
        return
    op.drop_column("transactions", "settlement_participant_ids")
    op.drop_constraint("fk_transaction_settlement_group", "transactions", type_="foreignkey")
    op.drop_column("transactions", "settlement_group_id")
