"""AI 도우미 호출 출처 ASSISTANT 추가

AI 도우미의 모델 호출 비용을 내부 개발과 나눠 기록할 수 있게 호출 출처 값을 추가한다.
ai_requests와 tasks의 usage_origin은 같은 값 목록을 쓰므로 두 CHECK를 함께 바꾼다.
owner_type 계산식은 그대로 두며, ASSISTANT는 시뮬레이션·연결 테스트처럼 POC로 계산된다.
CHECK 내용 변경은 autogenerate가 감지하지 못하므로 직접 작성했다.

리비전 ID: c5e1a9d3b702
이전 리비전: 404e6f91129f
생성 시각: 2026-11-05 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# Alembic이 사용하는 리비전 식별 정보.
revision: str = "c5e1a9d3b702"
down_revision: str | Sequence[str] | None = "404e6f91129f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("ai_requests", "tasks")
OLD_ORIGINS = "'CUSTOMER_SERVICE', 'INTERNAL_DEVELOPMENT', 'SIMULATION', 'SYSTEM_TEST'"
NEW_ORIGINS = f"{OLD_ORIGINS}, 'ASSISTANT'"


def _replace_origin_check(table: str, origins: str) -> None:
    name = f"{table}_usage_origin_check"
    op.drop_constraint(name, table, type_="check")
    op.create_check_constraint(name, table, f"usage_origin IN ({origins})")


def upgrade() -> None:
    """기존 행을 바꾸지 않고 ASSISTANT를 허용한다."""
    for table in TABLES:
        _replace_origin_check(table, NEW_ORIGINS)


def downgrade() -> None:
    """ASSISTANT 이력이 있으면 데이터와 제약을 그대로 두고 중단한다."""
    # 검사 이후 새 ASSISTANT 행이 들어오는 것을 막고, 뒤의 DDL과 같은 잠금을 잡는다.
    op.execute("LOCK TABLE ai_requests, tasks IN ACCESS EXCLUSIVE MODE")
    # SQL로 검사해야 --sql로 만든 downgrade 스크립트를 실행할 때도 보호가 유지된다.
    op.execute(
        """
        DO $assistant_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM ai_requests WHERE usage_origin = 'ASSISTANT')
               OR EXISTS (SELECT 1 FROM tasks WHERE usage_origin = 'ASSISTANT') THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: ai_requests or tasks contains ASSISTANT usage history.',
                    HINT = 'Keep the current revision; existing request history must not be deleted or rewritten.';
            END IF;
        END;
        $assistant_guard$;
        """
    )
    for table in TABLES:
        _replace_origin_check(table, OLD_ORIGINS)
