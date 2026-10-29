"""add no charge cost source

청구 없는 실패 호출을 확정 0원으로 기록할 수 있게 비용 근거와 조합 제약을 추가한다.
CHECK 내용 변경은 autogenerate가 감지하지 못하므로 직접 작성했다.

Revision ID: 7b2e4f6a9c10
Revises: ee924be75819
Create Date: 2026-10-29 13:56:52.439747

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b2e4f6a9c10"
down_revision: str | Sequence[str] | None = "ee924be75819"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """기존 행을 바꾸지 않고 NO_CHARGE를 허용하되 실패·확정·0원으로 제한한다."""
    op.drop_constraint("ai_requests_cost_source_check", "ai_requests", type_="check")
    op.create_check_constraint(
        "ai_requests_cost_source_check",
        "ai_requests",
        "cost_source IN ('API_RESPONSE', 'GENERATION_LOOKUP', 'PRICE_ESTIMATE', "
        "'MANUAL', 'MOCK', 'NO_CHARGE')",
    )
    op.create_check_constraint(
        "ck_ai_requests_no_charge",
        "ai_requests",
        "cost_source <> 'NO_CHARGE' OR "
        "(cost_status = 'CONFIRMED' AND cost_usd = 0 AND status = 'FAILED')",
    )


def downgrade() -> None:
    """NO_CHARGE 이력이 있으면 데이터와 제약을 그대로 두고 중단한다."""
    # 검사 이후 새 NO_CHARGE 행이 들어오는 것을 막고, 뒤의 DDL과 같은 잠금을 잡는다.
    op.execute("LOCK TABLE ai_requests IN ACCESS EXCLUSIVE MODE")
    # SQL로 검사해야 --sql로 만든 downgrade 스크립트를 실행할 때도 보호가 유지된다.
    op.execute(
        """
        DO $no_charge_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM ai_requests WHERE cost_source = 'NO_CHARGE') THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: ai_requests contains NO_CHARGE cost history.',
                    HINT = 'Keep the current revision; existing request history must not be deleted or rewritten.';
            END IF;
        END;
        $no_charge_guard$;
        """
    )
    op.drop_constraint("ck_ai_requests_no_charge", "ai_requests", type_="check")
    op.drop_constraint("ai_requests_cost_source_check", "ai_requests", type_="check")
    op.create_check_constraint(
        "ai_requests_cost_source_check",
        "ai_requests",
        "cost_source IN ('API_RESPONSE', 'GENERATION_LOOKUP', 'PRICE_ESTIMATE', "
        "'MANUAL', 'MOCK')",
    )
