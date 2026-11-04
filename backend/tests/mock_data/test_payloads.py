"""app/mock_data/payloads.py 테스트: 상세 화면에서 보여 줄 고객 호출 원문."""

import pytest

from app.mock_data import payloads
from app.mock_data.model_book import build_model_book
from app.mock_data.snapshot import load_snapshot
from app.mock_data.usage import CustomerUsage, generate_customer_usage
from app.models import RequestStatus

PAYLOADS_MIN, PAYLOADS_MAX = 20, 60


@pytest.fixture(scope="module")
def usage() -> CustomerUsage:
    return generate_customer_usage(build_model_book(load_snapshot()))


def test_a_few_dozen_recent_successful_calls_get_payloads(usage: CustomerUsage) -> None:
    rows = payloads.customer_payload_rows(usage)
    calls = {r["request_id"]: r for r in usage.requests}

    assert PAYLOADS_MIN <= len(rows) <= PAYLOADS_MAX
    assert len({r["request_id"] for r in rows}) == len(rows)
    for row in rows:
        call = calls[row["request_id"]]
        assert call["status"] == RequestStatus.SUCCESS
        assert call["customer_id"] is not None
        assert row["response_text"]


def test_payload_messages_mention_a_product_of_that_customer(
    usage: CustomerUsage,
) -> None:
    calls = {r["request_id"]: r for r in usage.requests}
    for row in payloads.customer_payload_rows(usage):
        customer = calls[row["request_id"]]["customer_id"]
        names = [p.name for p in payloads.products_of(customer)]
        content = " ".join(m["content"] for m in row["request_messages"])
        assert any(name in content for name in names)


def test_payloads_never_include_secrets_or_keys(usage: CustomerUsage) -> None:
    for row in payloads.customer_payload_rows(usage):
        text = str(row["request_messages"]) + (row["response_text"] or "")
        assert "sk-or-" not in text
        assert "OPENROUTER" not in text
