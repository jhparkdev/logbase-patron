"""SQLAlchemy ORM 모델 전체 (설계서 v0.6, 테이블 22개).

- 테이블·컬럼·제약은 설계 SQL(patron_schema_v0.6)과 같게 만든다. 제약 이름도 설계와 같다.
- 상태값 목록은 아래 StrEnum에 한 번만 정의하고, CHECK 제약을 그 값으로 만든다.
  나중에 API 스키마도 같은 Enum을 써서 OpenAPI로 프론트엔드에 전달한다.
- 확장(btree_gist), updated_at 트리거, 뷰 2개는 모델로 표현하지 않고 마이그레이션에서 만든다.
- 관계(relationship)는 서비스 코드에서 필요해질 때 추가한다. 지금은 컬럼과 외래키만 둔다.
- 컬럼은 설계 SQL과 같은 순서로 선언한다(스키마 비교와 pg_dump 결과를 맞추기 위해).

공통 규칙: 시각은 TIMESTAMPTZ(UTC), 금액은 NUMERIC(30,18)이고 미확인은 0이 아니라 NULL,
외래키는 ON DELETE RESTRICT(행을 지우지 않고 status/is_active로 비활성화).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    FetchedValue,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 이름을 적지 않은 제약에 PostgreSQL 자동 이름과 같은 이름을 붙인다(설계 SQL과 맞추기 위해).
# 예: customers_pkey, customers_customer_code_key, api_keys_customer_id_fkey
NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "fk": "%(table_name)s_%(column_0_N_name)s_fkey",
}

# 금액·단가 (설계 v0.6: NUMERIC(30,18))
MONEY = Numeric(30, 18)
SHA256_HEX_LENGTH = 64
CURRENCY_CODE_LENGTH = 3
RESTRICT = "RESTRICT"


class Base(DeclarativeBase):
    """모든 ORM 모델의 부모. Alembic은 Base.metadata를 보고 마이그레이션을 만든다."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# 상태값 목록 (순서는 설계 SQL의 CHECK 목록 순서와 같게 둔다)
# ---------------------------------------------------------------------------


class ProjectType(StrEnum):
    INTERNAL_DEV = "INTERNAL_DEV"
    CUSTOMER_PROJECT = "CUSTOMER_PROJECT"
    POC = "POC"
    TEST = "TEST"


class ServiceType(StrEnum):
    CUSTOMER_FACING = "CUSTOMER_FACING"
    INTERNAL = "INTERNAL"
    PATRON = "PATRON"


class KeyOwnerType(StrEnum):
    CUSTOMER = "CUSTOMER"
    PROJECT = "PROJECT"


class KeyEnvironment(StrEnum):
    DEV = "DEV"
    TEST = "TEST"
    PROD = "PROD"


class KeyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class LimitResetPeriod(StrEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ModelStatus(StrEnum):
    """등록 모델 상태. 시뮬레이션 결과에는 실행 당시 상태로 복사해 둔다."""

    TESTING = "TESTING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ConnectionTestStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class PriceStatus(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class PriceSource(StrEnum):
    OPENROUTER_MODELS = "OPENROUTER_MODELS"
    OPENROUTER_ENDPOINTS = "OPENROUTER_ENDPOINTS"
    MANUAL = "MANUAL"


class UsageOrigin(StrEnum):
    """호출 출처. 고객 사용량(CUSTOMER_SERVICE)과 나머지(내부·시뮬레이션·테스트)를 섞지 않는다."""

    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    INTERNAL_DEVELOPMENT = "INTERNAL_DEVELOPMENT"
    SIMULATION = "SIMULATION"
    SYSTEM_TEST = "SYSTEM_TEST"


class RequestOwnerType(StrEnum):
    """ai_requests.owner_type: usage_origin에서 DB가 자동 계산하는 비용 귀속 구분."""

    CUSTOMER = "CUSTOMER"
    INTERNAL = "INTERNAL"
    POC = "POC"


class DataSource(StrEnum):
    MOCK = "MOCK"
    LIVE = "LIVE"


class InputType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    TEXT_IMAGE = "TEXT_IMAGE"


class TestType(StrEnum):
    SCENARIO = "SCENARIO"
    CUSTOM = "CUSTOM"


class SimulationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CallPurpose(StrEnum):
    GENERATION = "GENERATION"
    EVALUATION = "EVALUATION"
    REGENERATION = "REGENERATION"
    EXPERIMENT = "EXPERIMENT"
    TEST = "TEST"
    OTHER = "OTHER"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class ErrorType(StrEnum):
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class CostStatus(StrEnum):
    """비용 상태. UNKNOWN이면 cost_usd는 반드시 NULL이다(0으로 기록하지 않음)."""

    CONFIRMED = "CONFIRMED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class CostSource(StrEnum):
    API_RESPONSE = "API_RESPONSE"
    GENERATION_LOOKUP = "GENERATION_LOOKUP"
    PRICE_ESTIMATE = "PRICE_ESTIMATE"
    MANUAL = "MANUAL"
    MOCK = "MOCK"
    NO_CHARGE = "NO_CHARGE"


class ValidationStatus(StrEnum):
    """시뮬레이션 결과의 JSON 파싱·Schema 검증 결과."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EXECUTED = "NOT_EXECUTED"


class BudgetScopeType(StrEnum):
    CUSTOMER = "CUSTOMER"
    PROJECT = "PROJECT"


class SubscriptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class Comparability(StrEnum):
    COMPARABLE = "COMPARABLE"
    UNCOMPARABLE = "UNCOMPARABLE"


class ReconciliationStatus(StrEnum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"


class ChangeAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    STATUS_CHANGE = "STATUS_CHANGE"
    DEACTIVATE = "DEACTIVATE"


# ---------------------------------------------------------------------------
# 제약·컬럼을 만드는 도우미
# ---------------------------------------------------------------------------


def _sql_list(values: type[StrEnum]) -> str:
    """Enum 값을 SQL 목록 문자열로 만든다. 예: 'A', 'B'"""
    return ", ".join(f"'{value}'" for value in values)


def in_check(table: str, column: str, values: type[StrEnum]) -> CheckConstraint:
    """컬럼 값이 Enum 목록 안에 있어야 한다는 CHECK. 이름은 PostgreSQL 자동 이름(<테이블>_<컬럼>_check)."""
    return CheckConstraint(
        f"{column} IN ({_sql_list(values)})", name=f"{table}_{column}_check"
    )


def column_check(table: str, column: str, condition: str) -> CheckConstraint:
    """한 컬럼에 대한 CHECK(예: >= 0). 이름은 PostgreSQL 자동 이름(<테이블>_<컬럼>_check)."""
    return CheckConstraint(condition, name=f"{table}_{column}_check")


def fk(target: str, **kwargs: Any) -> ForeignKey:
    """ON DELETE RESTRICT 외래키. 참조되는 행은 지울 수 없다."""
    return ForeignKey(target, ondelete=RESTRICT, **kwargs)


def bigint_identity_pk() -> Mapped[int]:
    """BIGINT GENERATED ALWAYS AS IDENTITY 기본키. DB가 번호를 매기고 직접 넣지 못하게 한다."""
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def updated_at_column() -> Mapped[datetime]:
    """수정 시각. 값은 DB 트리거(set_updated_at)가 바꾸므로 ORM은 저장 뒤 DB에서 다시 읽는다."""
    return mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        server_onupdate=FetchedValue(),
    )


def is_active_column() -> Mapped[bool]:
    return mapped_column(Boolean, server_default=text("true"))


def is_mock_column() -> Mapped[bool]:
    return mapped_column(Boolean, server_default=text("true"))


def first_day_of_month(column: str) -> str:
    """월 단위 값은 그 달 1일(KST 기준)로 저장한다."""
    return f"EXTRACT(DAY FROM {column}) = 1"


# ===========================================================================
# 4. 기준정보
# ===========================================================================


class Customer(Base):
    """4.1 고객 (P-01)."""

    __tablename__ = "customers"
    __table_args__ = (
        {"comment": "고객 (P-01). customer_code는 사람이 읽는 고정 코드"},
    )

    customer_id: Mapped[int] = bigint_identity_pk()
    customer_code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = is_active_column()
    is_mock: Mapped[bool] = is_mock_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class Project(Base):
    """4.2 내부 프로젝트 (P-02)."""

    __tablename__ = "projects"
    __table_args__ = (
        in_check("projects", "project_type", ProjectType),
        {
            "comment": "내부 프로젝트 (P-02). CUSTOMER_PROJECT도 내부 비용(해석, 기업 확인 필요)"
        },
    )

    project_id: Mapped[int] = bigint_identity_pk()
    project_code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = is_active_column()
    is_mock: Mapped[bool] = is_mock_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class User(Base):
    """4.3 관리자 계정. 비용 귀속 대상이 아니라 실행자·등록자 기록용. 삭제하지 않고 is_active=false로 비활성화."""

    __tablename__ = "users"
    __table_args__ = (
        {"comment": "Patron 관리자 계정. 비용 귀속 대상이 아니라 실행자·등록자 기록용"},
    )

    user_id: Mapped[int] = bigint_identity_pk()
    user_code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(
        Text, comment="Argon2id 해시(pwdlib[argon2]). 비밀번호 원문은 저장하지 않음"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = is_active_column()
    is_mock: Mapped[bool] = is_mock_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class Service(Base):
    """4.4 호출 서비스."""

    __tablename__ = "services"
    __table_args__ = (
        in_check("services", "service_type", ServiceType),
        {
            "comment": "호출 서비스. service_code는 프로그램용 고정값, name은 화면 표시명"
        },
    )

    service_id: Mapped[int] = bigint_identity_pk()
    service_code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    service_type: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = is_active_column()
    is_mock: Mapped[bool] = is_mock_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class APIKey(Base):
    """4.5 OpenRouter Key 매핑. Key 원문은 저장하지 않고, secret_ref가 가리키는 환경변수에만 있다."""

    __tablename__ = "api_keys"
    __table_args__ = (
        in_check("api_keys", "owner_type", KeyOwnerType),
        in_check("api_keys", "environment", KeyEnvironment),
        in_check("api_keys", "status", KeyStatus),
        column_check("api_keys", "limit_usd", "limit_usd >= 0"),
        in_check("api_keys", "limit_reset_period", LimitResetPeriod),
        # Key는 종류에 맞는 대상(고객 또는 프로젝트) 하나만 가진다.
        CheckConstraint(
            f"(owner_type = '{KeyOwnerType.CUSTOMER}' AND customer_id IS NOT NULL AND project_id IS NULL) OR "
            f"(owner_type = '{KeyOwnerType.PROJECT}' AND project_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_api_keys_owner",
        ),
        {
            "comment": "OpenRouter Key 매핑. 원문은 secret_ref가 가리키는 환경변수에만 있음"
        },
    )

    key_id: Mapped[int] = bigint_identity_pk()
    display_name: Mapped[str] = mapped_column(Text)
    secret_ref: Mapped[str | None] = mapped_column(
        Text, comment="Key 원문이 든 환경변수 이름. Mock Key는 NULL"
    )
    key_fingerprint: Mapped[str | None] = mapped_column(
        Text, comment="OpenRouter Key 식별자의 HMAC-SHA256. hash/label 원문 저장 금지"
    )
    workspace_ref: Mapped[str | None] = mapped_column(Text)
    owner_type: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("customers.customer_id")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("projects.project_id")
    )
    environment: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=KeyStatus.ACTIVE.value)
    limit_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    limit_reset_period: Mapped[str] = mapped_column(
        Text, server_default=LimitResetPeriod.NONE.value
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_mock: Mapped[bool] = is_mock_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class UserSession(Base):
    """4.6 로그인 세션 (v0.5). 토큰 원문은 저장하지 않고 SHA-256 해시만 둔다.

    로그아웃·비활성화·비밀번호 변경 때와 만료 정리 때 행을 지운다(이 테이블만 삭제 허용).
    유효한 세션 = token_hash 일치 + expires_at > now() + users.is_active = true
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        column_check("user_sessions", "token_hash", "token_hash ~ '^[0-9a-f]{64}$'"),
        CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        Index("ix_user_sessions_user", "user_id"),
        Index("ix_user_sessions_expires", "expires_at"),
        {
            "comment": "로그인 세션. 토큰 원문은 저장하지 않고 SHA-256 해시만 저장. 로그아웃·비활성화 시 행 삭제"
        },
    )

    session_id: Mapped[int] = bigint_identity_pk()
    user_id: Mapped[int] = mapped_column(BigInteger, fk("users.user_id"))
    token_hash: Mapped[str] = mapped_column(
        CHAR(SHA256_HEX_LENGTH),
        unique=True,
        comment="SHA-256(세션 토큰) 소문자 16진수 64자. 토큰 원문 저장 금지",
    )
    created_at: Mapped[datetime] = created_at_column()
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        comment="발급 시각 + 12시간. 쿠키 수명과 같은 상수에서 계산",
    )


