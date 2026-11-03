"""app/mock_data/routes.py 테스트: 시기에 따라 호출이 새 모델로 옮겨 가는 경로."""

from datetime import timedelta
from random import Random

import pytest

from app.mock_data import routes
from app.mock_data.model_plans import MODEL_PLANS
from app.mock_data.period import PERIOD_END, PERIOD_START

PLANS = {plan.model_id: plan for plan in MODEL_PLANS}
STEP = timedelta(hours=7)


def _times() -> list:
    times, at = [], PERIOD_START
    while at < PERIOD_END:
        times.append(at)
        at += STEP
    return times


@pytest.mark.parametrize("route", routes.ALL_ROUTES, ids=lambda r: r.name)
def test_route_only_picks_models_active_at_that_time(route: routes.Route) -> None:
    rng = Random(7)

    for at in _times():
        if at < route.stages[0].starts_at:
            continue
        plan = PLANS[routes.pick_model(route, at, rng)]
        assert plan.activated_at is not None and plan.activated_at <= at
        assert plan.deactivated_at is None or at < plan.deactivated_at


def test_migration_moves_traffic_gradually_to_the_new_model() -> None:
    route = routes.PDP_WRITER
    stage = route.stages[1]
    rng = Random(7)

    before = {routes.pick_model(route, stage.starts_at - STEP, rng) for _ in range(50)}
    during = {
        routes.pick_model(route, stage.starts_at + routes.MIGRATION / 2, rng)
        for _ in range(200)
    }
    after = {
        routes.pick_model(route, stage.starts_at + routes.MIGRATION, rng)
        for _ in range(50)
    }

    assert before == {route.stages[0].model_id}
    assert during == {route.stages[0].model_id, stage.model_id}
    assert after == {stage.model_id}
