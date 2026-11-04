"""모델·Provider별 즐겨찾기와 적용 설정에 따른 비교 중복 제약.

해시는 DB가 생성한다. 기존 백엔드는 새 필드를 보내지 않고도 저장할 수 있다.
함수·트리거·CHECK와 기존 데이터의 해시 채우기는 autogenerate 초안에 보완했다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "264258125f67"
down_revision: str | Sequence[str] | None = "7b2e4f6a9c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_hash_functions() -> None:
    # jsonb는 키 순서는 정규화하지만 숫자의 소수 자릿수는 보존한다. 재귀적으로
    # trim_scale을 적용해야 1과 1.0, 중첩된 숫자까지 같은 해시가 된다. 원문은 바꾸지 않는다.
    op.execute(
        """
        CREATE FUNCTION public.simulation_execution_config_normalize(config jsonb)
        RETURNS jsonb LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE
        SET search_path = pg_catalog AS $normalize$
        BEGIN
            CASE jsonb_typeof(config)
            WHEN 'object' THEN
                RETURN (SELECT coalesce(jsonb_object_agg(key,
                    public.simulation_execution_config_normalize(value)), '{}'::jsonb)
                    FROM jsonb_each(config));
            WHEN 'array' THEN
                RETURN (SELECT coalesce(jsonb_agg(
                    public.simulation_execution_config_normalize(value)
                    ORDER BY position), '[]'::jsonb)
                    FROM jsonb_array_elements(config) WITH ORDINALITY AS items(value, position));
            WHEN 'number' THEN
                RETURN to_jsonb(trim_scale((config #>> '{}')::numeric));
            ELSE
                RETURN config;
            END CASE;
        END;
        $normalize$;
        """
    )
    # PostgreSQL 내장 sha256을 쓰므로 새 extension이 필요하지 않다.
    op.execute(
        """
        CREATE FUNCTION public.simulation_execution_config_hash(config jsonb)
        RETURNS text LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
        SET search_path = pg_catalog AS $hash$
            SELECT encode(sha256(convert_to(
                public.simulation_execution_config_normalize(config)::text, 'UTF8')), 'hex');
        $hash$;
        """
    )


def _create_result_hash_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION public.set_simulation_result_config_hash()
        RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $trigger$
        BEGIN
            SELECT request.execution_config_hash INTO NEW.execution_config_hash
            FROM public.ai_requests AS request
            WHERE request.simulation_id = NEW.simulation_id
              AND request.request_id = NEW.request_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION USING ERRCODE = '23503',
                    MESSAGE = 'Simulation result must reference a request in the same simulation.',
                    CONSTRAINT = 'fk_simulation_results_request';
            END IF;
            RETURN NEW;
        END;
        $trigger$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_simulation_results_config_hash
        BEFORE INSERT OR UPDATE OF simulation_id, request_id, execution_config_hash
        ON simulation_results FOR EACH ROW
        EXECUTE FUNCTION public.set_simulation_result_config_hash();
        """
    )


def upgrade() -> None:
    """이력과 설정 원문은 보존하고 해시만 채운 뒤 새 중복 제약으로 교체한다."""
    op.execute(
        "LOCK TABLE simulation_runs, ai_requests, simulation_results IN ACCESS EXCLUSIVE MODE"
    )
    for table in ("simulation_runs", "ai_requests"):
        op.create_check_constraint(
            f"ck_{table}_execution_config_object",
            table,
            "jsonb_typeof(execution_config) = 'object'",
        )
    _create_hash_functions()
    op.add_column(
        "ai_requests",
        sa.Column(
            "execution_config_hash",
            sa.CHAR(64),
            sa.Computed(
                "simulation_execution_config_hash(execution_config)", persisted=True
            ),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_ai_requests_sim_req_config",
        "ai_requests",
        ["simulation_id", "request_id", "execution_config_hash"],
    )
    op.add_column(
        "simulation_results",
        sa.Column("execution_config_hash", sa.CHAR(64), nullable=True),
    )
    op.execute(
        """
        UPDATE simulation_results AS result
        SET execution_config_hash = request.execution_config_hash
        FROM ai_requests AS request
        WHERE result.simulation_id = request.simulation_id
          AND result.request_id = request.request_id;
        """
    )
    op.alter_column("simulation_results", "execution_config_hash", nullable=False)
    op.create_foreign_key(
        "fk_simulation_results_request_config",
        "simulation_results",
        "ai_requests",
        ["simulation_id", "request_id", "execution_config_hash"],
        ["simulation_id", "request_id", "execution_config_hash"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )
    _create_result_hash_trigger()
    op.create_index(
        "uq_sim_results_model_provider_config",
        "simulation_results",
        ["simulation_id", "model_id", "execution_provider", "execution_config_hash"],
        unique=True,
        postgresql_where=sa.text("is_final_attempt"),
    )
    op.drop_index("uq_sim_results_model_provider", table_name="simulation_results")
    op.create_table(
        "user_model_favorites",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=False),
        sa.Column("execution_provider", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "execution_provider <> '' AND execution_provider = btrim(execution_provider)",
            name="ck_user_model_favorites_provider",
        ),
        sa.ForeignKeyConstraint(["model_id"], ["models.model_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", "model_id", "execution_provider"),
    )


def downgrade() -> None:
    """저장된 이력이 있으면 중단한다. 새 테이블·컬럼이 비어 있을 때만 되돌린다."""
    op.execute(
        "LOCK TABLE simulation_runs, ai_requests, simulation_results, "
        "user_model_favorites IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        """
        DO $history_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM ai_requests)
                OR EXISTS (SELECT 1 FROM simulation_results)
                OR EXISTS (SELECT 1 FROM user_model_favorites) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: simulator settings history or favorites exist.',
                    HINT = 'Keep this revision; do not delete or rewrite saved history to downgrade.';
            END IF;
        END;
        $history_guard$;
        """
    )
    op.drop_table("user_model_favorites")
    op.drop_index(
        "uq_sim_results_model_provider_config", table_name="simulation_results"
    )
    op.create_index(
        "uq_sim_results_model_provider",
        "simulation_results",
        ["simulation_id", "model_id", "execution_provider"],
        unique=True,
        postgresql_where=sa.text("is_final_attempt"),
    )
    op.execute("DROP TRIGGER trg_simulation_results_config_hash ON simulation_results")
    op.execute("DROP FUNCTION public.set_simulation_result_config_hash()")
    op.drop_constraint(
        "fk_simulation_results_request_config", "simulation_results", type_="foreignkey"
    )
    op.drop_column("simulation_results", "execution_config_hash")
    op.drop_constraint("uq_ai_requests_sim_req_config", "ai_requests", type_="unique")
    op.drop_column("ai_requests", "execution_config_hash")
    op.execute("DROP FUNCTION public.simulation_execution_config_hash(jsonb)")
    op.execute("DROP FUNCTION public.simulation_execution_config_normalize(jsonb)")
    for table in ("ai_requests", "simulation_runs"):
        op.drop_constraint(f"ck_{table}_execution_config_object", table, type_="check")