# ===========================================================================
# 5. 모델
# ===========================================================================


class ModelRegistry(Base):
    """5.1 등록 모델 (P-03). 클래스 이름은 SQLAlchemy·Pydantic의 '모델'과 헷갈리지 않게 ModelRegistry로 둔다."""

    __tablename__ = "models"
    __table_args__ = (
        in_check("models", "status", ModelStatus),
        column_check("models", "context_length", "context_length > 0"),
        in_check("models", "last_test_status", ConnectionTestStatus),
        {
            "comment": "등록 모델 (P-03). provider는 모델 제작사. 연결 테스트 이력은 SYSTEM_TEST 호출"
        },
    )

    model_id: Mapped[int] = bigint_identity_pk()
    openrouter_model_id: Mapped[str] = mapped_column(Text, unique=True)
    provider: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=ModelStatus.TESTING.value)
    input_modalities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )
    output_modalities: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )
    supported_parameters: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )
    context_length: Mapped[int | None] = mapped_column(Integer)
    openrouter_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_test_status: Mapped[str | None] = mapped_column(Text)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # models ↔ ai_requests 순환 참조라 테이블을 모두 만든 뒤 외래키를 따로 추가한다(use_alter).
    last_test_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        fk(
            "ai_requests.request_id", use_alter=True, name="fk_models_last_test_request"
        ),
    )
    last_success_test_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class ModelPrice(Base):
    """5.2 가격 기준정보 이력. 수정하지 않고 새 행을 추가한다. execution_provider NULL = 모델 대표가."""

    __tablename__ = "model_prices"
    __table_args__ = (
        in_check("model_prices", "price_status", PriceStatus),
        column_check(
            "model_prices", "input_price_per_token", "input_price_per_token >= 0"
        ),
        column_check(
            "model_prices", "output_price_per_token", "output_price_per_token >= 0"
        ),
        column_check(
            "model_prices",
            "cache_read_price_per_token",
            "cache_read_price_per_token >= 0",
        ),
        column_check(
            "model_prices",
            "cache_write_price_per_token",
            "cache_write_price_per_token >= 0",
        ),
        in_check("model_prices", "source", PriceSource),
        # 가격을 안다(KNOWN)면 입력·출력 단가가 모두 있어야 한다.
        CheckConstraint(
            f"price_status <> '{PriceStatus.KNOWN}' OR "
            "(input_price_per_token IS NOT NULL AND output_price_per_token IS NOT NULL)",
            name="ck_model_prices_known",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_model_prices_period",
        ),
        # 같은 모델·실행 Provider의 "현재 유효" 가격은 1개 (NULL 실행 Provider도 중복 취급)
        Index(
            "uq_model_prices_current",
            "model_id",
            "execution_provider",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("effective_to IS NULL"),
        ),
        {
            "comment": "가격 기준정보 이력. 수정하지 않고 새 행 추가. execution_provider NULL = 모델 대표가"
        },
    )

    price_id: Mapped[int] = bigint_identity_pk()
    model_id: Mapped[int] = mapped_column(BigInteger, fk("models.model_id"))
    execution_provider: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(
        CHAR(CURRENCY_CODE_LENGTH), server_default="USD"
    )
    price_status: Mapped[str] = mapped_column(Text)
    input_price_per_token: Mapped[Decimal | None] = mapped_column(MONEY)
    output_price_per_token: Mapped[Decimal | None] = mapped_column(MONEY)
    cache_read_price_per_token: Mapped[Decimal | None] = mapped_column(MONEY)
    cache_write_price_per_token: Mapped[Decimal | None] = mapped_column(MONEY)
    raw_pricing: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()


