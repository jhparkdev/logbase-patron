"""새 모델 발견·비교 기록 model_discoveries 테이블 추가

리비전 ID: d7a3b81f4c26
이전 리비전: c5e1a9d3b702
생성 시각: 2026-11-05 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7a3b81f4c26"
down_revision: str | Sequence[str] | None = "c5e1a9d3b702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_discoveries",
        sa.Column(
            "discovery_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("openrouter_model_id", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("openrouter_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("base_model_id", sa.BigInteger(), nullable=True),
        sa.Column("compared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_cost_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("base_cost_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("new_latency_ms", sa.Integer(), nullable=True),
        sa.Column("base_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPARED', 'SKIPPED', 'FAILED')",
            name="model_discoveries_status_check",
        ),
        sa.CheckConstraint(
            "skip_reason IN ('INITIAL', 'PRICE_TOO_HIGH')",
            name="model_discoveries_skip_reason_check",
        ),
        sa.CheckConstraint(
            "openrouter_model_id <> '' "
            "AND openrouter_model_id = btrim(openrouter_model_id)",
            name="model_discoveries_openrouter_model_id_check",
        ),
        sa.CheckConstraint(
            "(status = 'SKIPPED') = (skip_reason IS NOT NULL)",
            name="ck_model_discoveries_skip_reason",
        ),
        sa.CheckConstraint(
            "status <> 'COMPARED' OR "
            "(compared_at IS NOT NULL AND base_model_id IS NOT NULL)",
            name="ck_model_discoveries_compared",
        ),
        sa.CheckConstraint(
            "new_cost_usd >= 0", name="model_discoveries_new_cost_usd_check"
        ),
        sa.CheckConstraint(
            "base_cost_usd >= 0", name="model_discoveries_base_cost_usd_check"
        ),
        sa.CheckConstraint(
            "new_latency_ms >= 0", name="model_discoveries_new_latency_ms_check"
        ),
        sa.CheckConstraint(
            "base_latency_ms >= 0", name="model_discoveries_base_latency_ms_check"
        ),
        sa.ForeignKeyConstraint(
            ["base_model_id"],
            ["models.model_id"],
            name=op.f("model_discoveries_base_model_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("discovery_id", name=op.f("model_discoveries_pkey")),
        sa.UniqueConstraint(
            "openrouter_model_id",
            name=op.f("model_discoveries_openrouter_model_id_key"),
        ),
        comment="새로 올라온 OpenRouter 모델과 기본 모델 비교 결과. 같은 모델을 두 번 비교하지 않는 기준",
    )
    op.create_index(
        "ix_model_discoveries_discovered_at", "model_discoveries", ["discovered_at"]
    )
    op.execute(
        "CREATE TRIGGER trg_model_discoveries_updated_at "
        "BEFORE UPDATE ON model_discoveries "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    """기록이 있으면 중단한다."""
    op.execute("LOCK TABLE model_discoveries IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $model_discoveries_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM model_discoveries) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: model_discoveries contains records.',
                    HINT = 'Keep this revision; discovery history must not be deleted.';
            END IF;
        END;
        $model_discoveries_guard$;
        """
    )
    op.drop_table("model_discoveries")
