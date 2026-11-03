"""모든 생성기의 결과를 테이블별로 모은다. 순서는 sql.TABLE_ORDER(외래키 순서)를 따른다."""

from app.mock_data import (
    budgets,
    change_logs,
    connection_tests,
    internal,
    keys,
    member_settings,
    members,
    model_catalog,
    organizations,
    payloads,
    reconciliation,
    scenarios,
    simulations,
    usage,
)
from app.mock_data.model_book import build_model_book
from app.mock_data.rows import Row
from app.mock_data.snapshot import load_snapshot
from app.mock_data.sql import TABLE_ORDER


def _with_last_used(key_rows: list[Row], requests: list[Row]) -> list[Row]:
    latest: dict[object, object] = {}
    for row in requests:
        current = latest.get(row["key_id"])
        if current is None or row["requested_at"] > current:
            latest[row["key_id"]] = row["requested_at"]
    return [{**row, "last_used_at": latest.get(row["key_id"])} for row in key_rows]


def build_dataset() -> dict[str, list[Row]]:
    snapshot = load_snapshot()
    book = build_model_book(snapshot)
    customer = usage.generate_customer_usage(book)
    sims = simulations.generate_simulations(book)
    requests = sorted(
        customer.requests
        + internal.generate_development_calls(book)
        + connection_tests.generate_connection_tests(book)
        + sims.requests,
        key=lambda row: row["requested_at"],
    )
    snapshots = reconciliation.key_usage_snapshot_rows(requests)
    tables: dict[str, list[Row]] = {
        "customers": organizations.customer_rows(),
        "projects": organizations.project_rows(),
        "users": members.user_rows(),
        "services": organizations.service_rows(),
        "api_keys": _with_last_used(keys.api_key_rows(), requests),
        "models": model_catalog.model_rows(snapshot),
        "user_model_favorites": member_settings.favorite_rows(),
        "model_prices": model_catalog.model_price_rows(snapshot),
        "tasks": customer.tasks,
        "test_scenarios": scenarios.scenario_rows(),
        "simulation_runs": sims.runs,
        "ai_requests": requests,
        "ai_request_payloads": payloads.customer_payload_rows(customer) + sims.payloads,
        "cost_adjustments": reconciliation.cost_adjustment_rows(requests),
        "simulation_results": sims.results,
        "budgets": budgets.budget_rows(),
        "subscription_costs": budgets.subscription_rows(),
        "key_usage_snapshots": snapshots,
        "usage_reconciliations": reconciliation.usage_reconciliation_rows(
            requests, snapshots
        ),
        "change_logs": change_logs.change_log_rows(),
    }
    return {table: tables[table] for table in TABLE_ORDER}
