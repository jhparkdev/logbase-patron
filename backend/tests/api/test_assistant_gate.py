from app.api.assistant_gate import AssistantGate


def test_한_사용자는_답을_받기_전에_다음_질문을_보낼_수_없다() -> None:
    gate = AssistantGate()

    assert gate.try_enter(user_id=1, capacity=3)
    assert not gate.try_enter(user_id=1, capacity=3)
    gate.leave(user_id=1)
    assert gate.try_enter(user_id=1, capacity=3)


def test_동시에_처리하는_요청_수는_정한_수를_넘지_않는다() -> None:
    gate = AssistantGate()

    assert gate.try_enter(user_id=1, capacity=2)
    assert gate.try_enter(user_id=2, capacity=2)
    assert not gate.try_enter(user_id=3, capacity=2)
    gate.leave(user_id=2)
    assert gate.try_enter(user_id=3, capacity=2)


def test_들어오지_않은_사용자를_내보내도_다른_사용자는_그대로다() -> None:
    gate = AssistantGate()
    assert gate.try_enter(user_id=1, capacity=1)

    gate.leave(user_id=2)

    assert not gate.try_enter(user_id=3, capacity=1)
