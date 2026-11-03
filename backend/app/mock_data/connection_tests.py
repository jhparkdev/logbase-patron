"""모델 연결 테스트(SYSTEM_TEST). 등록한 구성원이 PoC Key로 실행한다.

모델마다 일정(model_plans)의 시각에 성공으로 끝나고, 일부 모델은 그 전에 한 번 실패한다.
"""

from datetime import timedelta

from app.mock_data import routes
from app.mock_data.calls import CallSpec, Shape, build_call
from app.mock_data.ids import rng_for
from app.mock_data.keys import poc_key
from app.mock_data.model_book import ModelBook
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.organizations import service_id
from app.mock_data.outcomes import FAILURES, SUCCESS
from app.mock_data.period import PERIOD_END
from app.mock_data.rows import Row
from app.models import CallPurpose, ErrorType, UsageOrigin
from app.services.model_test import TEST_SERVICE_CODE

CONNECTION_TEST_INPUT = "connection-test-prompt-v1"
# 첫 연결 테스트가 실패해 다시 시도한 모델: (실패 유형, 성공한 테스트보다 앞선 시간)
FIRST_TEST_FAILURES = {
    routes.ARGON: (ErrorType.PROVIDER_ERROR, timedelta(minutes=40)),
    routes.model_id("moonshotai/kimi-k3.1-pro"): (
        ErrorType.TIMEOUT_ERROR,
        timedelta(minutes=5),
    ),
}


def generate_connection_tests(book: ModelBook) -> list[Row]:
    rng = rng_for("connection-tests")
    key = poc_key()
    rows: list[Row] = []
    for plan in MODEL_PLANS:
        spec = CallSpec(
            usage_origin=UsageOrigin.SYSTEM_TEST,
            key_id=key.key_id,
            service_id=service_id(TEST_SERVICE_CODE),
            model_id=plan.model_id,
            shape=Shape.CONNECTION_TEST,
            call_purpose=CallPurpose.TEST,
            project_id=key.project_id,
            executed_by=plan.created_by,
            routing_policy={"allow_fallbacks": False},
            input_reference=CONNECTION_TEST_INPUT,
        )
        if plan.model_id in FIRST_TEST_FAILURES:
            error_type, lead = FIRST_TEST_FAILURES[plan.model_id]
            rows.append(
                build_call(
                    spec,
                    plan.tested_at - lead,
                    FAILURES[error_type],
                    book,
                    rng,
                    PERIOD_END,
                )
            )
        rows.append(build_call(spec, plan.tested_at, SUCCESS, book, rng, PERIOD_END))
    rows.sort(key=lambda row: row["requested_at"])
    return rows
