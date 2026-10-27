"""initial schema

빈 DB에 설계서 v0.6의 전체 구조(테이블 22개, 뷰 2개)를 처음 만드는 마이그레이션.

- 테이블·제약·인덱스는 autogenerate가 app/models.py에서 만들었다.
- autogenerate가 다루지 않는 것은 직접 추가했다: btree_gist 확장, set_updated_at() 함수,
  updated_at 트리거 12개, 뷰 2개, models ↔ ai_requests 순환 외래키.
- 기준: 설계 SQL patron_schema_v0.6.sql(레포에는 없는 설계 문서).
- 이미 공유(merge)된 뒤에는 이 파일을 고치지 않고 새 마이그레이션을 추가한다.

Revision ID: ee924be75819
Revises:
Create Date: 2026-10-27 16:58:45.935329

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ee924be75819"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# updated_at이 있는 12개 테이블. 행을 수정하면 트리거가 updated_at을 now()로 바꾼다.
UPDATED_AT_TABLES = [
    "customers",
    "projects",
    "users",
    "services",
    "api_keys",
    "models",
    "ai_requests",
    "test_scenarios",
    "simulation_runs",
    "budgets",
    "subscription_costs",
    "usage_reconciliations",
]

SET_UPDATED_AT_FUNCTION = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$
"""

# 모든 사용량·비용 집계는 이 뷰를 거친다 (요약 = 상세, T-12)
V_REQUEST_FACTS = """
CREATE VIEW v_request_facts AS
SELECT
  r.request_id,
  r.usage_origin,
  r.owner_type,
  r.key_id,
  r.customer_id,
  c.customer_code,
  c.name                                                        AS customer_name,
  r.project_id,
  p.project_code,
  p.name                                                        AS project_name,
  r.executed_by,
  r.service_id,
  s.service_code,
  s.name                                                        AS service_name,
  r.task_id,
  t.task_type,
  r.simulation_id,
  r.model_id,
  r.requested_model,
  m.display_name                                                AS model_display_name,
  r.actual_provider,
  r.call_purpose,
  r.attempt_no,
  r.status,
  r.error_type,
  r.requested_at,
  (r.requested_at AT TIME ZONE 'Asia/Seoul')::date                       AS kst_date,
  date_trunc('month', r.requested_at AT TIME ZONE 'Asia/Seoul')::date    AS kst_month,
  r.latency_ms,
  r.input_tokens,
  r.output_tokens,
  r.cached_tokens,
  r.reasoning_tokens,
  r.cost_usd,
  r.cost_status,
  CASE WHEN r.cost_status = 'CONFIRMED' THEN r.cost_usd END     AS confirmed_cost_usd,
  CASE WHEN r.cost_status = 'ESTIMATED' THEN r.cost_usd END     AS estimated_cost_usd,
  (r.cost_status = 'UNKNOWN')                                   AS is_cost_unknown,
  (r.usage_origin = 'CUSTOMER_SERVICE' AND r.customer_id IS NULL) AS is_customer_unclassified,
  r.data_source
FROM ai_requests r
LEFT JOIN customers c ON c.customer_id = r.customer_id
LEFT JOIN projects  p ON p.project_id  = r.project_id
LEFT JOIN services  s ON s.service_id  = r.service_id
LEFT JOIN tasks     t ON t.task_id     = r.task_id
LEFT JOIN models    m ON m.model_id    = r.model_id
"""

# 시뮬레이션 실행별 요약 (P-05 목록). 성공 수·비용은 저장하지 않고 여기서 계산
V_SIMULATION_SUMMARY = """
CREATE VIEW v_simulation_summary AS
SELECT
  sr.simulation_id,
  sr.rerun_of_simulation_id,
  sr.test_type,
  sc.scenario_code,
  sr.status,
  sr.model_count,
  sr.requested_at,
  sr.completed_at,
  sr.executed_by,
  COUNT(r.request_id) FILTER (WHERE res.is_final_attempt)                                  AS final_result_count,
  COUNT(r.request_id) FILTER (WHERE res.is_final_attempt AND r.status = 'SUCCESS')         AS success_count,
  COUNT(r.request_id) FILTER (WHERE res.is_final_attempt AND r.status IN ('FAILED', 'TIMEOUT')) AS failure_count,
  SUM(r.cost_usd) FILTER (WHERE r.cost_status = 'CONFIRMED')                               AS confirmed_cost_usd,
  SUM(r.cost_usd) FILTER (WHERE r.cost_status = 'ESTIMATED')                               AS estimated_cost_usd,
  COUNT(r.request_id) FILTER (WHERE r.cost_status = 'UNKNOWN')                             AS unknown_cost_count,
  CASE
    WHEN bool_or(r.status IN ('PENDING', 'RUNNING'))  THEN '확인 중'
    WHEN bool_or(r.cost_status = 'UNKNOWN')           THEN '미확인 포함'
    WHEN bool_or(r.cost_status = 'ESTIMATED')         THEN '추정 포함'
    WHEN COUNT(r.request_id) > 0                      THEN '확정'
    ELSE '확인 중'
  END                                                                                      AS cost_check_status
FROM simulation_runs sr
LEFT JOIN test_scenarios     sc  ON sc.scenario_id   = sr.scenario_id
LEFT JOIN simulation_results res ON res.simulation_id = sr.simulation_id
LEFT JOIN ai_requests        r   ON r.request_id      = res.request_id
GROUP BY sr.simulation_id, sc.scenario_code
"""