# ===========================================================================
# 6~7. 호출 이력과 시뮬레이션
# ===========================================================================


class Task(Base):
    """6.1 업무 작업. 작업 건수 = COUNT(DISTINCT task_id)."""

    __tablename__ = "tasks"
    __table_args__ = (
        in_check("tasks", "usage_origin", UsageOrigin),
        in_check("tasks", "data_source", DataSource),
        CheckConstraint(
            "num_nonnulls(customer_id, project_id) <= 1", name="ck_tasks_single_owner"
        ),
        # 고객 작업에는 프로젝트를, 그 밖의 작업에는 고객을 붙이지 않는다.
        CheckConstraint(
            f"(usage_origin = '{UsageOrigin.CUSTOMER_SERVICE}' AND project_id IS NULL) OR "
            f"(usage_origin <> '{UsageOrigin.CUSTOMER_SERVICE}' AND customer_id IS NULL)",
            name="ck_tasks_origin_owner",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_tasks_period",
        ),
        # 같은 서비스에서 같은 작업 번호가 두 번 들어와도 작업 건수가 중복되지 않게 함 (NULL은 영향 없음)
        UniqueConstraint(
            "service_id", "external_task_ref", name="uq_tasks_service_ref"
        ),
        {
            "comment": "업무 작업. external_task_ref는 호출한 서비스 쪽 작업 번호(참고값)"
        },
    )

    task_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    external_task_ref: Mapped[str | None] = mapped_column(Text)
    usage_origin: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("customers.customer_id")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("projects.project_id")
    )
    service_id: Mapped[int] = mapped_column(BigInteger, fk("services.service_id"))
    task_type: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class TestScenario(Base):
    """7.1 시나리오 템플릿(레시피). 실행 당시 값은 simulation_runs에 복사 저장한다."""

    __tablename__ = "test_scenarios"
    __table_args__ = (
        in_check("test_scenarios", "input_type", InputType),
        {
            "comment": "시나리오 템플릿(레시피). 실행 당시 값은 simulation_runs에 복사 저장"
        },
    )

    scenario_id: Mapped[int] = bigint_identity_pk()
    scenario_code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    input_type: Mapped[str] = mapped_column(Text)
    prompt_template: Mapped[str] = mapped_column(Text)
    default_json_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    default_execution_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'")
    )
    is_active: Mapped[bool] = is_active_column()
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class SimulationRun(Base):
    """7.2 비교 실행 1회. 성공 수·비용 합계는 저장하지 않고 v_simulation_summary에서 계산한다. 재실행은 새 ID로 만든다."""

    __tablename__ = "simulation_runs"
    __table_args__ = (
        in_check("simulation_runs", "test_type", TestType),
        column_check("simulation_runs", "model_count", "model_count BETWEEN 2 AND 4"),
        in_check("simulation_runs", "status", SimulationStatus),
        in_check("simulation_runs", "data_source", DataSource),
        # 시나리오 실행에만 시나리오를 붙인다.
        CheckConstraint(
            f"(test_type = '{TestType.SCENARIO}' AND scenario_id IS NOT NULL) OR "
            f"(test_type = '{TestType.CUSTOM}' AND scenario_id IS NULL)",
            name="ck_simulation_runs_scenario",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_simulation_runs_period",
        ),
        CheckConstraint(
            "rerun_of_simulation_id IS DISTINCT FROM simulation_id",
            name="ck_simulation_runs_not_self",
        ),
        {
            "comment": "비교 실행 1회. 성공 수·비용 합계는 저장하지 않고 v_simulation_summary에서 계산"
        },
    )

    simulation_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    rerun_of_simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, fk("simulation_runs.simulation_id")
    )
    test_type: Mapped[str] = mapped_column(Text)
    scenario_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("test_scenarios.scenario_id")
    )
    prompt_text: Mapped[str] = mapped_column(Text)
    input_text: Mapped[str | None] = mapped_column(Text)
    json_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    execution_config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    routing_policy: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_hash: Mapped[str] = mapped_column(CHAR(SHA256_HEX_LENGTH))
    model_count: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(
        Text, server_default=SimulationStatus.PENDING.value
    )
    project_id: Mapped[int] = mapped_column(BigInteger, fk("projects.project_id"))
    key_id: Mapped[int] = mapped_column(BigInteger, fk("api_keys.key_id"))
    executed_by: Mapped[int] = mapped_column(BigInteger, fk("users.user_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


# owner_type 자동 계산식: 고객 호출 → CUSTOMER, 내부 개발 → INTERNAL, 시뮬레이션·연결 테스트 → POC
OWNER_TYPE_EXPRESSION = (
    "CASE usage_origin "
    f"WHEN '{UsageOrigin.CUSTOMER_SERVICE}' THEN '{RequestOwnerType.CUSTOMER}' "
    f"WHEN '{UsageOrigin.INTERNAL_DEVELOPMENT}' THEN '{RequestOwnerType.INTERNAL}' "
    f"ELSE '{RequestOwnerType.POC}' "
    "END"
)
# 실행자(executed_by)를 기록하는 출처: 시뮬레이션·연결 테스트
EXECUTOR_ORIGINS = f"'{UsageOrigin.SIMULATION}', '{UsageOrigin.SYSTEM_TEST}'"


class AIRequest(Base):
    """6.2 AI 호출 이력. 호출 1회 = 1행. 모든 사용량·비용 집계의 기준 데이터(Source of Truth).

    생성·상태·비용 변경은 services/requests.py만 한다. 종료된 호출의 비용은 대조(reconcile)로만 갱신한다.
    """

    __tablename__ = "ai_requests"
    __table_args__ = (
        in_check("ai_requests", "usage_origin", UsageOrigin),
        in_check("ai_requests", "call_purpose", CallPurpose),
        column_check("ai_requests", "attempt_no", "attempt_no >= 1"),
        in_check("ai_requests", "status", RequestStatus),
        in_check("ai_requests", "error_type", ErrorType),
        column_check("ai_requests", "latency_ms", "latency_ms >= 0"),
        column_check("ai_requests", "input_tokens", "input_tokens >= 0"),
        column_check("ai_requests", "output_tokens", "output_tokens >= 0"),
        column_check("ai_requests", "cached_tokens", "cached_tokens >= 0"),
        column_check("ai_requests", "cache_write_tokens", "cache_write_tokens >= 0"),
        column_check("ai_requests", "reasoning_tokens", "reasoning_tokens >= 0"),
        column_check("ai_requests", "cost_usd", "cost_usd >= 0"),
        in_check("ai_requests", "cost_status", CostStatus),
        in_check("ai_requests", "cost_source", CostSource),
        in_check("ai_requests", "data_source", DataSource),
        # 설계서 6.2 "DB가 직접 강제하는 규칙"
        # 1) 귀속 대상은 최대 1개
        CheckConstraint(
            "num_nonnulls(customer_id, project_id) <= 1",
            name="ck_ai_requests_single_owner",
        ),
        # 2) 출처와 귀속 일치 (T-02). 내부 호출은 프로젝트 필수, 고객 호출은 고객 미상(미분류) 허용
        CheckConstraint(
            f"(usage_origin = '{UsageOrigin.CUSTOMER_SERVICE}' AND project_id IS NULL) OR "
            f"(usage_origin <> '{UsageOrigin.CUSTOMER_SERVICE}' AND customer_id IS NULL "
            "AND project_id IS NOT NULL)",
            name="ck_ai_requests_origin_owner",
        ),
        # 3) 시뮬레이션 호출은 실행 ID 필수
        CheckConstraint(
            f"usage_origin <> '{UsageOrigin.SIMULATION}' OR simulation_id IS NOT NULL",
            name="ck_ai_requests_simulation",
        ),
        # 4) 재시도 관계 (T-11)
        CheckConstraint(
            "(attempt_no = 1 AND parent_request_id IS NULL) OR "
            "(attempt_no > 1 AND parent_request_id IS NOT NULL)",
            name="ck_ai_requests_retry",
        ),
        # 5) 비용 미확인 ≠ 0 (T-08, T-09)
        CheckConstraint(
            f"(cost_status = '{CostStatus.UNKNOWN}' AND cost_usd IS NULL) OR "
            f"(cost_status <> '{CostStatus.UNKNOWN}' AND cost_usd IS NOT NULL)",
            name="ck_ai_requests_cost_unknown",
        ),
        # 6) 추정 비용은 가격 근거 필요
        CheckConstraint(
            f"cost_status <> '{CostStatus.ESTIMATED}' OR price_id IS NOT NULL",
            name="ck_ai_requests_cost_estimated",
        ),
        # 청구 없음으로 확정한 근거는 실패 호출의 확정 0원에만 쓴다.
        CheckConstraint(
            f"cost_source <> '{CostSource.NO_CHARGE}' OR "
            f"(cost_status = '{CostStatus.CONFIRMED}' AND cost_usd = 0 "
            f"AND status = '{RequestStatus.FAILED}')",
            name="ck_ai_requests_no_charge",
        ),
        # 7) 오류 정합성
        CheckConstraint(
            f"(status = '{RequestStatus.SUCCESS}' AND error_type IS NULL) OR "
            f"(status IN ('{RequestStatus.FAILED}', '{RequestStatus.TIMEOUT}') AND error_type IS NOT NULL) OR "
            f"(status IN ('{RequestStatus.PENDING}', '{RequestStatus.RUNNING}', '{RequestStatus.CANCELLED}'))",
            name="ck_ai_requests_error",
        ),
        # 8) 실행자 기록 (v0.4): 시뮬레이션·연결 테스트만 실행자를 기록
        CheckConstraint(
            f"(usage_origin IN ({EXECUTOR_ORIGINS}) AND executed_by IS NOT NULL) OR "
            f"(usage_origin NOT IN ({EXECUTOR_ORIGINS}) AND executed_by IS NULL)",
            name="ck_ai_requests_executed_by",
        ),
        # 기본 검증: 시간 순서
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_ai_requests_period",
        ),
        # 기본 검증: 세부 Token은 상위 Token에 포함
        CheckConstraint(
            "(cached_tokens IS NULL OR input_tokens IS NULL OR cached_tokens <= input_tokens) AND "
            "(reasoning_tokens IS NULL OR output_tokens IS NULL OR reasoning_tokens <= output_tokens)",
            name="ck_ai_requests_token_breakdown",
        ),
        # simulation_results 복합 외래키의 대상
        UniqueConstraint("simulation_id", "request_id", name="uq_ai_requests_sim_req"),
        Index("ix_ai_requests_origin_time", "usage_origin", "requested_at"),
        Index("ix_ai_requests_customer_time", "customer_id", "requested_at"),
        Index("ix_ai_requests_project_time", "project_id", "requested_at"),
        Index("ix_ai_requests_model", "model_id"),
        Index("ix_ai_requests_task", "task_id"),
        Index("ix_ai_requests_parent", "parent_request_id"),
        Index(
            "ix_ai_requests_cost_unknown",
            "requested_at",
            postgresql_where=text(f"cost_status = '{CostStatus.UNKNOWN}'"),
        ),
        Index(
            "ix_ai_requests_open",
            "requested_at",
            postgresql_where=text(
                f"status IN ('{RequestStatus.PENDING}', '{RequestStatus.RUNNING}')"
            ),
        ),
        {
            "comment": "AI 호출 이력. 호출 1회 = 1행. 모든 사용량·비용 집계의 기준 데이터(Source of Truth)"
        },
    )

    # A. 요청 식별 및 귀속
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    usage_origin: Mapped[str] = mapped_column(Text)
    owner_type: Mapped[str] = mapped_column(
        Text,
        Computed(OWNER_TYPE_EXPRESSION, persisted=True),
        comment="usage_origin에서 자동 계산 (직접 입력 불가)",
    )
    key_id: Mapped[int] = mapped_column(BigInteger, fk("api_keys.key_id"))
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("customers.customer_id")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("projects.project_id")
    )
    executed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        fk("users.user_id"),
        comment="시뮬레이션·연결 테스트를 실행한 관리자. 비용 귀속에는 쓰지 않음 (v0.4)",
    )
    service_id: Mapped[int] = mapped_column(BigInteger, fk("services.service_id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, fk("tasks.task_id"))
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, fk("simulation_runs.simulation_id")
    )
    call_purpose: Mapped[str] = mapped_column(Text)
    attempt_no: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    parent_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, fk("ai_requests.request_id")
    )

    # B. 모델 및 실행 조건
    model_id: Mapped[int | None] = mapped_column(BigInteger, fk("models.model_id"))
    requested_model: Mapped[str] = mapped_column(Text)
    requested_provider: Mapped[str | None] = mapped_column(Text)
    actual_model: Mapped[str | None] = mapped_column(Text)
    actual_provider: Mapped[str | None] = mapped_column(Text)
    routing_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'")
    )
    execution_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'")
    )
    input_reference: Mapped[str | None] = mapped_column(Text)
    input_hash: Mapped[str | None] = mapped_column(CHAR(SHA256_HEX_LENGTH))

    # C. 실행 결과
    status: Mapped[str] = mapped_column(
        Text, server_default=RequestStatus.PENDING.value
    )
    error_type: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    finish_reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    external_generation_id: Mapped[str | None] = mapped_column(Text, unique=True)

    # D. Token 및 비용
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_tokens: Mapped[int | None] = mapped_column(
        Integer, comment="input_tokens에 포함된 값. 합계 시 더하지 않음"
    )
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(
        Integer, comment="output_tokens에 포함된 값. 합계 시 더하지 않음"
    )
    usage_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        MONEY, comment="비용 미확인이면 NULL (0이 아님)"
    )
    cost_status: Mapped[str] = mapped_column(
        Text, server_default=CostStatus.UNKNOWN.value
    )
    cost_source: Mapped[str | None] = mapped_column(Text)
    price_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("model_prices.price_id")
    )
    cost_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class AIRequestPayload(Base):
    """6.3 호출 원문 (호출과 1:1). 이미지는 base64 대신 asset_id로 가리킨다."""

    __tablename__ = "ai_request_payloads"
    __table_args__ = ({"comment": "호출 원문. 이미지는 base64 대신 asset_id로 가리킴"},)

    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, fk("ai_requests.request_id"), primary_key=True
    )
    request_messages: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response_text: Mapped[str | None] = mapped_column(Text)
    response_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()