VIEW_COMMENTS = {
    "v_request_facts": "공통 집계 뷰. P-01은 usage_origin = CUSTOMER_SERVICE, P-02는 나머지 3종",
    "v_simulation_summary": (
        "P-05 실행 이력 목록용 요약. 비용 확인 상태: 확인 중 / 미확인 포함 / 추정 포함 / 확정"
    ),
}


def upgrade() -> None:
    """Upgrade schema."""
    # 예산 기간 겹침 금지(EXCLUDE 제약)에 필요. budgets 테이블보다 먼저 만든다.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(SET_UPDATED_AT_FUNCTION)

    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "customers",
        sa.Column(
            "customer_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("customer_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("customer_id", name=op.f("customers_pkey")),
        sa.UniqueConstraint("customer_code", name=op.f("customers_customer_code_key")),
        comment="고객 (P-01). customer_code는 사람이 읽는 고정 코드",
    )
    op.create_table(
        "projects",
        sa.Column(
            "project_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("project_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("project_type", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
            "project_type IN ('INTERNAL_DEV', 'CUSTOMER_PROJECT', 'POC', 'TEST')",
            name="projects_project_type_check",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("projects_pkey")),
        sa.UniqueConstraint("project_code", name=op.f("projects_project_code_key")),
        comment="내부 프로젝트 (P-02). CUSTOMER_PROJECT도 내부 비용(해석, 기업 확인 필요)",
    )
    op.create_table(
        "services",
        sa.Column(
            "service_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("service_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("service_type", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
            "service_type IN ('CUSTOMER_FACING', 'INTERNAL', 'PATRON')",
            name="services_service_type_check",
        ),
        sa.PrimaryKeyConstraint("service_id", name=op.f("services_pkey")),
        sa.UniqueConstraint("service_code", name=op.f("services_service_code_key")),
        comment="호출 서비스. service_code는 프로그램용 고정값, name은 화면 표시명",
    )
    op.create_table(
        "test_scenarios",
        sa.Column(
            "scenario_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("scenario_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column(
            "default_json_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "default_execution_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
            "input_type IN ('TEXT', 'IMAGE', 'TEXT_IMAGE')",
            name="test_scenarios_input_type_check",
        ),
        sa.PrimaryKeyConstraint("scenario_id", name=op.f("test_scenarios_pkey")),
        sa.UniqueConstraint(
            "scenario_code", name=op.f("test_scenarios_scenario_code_key")
        ),
        comment="시나리오 템플릿(레시피). 실행 당시 값은 simulation_runs에 복사 저장",
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "password_hash",
            sa.Text(),
            nullable=False,
            comment="Argon2id 해시(pwdlib[argon2]). 비밀번호 원문은 저장하지 않음",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("users_pkey")),
        sa.UniqueConstraint("email", name=op.f("users_email_key")),
        sa.UniqueConstraint("user_code", name=op.f("users_user_code_key")),
        comment="Patron 관리자 계정. 비용 귀속 대상이 아니라 실행자·등록자 기록용",
    )
    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "secret_ref",
            sa.Text(),
            nullable=True,
            comment="Key 원문이 든 환경변수 이름. Mock Key는 NULL",
        ),
        sa.Column(
            "key_fingerprint",
            sa.Text(),
            nullable=True,
            comment="OpenRouter Key 식별자의 HMAC-SHA256. hash/label 원문 저장 금지",
        ),
        sa.Column("workspace_ref", sa.Text(), nullable=True),
        sa.Column("owner_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
        sa.Column("limit_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column(
            "limit_reset_period", sa.Text(), server_default="NONE", nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_mock", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
            "(owner_type = 'CUSTOMER' AND customer_id IS NOT NULL AND project_id IS NULL) OR (owner_type = 'PROJECT' AND project_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_api_keys_owner",
        ),
        sa.CheckConstraint(
            "environment IN ('DEV', 'TEST', 'PROD')", name="api_keys_environment_check"
        ),
        sa.CheckConstraint(
            "limit_reset_period IN ('NONE', 'DAILY', 'WEEKLY', 'MONTHLY')",
            name="api_keys_limit_reset_period_check",
        ),
        sa.CheckConstraint(
            "owner_type IN ('CUSTOMER', 'PROJECT')", name="api_keys_owner_type_check"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name="api_keys_status_check"
        ),
        sa.CheckConstraint("limit_usd >= 0", name="api_keys_limit_usd_check"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name=op.f("api_keys_customer_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("api_keys_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("key_id", name=op.f("api_keys_pkey")),
        comment="OpenRouter Key 매핑. 원문은 secret_ref가 가리키는 환경변수에만 있음",
    )
    op.create_table(
        "budgets",
        sa.Column(
            "budget_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "monthly_amount_usd", sa.Numeric(precision=30, scale=18), nullable=False
        ),
        sa.Column(
            "warning_threshold_pct", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column("effective_from_month", sa.Date(), nullable=False),
        sa.Column("effective_to_month", sa.Date(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
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
        postgresql.ExcludeConstraint(
            (sa.column("scope_type"), "="),
            (sa.text("COALESCE(customer_id, -1)"), "="),
            (sa.text("COALESCE(project_id, -1)"), "="),
            (
                sa.text("daterange(effective_from_month, effective_to_month, '[]')"),
                "&&",
            ),
            using="gist",
            name="ex_budgets_no_overlap",
        ),
        sa.CheckConstraint(
            "(scope_type = 'CUSTOMER' AND customer_id IS NOT NULL AND project_id IS NULL) OR (scope_type = 'PROJECT' AND project_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_budgets_scope",
        ),
        sa.CheckConstraint(
            "scope_type IN ('CUSTOMER', 'PROJECT')", name="budgets_scope_type_check"
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM effective_from_month) = 1",
            name="budgets_effective_from_month_check",
        ),
        sa.CheckConstraint(
            "effective_to_month IS NULL OR EXTRACT(DAY FROM effective_to_month) = 1",
            name="budgets_effective_to_month_check",
        ),
        sa.CheckConstraint(
            "effective_to_month IS NULL OR effective_to_month >= effective_from_month",
            name="ck_budgets_period",
        ),
        sa.CheckConstraint(
            "monthly_amount_usd > 0", name="budgets_monthly_amount_usd_check"
        ),
        sa.CheckConstraint(
            "warning_threshold_pct BETWEEN 0 AND 100",
            name="budgets_warning_threshold_pct_check",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("budgets_created_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name=op.f("budgets_customer_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("budgets_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
            name=op.f("budgets_updated_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("budget_id", name=op.f("budgets_pkey")),
        comment="월 예산(고객·프로젝트). 사용률·상태는 저장하지 않고 백엔드 공통 집계 코드에서 계산(v0.6). 예산이 없으면 0%가 아니라 미설정",
    )
    op.create_table(
        "change_logs",
        sa.Column("log_id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('CREATE', 'UPDATE', 'STATUS_CHANGE', 'DEACTIVATE')",
            name="change_logs_action_check",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            ["users.user_id"],
            name=op.f("change_logs_changed_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("log_id", name=op.f("change_logs_pkey")),
        comment="Key 매핑·모델 상태·예산·구독료·호출 귀속 수정 등 변경 이력. 대상이 여러 테이블이라 FK 없음",
    )
    op.create_index(
        "ix_change_logs_entity",
        "change_logs",
        ["entity_type", "entity_id", "changed_at"],
        unique=False,
    )
    op.create_table(
        "input_assets",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0", name="input_assets_file_size_bytes_check"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.user_id"],
            name=op.f("input_assets_uploaded_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("input_assets_pkey")),
        comment="시뮬레이터 이미지 입력 참조. 파일은 서버에 보관, DB에는 경로·해시만",
    )
    op.create_table(
        "models",
        sa.Column(
            "model_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("openrouter_model_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="TESTING", nullable=False),
        sa.Column(
            "input_modalities",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "output_modalities",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "supported_parameters",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column(
            "openrouter_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("metadata_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.Text(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_request_id", sa.Uuid(), nullable=True),
        sa.Column("last_success_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
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
            "last_test_status IN ('SUCCESS', 'FAILED', 'TIMEOUT')",
            name="models_last_test_status_check",
        ),
        sa.CheckConstraint(
            "status IN ('TESTING', 'ACTIVE', 'INACTIVE')", name="models_status_check"
        ),
        sa.CheckConstraint("context_length > 0", name="models_context_length_check"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("models_created_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("model_id", name=op.f("models_pkey")),
        sa.UniqueConstraint(
            "openrouter_model_id", name=op.f("models_openrouter_model_id_key")
        ),
        comment="등록 모델 (P-03). provider는 모델 제작사. 연결 테스트 이력은 SYSTEM_TEST 호출",
    )
    op.create_table(
        "subscription_costs",
        sa.Column(
            "subscription_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("subscription_reference", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("subscription_type", sa.Text(), nullable=True),
        sa.Column("applied_month", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="USD", nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default="ACTIVE", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
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
            "currency = 'USD'", name="subscription_costs_currency_check"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED')", name="subscription_costs_status_check"
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM applied_month) = 1",
            name="subscription_costs_applied_month_check",
        ),
        sa.CheckConstraint("amount >= 0", name="subscription_costs_amount_check"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("subscription_costs_created_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("subscription_costs_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
            name=op.f("subscription_costs_updated_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "subscription_id", name=op.f("subscription_costs_pkey")
        ),
        sa.UniqueConstraint(
            "subscription_reference",
            "applied_month",
            name="uq_subscription_costs_ref_month",
        ),
        comment="월 구독료. 결제 후 실제 청구액을 USD로 입력(원화 원금은 note). project_id NULL = 미배분",
    )
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("external_task_ref", sa.Text(), nullable=True),
        sa.Column("usage_origin", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(usage_origin = 'CUSTOMER_SERVICE' AND project_id IS NULL) OR (usage_origin <> 'CUSTOMER_SERVICE' AND customer_id IS NULL)",
            name="ck_tasks_origin_owner",
        ),
        sa.CheckConstraint(
            "data_source IN ('MOCK', 'LIVE')", name="tasks_data_source_check"
        ),
        sa.CheckConstraint(
            "usage_origin IN ('CUSTOMER_SERVICE', 'INTERNAL_DEVELOPMENT', 'SIMULATION', 'SYSTEM_TEST')",
            name="tasks_usage_origin_check",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_tasks_period",
        ),
        sa.CheckConstraint(
            "num_nonnulls(customer_id, project_id) <= 1", name="ck_tasks_single_owner"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name=op.f("tasks_customer_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("tasks_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.service_id"],
            name=op.f("tasks_service_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("task_id", name=op.f("tasks_pkey")),
        sa.UniqueConstraint(
            "service_id", "external_task_ref", name="uq_tasks_service_ref"
        ),
        comment="업무 작업. external_task_ref는 호출한 서비스 쪽 작업 번호(참고값)",
    )
    op.create_table(
        "user_sessions",
        sa.Column(
            "session_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "token_hash",
            sa.CHAR(length=64),
            nullable=False,
            comment="SHA-256(세션 토큰) 소문자 16진수 64자. 토큰 원문 저장 금지",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="발급 시각 + 12시간. 쿠키 수명과 같은 상수에서 계산",
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name="user_sessions_token_hash_check"
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("user_sessions_user_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", name=op.f("user_sessions_pkey")),
        sa.UniqueConstraint("token_hash", name=op.f("user_sessions_token_hash_key")),
        comment="로그인 세션. 토큰 원문은 저장하지 않고 SHA-256 해시만 저장. 로그아웃·비활성화 시 행 삭제",
    )
    op.create_index(
        "ix_user_sessions_expires", "user_sessions", ["expires_at"], unique=False
    )
    op.create_index("ix_user_sessions_user", "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "key_usage_snapshots",
        sa.Column(
            "snapshot_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("key_id", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage_total_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("usage_daily_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column(
            "usage_weekly_usd", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column(
            "usage_monthly_usd", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column("limit_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column(
            "limit_remaining_usd", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column(
            "raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["api_keys.key_id"],
            name=op.f("key_usage_snapshots_key_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", name=op.f("key_usage_snapshots_pkey")),
        comment="GET /key 응답 스냅샷. label, hash 등 Key 일부가 담긴 필드는 제거 후 저장",
    )
    op.create_index(
        "ix_key_usage_snapshots_key_time",
        "key_usage_snapshots",
        ["key_id", "captured_at"],
        unique=False,
    )
    op.create_table(
        "model_prices",
        sa.Column(
            "price_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("execution_provider", sa.Text(), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), server_default="USD", nullable=False),
        sa.Column("price_status", sa.Text(), nullable=False),
        sa.Column(
            "input_price_per_token", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column(
            "output_price_per_token", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column(
            "cache_read_price_per_token",
            sa.Numeric(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "cache_write_price_per_token",
            sa.Numeric(precision=30, scale=18),
            nullable=True,
        ),
        sa.Column(
            "raw_pricing", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "price_status <> 'KNOWN' OR (input_price_per_token IS NOT NULL AND output_price_per_token IS NOT NULL)",
            name="ck_model_prices_known",
        ),
        sa.CheckConstraint(
            "price_status IN ('KNOWN', 'UNKNOWN')",
            name="model_prices_price_status_check",
        ),
        sa.CheckConstraint(
            "source IN ('OPENROUTER_MODELS', 'OPENROUTER_ENDPOINTS', 'MANUAL')",
            name="model_prices_source_check",
        ),
        sa.CheckConstraint(
            "cache_read_price_per_token >= 0",
            name="model_prices_cache_read_price_per_token_check",
        ),
        sa.CheckConstraint(
            "cache_write_price_per_token >= 0",
            name="model_prices_cache_write_price_per_token_check",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_model_prices_period",
        ),
        sa.CheckConstraint(
            "input_price_per_token >= 0",
            name="model_prices_input_price_per_token_check",
        ),
        sa.CheckConstraint(
            "output_price_per_token >= 0",
            name="model_prices_output_price_per_token_check",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.model_id"],
            name=op.f("model_prices_model_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("price_id", name=op.f("model_prices_pkey")),
        comment="가격 기준정보 이력. 수정하지 않고 새 행 추가. execution_provider NULL = 모델 대표가",
    )
    op.create_index(
        "uq_model_prices_current",
        "model_prices",
        ["model_id", "execution_provider"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.create_table(
        "simulation_runs",
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("rerun_of_simulation_id", sa.Uuid(), nullable=True),
        sa.Column("test_type", sa.Text(), nullable=False),
        sa.Column("scenario_id", sa.BigInteger(), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=True),
        sa.Column(
            "json_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "execution_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "routing_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("input_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("model_count", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("key_id", sa.BigInteger(), nullable=False),
        sa.Column("executed_by", sa.BigInteger(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False),
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
            "(test_type = 'SCENARIO' AND scenario_id IS NOT NULL) OR (test_type = 'CUSTOM' AND scenario_id IS NULL)",
            name="ck_simulation_runs_scenario",
        ),
        sa.CheckConstraint(
            "data_source IN ('MOCK', 'LIVE')", name="simulation_runs_data_source_check"
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED')",
            name="simulation_runs_status_check",
        ),
        sa.CheckConstraint(
            "test_type IN ('SCENARIO', 'CUSTOM')",
            name="simulation_runs_test_type_check",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_simulation_runs_period",
        ),
        sa.CheckConstraint(
            "model_count BETWEEN 2 AND 4", name="simulation_runs_model_count_check"
        ),
        sa.CheckConstraint(
            "rerun_of_simulation_id IS DISTINCT FROM simulation_id",
            name="ck_simulation_runs_not_self",
        ),
        sa.ForeignKeyConstraint(
            ["executed_by"],
            ["users.user_id"],
            name=op.f("simulation_runs_executed_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["api_keys.key_id"],
            name=op.f("simulation_runs_key_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("simulation_runs_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rerun_of_simulation_id"],
            ["simulation_runs.simulation_id"],
            name=op.f("simulation_runs_rerun_of_simulation_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["test_scenarios.scenario_id"],
            name=op.f("simulation_runs_scenario_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("simulation_id", name=op.f("simulation_runs_pkey")),
        comment="비교 실행 1회. 성공 수·비용 합계는 저장하지 않고 v_simulation_summary에서 계산",
    )
    op.create_table(
        "ai_requests",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("usage_origin", sa.Text(), nullable=False),
        sa.Column(
            "owner_type",
            sa.Text(),
            sa.Computed(
                "CASE usage_origin WHEN 'CUSTOMER_SERVICE' THEN 'CUSTOMER' WHEN 'INTERNAL_DEVELOPMENT' THEN 'INTERNAL' ELSE 'POC' END",
                persisted=True,
            ),
            nullable=False,
            comment="usage_origin에서 자동 계산 (직접 입력 불가)",
        ),
        sa.Column("key_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "executed_by",
            sa.BigInteger(),
            nullable=True,
            comment="시뮬레이션·연결 테스트를 실행한 관리자. 비용 귀속에는 쓰지 않음 (v0.4)",
        ),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("simulation_id", sa.Uuid(), nullable=True),
        sa.Column("call_purpose", sa.Text(), nullable=False),
        sa.Column(
            "attempt_no", sa.SmallInteger(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("parent_request_id", sa.Uuid(), nullable=True),
        sa.Column("model_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_model", sa.Text(), nullable=False),
        sa.Column("requested_provider", sa.Text(), nullable=True),
        sa.Column("actual_model", sa.Text(), nullable=True),
        sa.Column("actual_provider", sa.Text(), nullable=True),
        sa.Column(
            "routing_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "execution_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("input_reference", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("finish_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("external_generation_id", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "cached_tokens",
            sa.Integer(),
            nullable=True,
            comment="input_tokens에 포함된 값. 합계 시 더하지 않음",
        ),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "reasoning_tokens",
            sa.Integer(),
            nullable=True,
            comment="output_tokens에 포함된 값. 합계 시 더하지 않음",
        ),
        sa.Column("usage_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=30, scale=18),
            nullable=True,
            comment="비용 미확인이면 NULL (0이 아님)",
        ),
        sa.Column("cost_status", sa.Text(), server_default="UNKNOWN", nullable=False),
        sa.Column("cost_source", sa.Text(), nullable=True),
        sa.Column("price_id", sa.BigInteger(), nullable=True),
        sa.Column("cost_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False),
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
            "(cost_status = 'UNKNOWN' AND cost_usd IS NULL) OR (cost_status <> 'UNKNOWN' AND cost_usd IS NOT NULL)",
            name="ck_ai_requests_cost_unknown",
        ),
        sa.CheckConstraint(
            "(status = 'SUCCESS' AND error_type IS NULL) OR (status IN ('FAILED', 'TIMEOUT') AND error_type IS NOT NULL) OR (status IN ('PENDING', 'RUNNING', 'CANCELLED'))",
            name="ck_ai_requests_error",
        ),
        sa.CheckConstraint(
            "(usage_origin = 'CUSTOMER_SERVICE' AND project_id IS NULL) OR (usage_origin <> 'CUSTOMER_SERVICE' AND customer_id IS NULL AND project_id IS NOT NULL)",
            name="ck_ai_requests_origin_owner",
        ),
        sa.CheckConstraint(
            "(usage_origin IN ('SIMULATION', 'SYSTEM_TEST') AND executed_by IS NOT NULL) OR (usage_origin NOT IN ('SIMULATION', 'SYSTEM_TEST') AND executed_by IS NULL)",
            name="ck_ai_requests_executed_by",
        ),
        sa.CheckConstraint(
            "call_purpose IN ('GENERATION', 'EVALUATION', 'REGENERATION', 'EXPERIMENT', 'TEST', 'OTHER')",
            name="ai_requests_call_purpose_check",
        ),
        sa.CheckConstraint(
            "cost_source IN ('API_RESPONSE', 'GENERATION_LOOKUP', 'PRICE_ESTIMATE', 'MANUAL', 'MOCK')",
            name="ai_requests_cost_source_check",
        ),
        sa.CheckConstraint(
            "cost_status <> 'ESTIMATED' OR price_id IS NOT NULL",
            name="ck_ai_requests_cost_estimated",
        ),
        sa.CheckConstraint(
            "cost_status IN ('CONFIRMED', 'ESTIMATED', 'UNKNOWN')",
            name="ai_requests_cost_status_check",
        ),
        sa.CheckConstraint(
            "data_source IN ('MOCK', 'LIVE')", name="ai_requests_data_source_check"
        ),
        sa.CheckConstraint(
            "error_type IN ('AUTH_ERROR', 'RATE_LIMIT', 'TIMEOUT_ERROR', 'PROVIDER_ERROR', 'NETWORK_ERROR', 'INVALID_RESPONSE', 'UNSUPPORTED_INPUT', 'UNKNOWN_ERROR')",
            name="ai_requests_error_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'TIMEOUT', 'CANCELLED')",
            name="ai_requests_status_check",
        ),
        sa.CheckConstraint(
            "usage_origin <> 'SIMULATION' OR simulation_id IS NOT NULL",
            name="ck_ai_requests_simulation",
        ),
        sa.CheckConstraint(
            "usage_origin IN ('CUSTOMER_SERVICE', 'INTERNAL_DEVELOPMENT', 'SIMULATION', 'SYSTEM_TEST')",
            name="ai_requests_usage_origin_check",
        ),
        sa.CheckConstraint(
            "(attempt_no = 1 AND parent_request_id IS NULL) OR (attempt_no > 1 AND parent_request_id IS NOT NULL)",
            name="ck_ai_requests_retry",
        ),
        sa.CheckConstraint(
            "(cached_tokens IS NULL OR input_tokens IS NULL OR cached_tokens <= input_tokens) AND (reasoning_tokens IS NULL OR output_tokens IS NULL OR reasoning_tokens <= output_tokens)",
            name="ck_ai_requests_token_breakdown",
        ),
        sa.CheckConstraint("attempt_no >= 1", name="ai_requests_attempt_no_check"),
        sa.CheckConstraint(
            "cache_write_tokens >= 0", name="ai_requests_cache_write_tokens_check"
        ),
        sa.CheckConstraint(
            "cached_tokens >= 0", name="ai_requests_cached_tokens_check"
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_ai_requests_period",
        ),
        sa.CheckConstraint("cost_usd >= 0", name="ai_requests_cost_usd_check"),
        sa.CheckConstraint("input_tokens >= 0", name="ai_requests_input_tokens_check"),
        sa.CheckConstraint("latency_ms >= 0", name="ai_requests_latency_ms_check"),
        sa.CheckConstraint(
            "num_nonnulls(customer_id, project_id) <= 1",
            name="ck_ai_requests_single_owner",
        ),
        sa.CheckConstraint(
            "output_tokens >= 0", name="ai_requests_output_tokens_check"
        ),
        sa.CheckConstraint(
            "reasoning_tokens >= 0", name="ai_requests_reasoning_tokens_check"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name=op.f("ai_requests_customer_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["executed_by"],
            ["users.user_id"],
            name=op.f("ai_requests_executed_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["api_keys.key_id"],
            name=op.f("ai_requests_key_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.model_id"],
            name=op.f("ai_requests_model_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_request_id"],
            ["ai_requests.request_id"],
            name=op.f("ai_requests_parent_request_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["price_id"],
            ["model_prices.price_id"],
            name=op.f("ai_requests_price_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.project_id"],
            name=op.f("ai_requests_project_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.service_id"],
            name=op.f("ai_requests_service_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulation_runs.simulation_id"],
            name=op.f("ai_requests_simulation_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("ai_requests_task_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("request_id", name=op.f("ai_requests_pkey")),
        sa.UniqueConstraint(
            "external_generation_id",
            name=op.f("ai_requests_external_generation_id_key"),
        ),
        sa.UniqueConstraint(
            "simulation_id", "request_id", name="uq_ai_requests_sim_req"
        ),
        comment="AI 호출 이력. 호출 1회 = 1행. 모든 사용량·비용 집계의 기준 데이터(Source of Truth)",
    )
    op.create_index(
        "ix_ai_requests_cost_unknown",
        "ai_requests",
        ["requested_at"],
        unique=False,
        postgresql_where=sa.text("cost_status = 'UNKNOWN'"),
    )
    op.create_index(
        "ix_ai_requests_customer_time",
        "ai_requests",
        ["customer_id", "requested_at"],
        unique=False,
    )
    op.create_index("ix_ai_requests_model", "ai_requests", ["model_id"], unique=False)
    op.create_index(
        "ix_ai_requests_open",
        "ai_requests",
        ["requested_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )
    op.create_index(
        "ix_ai_requests_origin_time",
        "ai_requests",
        ["usage_origin", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_requests_parent", "ai_requests", ["parent_request_id"], unique=False
    )
    op.create_index(
        "ix_ai_requests_project_time",
        "ai_requests",
        ["project_id", "requested_at"],
        unique=False,
    )
    op.create_index("ix_ai_requests_task", "ai_requests", ["task_id"], unique=False)
    # models ↔ ai_requests 순환 참조라 두 테이블을 모두 만든 뒤 외래키를 추가한다.
    op.create_foreign_key(
        "fk_models_last_test_request",
        "models",
        "ai_requests",
        ["last_test_request_id"],
        ["request_id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "simulation_run_assets",
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["input_assets.asset_id"],
            name=op.f("simulation_run_assets_asset_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulation_runs.simulation_id"],
            name=op.f("simulation_run_assets_simulation_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "simulation_id", "asset_id", name=op.f("simulation_run_assets_pkey")
        ),
    )
    op.create_table(
        "usage_reconciliations",
        sa.Column(
            "reconciliation_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("key_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("end_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "external_usage_usd", sa.Numeric(precision=30, scale=18), nullable=True
        ),
        sa.Column(
            "patron_confirmed_usd", sa.Numeric(precision=30, scale=18), nullable=False
        ),
        sa.Column(
            "patron_estimated_usd", sa.Numeric(precision=30, scale=18), nullable=False
        ),
        sa.Column("patron_unknown_count", sa.Integer(), nullable=False),
        sa.Column("difference_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("comparability", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="OPEN", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
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
            "(comparability = 'COMPARABLE' AND external_usage_usd IS NOT NULL AND difference_usd IS NOT NULL) OR (comparability = 'UNCOMPARABLE' AND external_usage_usd IS NULL AND difference_usd IS NULL)",
            name="ck_usage_reconciliations_comparable",
        ),
        sa.CheckConstraint(
            "comparability IN ('COMPARABLE', 'UNCOMPARABLE')",
            name="usage_reconciliations_comparability_check",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'REVIEWED')", name="usage_reconciliations_status_check"
        ),
        sa.CheckConstraint(
            "patron_unknown_count >= 0",
            name="usage_reconciliations_patron_unknown_count_check",
        ),
        sa.CheckConstraint(
            "period_end > period_start", name="ck_usage_reconciliations_period"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name=op.f("usage_reconciliations_created_by_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["end_snapshot_id"],
            ["key_usage_snapshots.snapshot_id"],
            name=op.f("usage_reconciliations_end_snapshot_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["key_id"],
            ["api_keys.key_id"],
            name=op.f("usage_reconciliations_key_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["start_snapshot_id"],
            ["key_usage_snapshots.snapshot_id"],
            name=op.f("usage_reconciliations_start_snapshot_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "reconciliation_id", name=op.f("usage_reconciliations_pkey")
        ),
        comment="OpenRouter 사용량과 Patron 기록의 대조. 차액은 개별 호출에 배분하지 않음",
    )
    op.create_table(
        "ai_request_payloads",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "request_messages", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column(
            "response_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["ai_requests.request_id"],
            name=op.f("ai_request_payloads_request_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("request_id", name=op.f("ai_request_payloads_pkey")),
        comment="호출 원문. 이미지는 base64 대신 asset_id로 가리킴",
    )
    op.create_table(
        "cost_adjustments",
        sa.Column(
            "adjustment_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("old_cost_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("new_cost_usd", sa.Numeric(precision=30, scale=18), nullable=True),
        sa.Column("old_cost_status", sa.Text(), nullable=False),
        sa.Column("new_cost_status", sa.Text(), nullable=False),
        sa.Column("old_cost_source", sa.Text(), nullable=True),
        sa.Column("new_cost_source", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("adjusted_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "adjusted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "new_cost_status IN ('CONFIRMED', 'ESTIMATED', 'UNKNOWN')",
            name="cost_adjustments_new_cost_status_check",
        ),
        sa.CheckConstraint(
            "old_cost_status IN ('CONFIRMED', 'ESTIMATED', 'UNKNOWN')",
            name="cost_adjustments_old_cost_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["adjusted_by_user_id"],
            ["users.user_id"],
            name=op.f("cost_adjustments_adjusted_by_user_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["ai_requests.request_id"],
            name=op.f("cost_adjustments_request_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("adjustment_id", name=op.f("cost_adjustments_pkey")),
        comment="호출 비용 정정 이력. adjusted_by_user_id NULL = 시스템 정산",
    )
    op.create_index(
        "ix_cost_adjustments_request", "cost_adjustments", ["request_id"], unique=False
    )
    op.create_table(
        "simulation_results",
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("slot_no", sa.SmallInteger(), nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("execution_provider", sa.Text(), nullable=False),
        sa.Column("model_status_at_run", sa.Text(), nullable=False),
        sa.Column("model_display_name_at_run", sa.Text(), nullable=False),
        sa.Column(
            "is_final_attempt",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("json_parse_status", sa.Text(), nullable=True),
        sa.Column("schema_validation_status", sa.Text(), nullable=True),
        sa.Column(
            "missing_required_fields", postgresql.ARRAY(sa.Text()), nullable=True
        ),
        sa.Column(
            "validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("comparability_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "json_parse_status IN ('PASSED', 'FAILED', 'NOT_APPLICABLE', 'NOT_EXECUTED')",
            name="simulation_results_json_parse_status_check",
        ),
        sa.CheckConstraint(
            "model_status_at_run IN ('TESTING', 'ACTIVE', 'INACTIVE')",
            name="simulation_results_model_status_at_run_check",
        ),
        sa.CheckConstraint(
            "schema_validation_status IN ('PASSED', 'FAILED', 'NOT_APPLICABLE', 'NOT_EXECUTED')",
            name="simulation_results_schema_validation_status_check",
        ),
        sa.CheckConstraint(
            "slot_no BETWEEN 1 AND 4", name="simulation_results_slot_no_check"
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.model_id"],
            name=op.f("simulation_results_model_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id", "request_id"],
            ["ai_requests.simulation_id", "ai_requests.request_id"],
            name="fk_simulation_results_request",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulation_runs.simulation_id"],
            name=op.f("simulation_results_simulation_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "simulation_id", "request_id", name=op.f("simulation_results_pkey")
        ),
        sa.UniqueConstraint(
            "request_id", name=op.f("simulation_results_request_id_key")
        ),
    )
    op.create_index(
        "uq_sim_results_model_provider",
        "simulation_results",
        ["simulation_id", "model_id", "execution_provider"],
        unique=True,
        postgresql_where=sa.text("is_final_attempt"),
    )
    op.create_index(
        "uq_sim_results_slot",
        "simulation_results",
        ["simulation_id", "slot_no"],
        unique=True,
        postgresql_where=sa.text("is_final_attempt"),
    )
    # ### end Alembic commands ###

    for table in UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    op.execute(V_REQUEST_FACTS)
    op.execute(V_SIMULATION_SUMMARY)
    for view, comment in VIEW_COMMENTS.items():
        # COMMENT 문은 바인드 파라미터를 받지 않으므로 작은따옴표를 이스케이프해 문자열로 넣는다.
        escaped = comment.replace("'", "''")
        op.execute(f"COMMENT ON VIEW {view} IS '{escaped}'")


def downgrade() -> None:
    """Downgrade schema. upgrade의 역순으로 모두 지운다(트리거는 테이블과 함께 지워진다)."""
    op.execute("DROP VIEW v_simulation_summary")
    op.execute("DROP VIEW v_request_facts")
    op.drop_constraint("fk_models_last_test_request", "models", type_="foreignkey")

    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "uq_sim_results_slot",
        table_name="simulation_results",
        postgresql_where=sa.text("is_final_attempt"),
    )
    op.drop_index(
        "uq_sim_results_model_provider",
        table_name="simulation_results",
        postgresql_where=sa.text("is_final_attempt"),
    )
    op.drop_table("simulation_results")
    op.drop_index("ix_cost_adjustments_request", table_name="cost_adjustments")
    op.drop_table("cost_adjustments")
    op.drop_table("ai_request_payloads")
    op.drop_table("usage_reconciliations")
    op.drop_table("simulation_run_assets")
    op.drop_index("ix_ai_requests_task", table_name="ai_requests")
    op.drop_index("ix_ai_requests_project_time", table_name="ai_requests")
    op.drop_index("ix_ai_requests_parent", table_name="ai_requests")
    op.drop_index("ix_ai_requests_origin_time", table_name="ai_requests")
    op.drop_index(
        "ix_ai_requests_open",
        table_name="ai_requests",
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )
    op.drop_index("ix_ai_requests_model", table_name="ai_requests")
    op.drop_index("ix_ai_requests_customer_time", table_name="ai_requests")
    op.drop_index(
        "ix_ai_requests_cost_unknown",
        table_name="ai_requests",
        postgresql_where=sa.text("cost_status = 'UNKNOWN'"),
    )
    op.drop_table("ai_requests")
    op.drop_table("simulation_runs")
    op.drop_index(
        "uq_model_prices_current",
        table_name="model_prices",
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.drop_table("model_prices")
    op.drop_index("ix_key_usage_snapshots_key_time", table_name="key_usage_snapshots")
    op.drop_table("key_usage_snapshots")
    op.drop_index("ix_user_sessions_user", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("tasks")
    op.drop_table("subscription_costs")
    op.drop_table("models")
    op.drop_table("input_assets")
    op.drop_index("ix_change_logs_entity", table_name="change_logs")
    op.drop_table("change_logs")
    op.drop_table("budgets")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("test_scenarios")
    op.drop_table("services")
    op.drop_table("projects")
    op.drop_table("customers")
    # ### end Alembic commands ###

    op.execute("DROP FUNCTION set_updated_at()")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