class InputAsset(Base):
    """6.4 시뮬레이터 이미지 입력 참조. 파일은 서버에 보관하고 DB에는 경로·해시만 둔다(설계 v0.6)."""

    __tablename__ = "input_assets"
    __table_args__ = (
        column_check("input_assets", "file_size_bytes", "file_size_bytes >= 0"),
        {
            "comment": "시뮬레이터 이미지 입력 참조. 파일은 서버에 보관, DB에는 경로·해시만"
        },
    )

    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    storage_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(CHAR(SHA256_HEX_LENGTH))
    mime_type: Mapped[str] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_filename: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    created_at: Mapped[datetime] = created_at_column()


class CostAdjustment(Base):
    """6.5 호출 비용 정정 이력. adjusted_by_user_id NULL = 시스템 정산."""

    __tablename__ = "cost_adjustments"
    __table_args__ = (
        in_check("cost_adjustments", "old_cost_status", CostStatus),
        in_check("cost_adjustments", "new_cost_status", CostStatus),
        Index("ix_cost_adjustments_request", "request_id"),
        {"comment": "호출 비용 정정 이력. adjusted_by_user_id NULL = 시스템 정산"},
    )

    adjustment_id: Mapped[int] = bigint_identity_pk()
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, fk("ai_requests.request_id"))
    old_cost_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    new_cost_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    old_cost_status: Mapped[str] = mapped_column(Text)
    new_cost_status: Mapped[str] = mapped_column(Text)
    old_cost_source: Mapped[str | None] = mapped_column(Text)
    new_cost_source: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    adjusted_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("users.user_id")
    )
    adjusted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SimulationRunAsset(Base):
    """7.3 실행과 이미지 연결."""

    __tablename__ = "simulation_run_assets"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, fk("simulation_runs.simulation_id"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, fk("input_assets.asset_id"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(SmallInteger)


class SimulationResult(Base):
    """7.4 모델별 결과·검증. 한 칸(slot)에는 최종 결과가 하나이고, 이전 시도는 is_final_attempt=false로 남는다."""

    __tablename__ = "simulation_results"
    __table_args__ = (
        column_check("simulation_results", "slot_no", "slot_no BETWEEN 1 AND 4"),
        in_check("simulation_results", "model_status_at_run", ModelStatus),
        in_check("simulation_results", "json_parse_status", ValidationStatus),
        in_check("simulation_results", "schema_validation_status", ValidationStatus),
        # 다른 시뮬레이션의 호출을 결과로 연결하지 못하게 강제
        ForeignKeyConstraint(
            ["simulation_id", "request_id"],
            ["ai_requests.simulation_id", "ai_requests.request_id"],
            name="fk_simulation_results_request",
            ondelete=RESTRICT,
        ),
        Index(
            "uq_sim_results_slot",
            "simulation_id",
            "slot_no",
            unique=True,
            postgresql_where=text("is_final_attempt"),
        ),
        # 같은 모델은 실행 Provider가 다를 때만 한 실행에 두 번 넣을 수 있음
        Index(
            "uq_sim_results_model_provider",
            "simulation_id",
            "model_id",
            "execution_provider",
            unique=True,
            postgresql_where=text("is_final_attempt"),
        ),
    )

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, fk("simulation_runs.simulation_id"), primary_key=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, unique=True)
    slot_no: Mapped[int] = mapped_column(SmallInteger)
    model_id: Mapped[int] = mapped_column(BigInteger, fk("models.model_id"))
    # 이 칸에서 고정한 실행 Provider (자동 라우팅 없음)
    execution_provider: Mapped[str] = mapped_column(Text)
    model_status_at_run: Mapped[str] = mapped_column(Text)
    model_display_name_at_run: Mapped[str] = mapped_column(Text)
    is_final_attempt: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    json_parse_status: Mapped[str | None] = mapped_column(Text)
    schema_validation_status: Mapped[str | None] = mapped_column(Text)
    missing_required_fields: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    validation_errors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    comparability_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


# ===========================================================================
# 8. 예산·구독료
# ===========================================================================


class Budget(Base):
    """8.1 월 예산(고객·프로젝트). 한 번 등록하면 다음 달에도 유지된다.

    사용률·상태는 저장하지 않고 백엔드 공통 집계 코드에서 계산한다(v0.6). 예산이 없으면 0%가 아니라 미설정.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        in_check("budgets", "scope_type", BudgetScopeType),
        column_check("budgets", "monthly_amount_usd", "monthly_amount_usd > 0"),
        column_check(
            "budgets",
            "warning_threshold_pct",
            "warning_threshold_pct BETWEEN 0 AND 100",
        ),
        column_check(
            "budgets",
            "effective_from_month",
            first_day_of_month("effective_from_month"),
        ),
        column_check(
            "budgets",
            "effective_to_month",
            f"effective_to_month IS NULL OR {first_day_of_month('effective_to_month')}",
        ),
        CheckConstraint(
            f"(scope_type = '{BudgetScopeType.CUSTOMER}' AND customer_id IS NOT NULL AND project_id IS NULL) OR "
            f"(scope_type = '{BudgetScopeType.PROJECT}' AND project_id IS NOT NULL AND customer_id IS NULL)",
            name="ck_budgets_scope",
        ),
        CheckConstraint(
            "effective_to_month IS NULL OR effective_to_month >= effective_from_month",
            name="ck_budgets_period",
        ),
        # 같은 대상의 적용 기간 겹침 금지 (종료 월 포함, 종료 NULL = 무기한). btree_gist 확장이 필요하다.
        ExcludeConstraint(
            ("scope_type", "="),
            (text("COALESCE(customer_id, -1)"), "="),
            (text("COALESCE(project_id, -1)"), "="),
            (text("daterange(effective_from_month, effective_to_month, '[]')"), "&&"),
            name="ex_budgets_no_overlap",
            using="gist",
        ),
        {
            "comment": "월 예산(고객·프로젝트). 사용률·상태는 저장하지 않고 백엔드 공통 집계 코드에서 계산(v0.6). 예산이 없으면 0%가 아니라 미설정"
        },
    )

    budget_id: Mapped[int] = bigint_identity_pk()
    scope_type: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("customers.customer_id")
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("projects.project_id")
    )
    monthly_amount_usd: Mapped[Decimal] = mapped_column(MONEY)
    warning_threshold_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    effective_from_month: Mapped[date] = mapped_column(Date)
    effective_to_month: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class SubscriptionCost(Base):
    """8.2 월 구독료. API 비용과 따로 집계한다. 결제 후 실제 청구액을 USD로 입력(원화 원금은 note)."""

    __tablename__ = "subscription_costs"
    __table_args__ = (
        column_check(
            "subscription_costs", "applied_month", first_day_of_month("applied_month")
        ),
        column_check("subscription_costs", "amount", "amount >= 0"),
        # v0.4: USD 고정
        column_check("subscription_costs", "currency", "currency = 'USD'"),
        in_check("subscription_costs", "status", SubscriptionStatus),
        UniqueConstraint(
            "subscription_reference",
            "applied_month",
            name="uq_subscription_costs_ref_month",
        ),
        {
            "comment": "월 구독료. 결제 후 실제 청구액을 USD로 입력(원화 원금은 note). project_id NULL = 미배분"
        },
    )

    subscription_id: Mapped[int] = bigint_identity_pk()
    subscription_reference: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(Text)
    subscription_type: Mapped[str | None] = mapped_column(Text)
    applied_month: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    currency: Mapped[str] = mapped_column(
        CHAR(CURRENCY_CODE_LENGTH), server_default="USD"
    )
    project_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("projects.project_id")
    )
    status: Mapped[str] = mapped_column(
        Text, server_default=SubscriptionStatus.ACTIVE.value
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


# ===========================================================================
# 9. 대조·감사
# ===========================================================================


class KeyUsageSnapshot(Base):
    """9.1 OpenRouter Key 사용량 스냅샷(GET /key 응답). Key 일부가 담긴 필드(label, hash 등)는 제거 후 저장."""

    __tablename__ = "key_usage_snapshots"
    __table_args__ = (
        Index("ix_key_usage_snapshots_key_time", "key_id", "captured_at"),
        {
            "comment": "GET /key 응답 스냅샷. label, hash 등 Key 일부가 담긴 필드는 제거 후 저장"
        },
    )

    snapshot_id: Mapped[int] = bigint_identity_pk()
    key_id: Mapped[int] = mapped_column(BigInteger, fk("api_keys.key_id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usage_total_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    usage_daily_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    usage_weekly_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    usage_monthly_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    limit_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    limit_remaining_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class UsageReconciliation(Base):
    """9.2 OpenRouter 사용량과 Patron 기록의 대조 결과 (T-27). 차액은 개별 호출에 배분하지 않는다."""

    __tablename__ = "usage_reconciliations"
    __table_args__ = (
        column_check(
            "usage_reconciliations", "patron_unknown_count", "patron_unknown_count >= 0"
        ),
        in_check("usage_reconciliations", "comparability", Comparability),
        in_check("usage_reconciliations", "status", ReconciliationStatus),
        CheckConstraint(
            "period_end > period_start", name="ck_usage_reconciliations_period"
        ),
        # 비교 가능할 때만 외부 사용량과 차액이 있다.
        CheckConstraint(
            f"(comparability = '{Comparability.COMPARABLE}' "
            "AND external_usage_usd IS NOT NULL AND difference_usd IS NOT NULL) OR "
            f"(comparability = '{Comparability.UNCOMPARABLE}' "
            "AND external_usage_usd IS NULL AND difference_usd IS NULL)",
            name="ck_usage_reconciliations_comparable",
        ),
        {
            "comment": "OpenRouter 사용량과 Patron 기록의 대조. 차액은 개별 호출에 배분하지 않음"
        },
    )

    reconciliation_id: Mapped[int] = bigint_identity_pk()
    key_id: Mapped[int] = mapped_column(BigInteger, fk("api_keys.key_id"))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    start_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("key_usage_snapshots.snapshot_id")
    )
    end_snapshot_id: Mapped[int | None] = mapped_column(
        BigInteger, fk("key_usage_snapshots.snapshot_id")
    )
    external_usage_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    patron_confirmed_usd: Mapped[Decimal] = mapped_column(MONEY)
    patron_estimated_usd: Mapped[Decimal] = mapped_column(MONEY)
    patron_unknown_count: Mapped[int] = mapped_column(Integer)
    difference_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    comparability: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, server_default=ReconciliationStatus.OPEN.value
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class ChangeLog(Base):
    """9.3 변경 이력 (공통). 대상이 여러 테이블이라 외래키가 없다."""

    __tablename__ = "change_logs"
    __table_args__ = (
        in_check("change_logs", "action", ChangeAction),
        Index("ix_change_logs_entity", "entity_type", "entity_id", "changed_at"),
        {
            "comment": "Key 매핑·모델 상태·예산·구독료·호출 귀속 수정 등 변경 이력. 대상이 여러 테이블이라 FK 없음"
        },
    )

    log_id: Mapped[int] = bigint_identity_pk()
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[int | None] = mapped_column(BigInteger, fk("users.user_id"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
