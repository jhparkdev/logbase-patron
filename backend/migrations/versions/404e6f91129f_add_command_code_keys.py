"""구성원별 Command Code Key 매핑 command_code_keys 테이블 추가

Key 원문은 저장하지 않고 참조 이름만 둔다. 기존 테이블은 바꾸지 않는다.
autogenerate가 다루지 않는 updated_at 트리거는 직접 추가했다.

리비전 ID: 404e6f91129f
이전 리비전: a4d8e2c61f37
생성 시각: 2026-11-02 20:01:21.152995

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Alembic이 사용하는 리비전 식별 정보.
revision: str = "404e6f91129f"
down_revision: str | Sequence[str] | None = "a4d8e2c61f37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "command_code_keys",
        sa.Column(
            "command_code_key_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("member_name", sa.Text(), nullable=False),
        sa.Column(
            "secret_ref",
            sa.Text(),
            nullable=False,
            comment="Key 원문을 찾는 참조 이름. 원문 저장 금지",
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
            "member_name <> '' AND member_name = btrim(member_name)",
            name="command_code_keys_member_name_check",
        ),
        sa.CheckConstraint(
            "secret_ref ~ '^COMMAND_CODE_KEY_[A-Z0-9_]+$'",
            name="command_code_keys_secret_ref_check",
        ),
        sa.PrimaryKeyConstraint(
            "command_code_key_id", name=op.f("command_code_keys_pkey")
        ),
        sa.UniqueConstraint(
            "secret_ref", name=op.f("command_code_keys_secret_ref_key")
        ),
        comment="구성원별 Command Code Key 매핑. 원문은 저장하지 않고 참조 이름만 저장",
    )
    op.create_index(
        "uq_command_code_keys_active_member",
        "command_code_keys",
        ["member_name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.execute(
        "CREATE TRIGGER trg_command_code_keys_updated_at "
        "BEFORE UPDATE ON command_code_keys "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    """등록된 Key 매핑이 있으면 중단한다. 테이블이 비어 있을 때만 되돌린다."""
    # 검사 이후 새 행이 들어오는 것을 막고, 뒤의 DDL과 같은 잠금을 잡는다.
    op.execute("LOCK TABLE command_code_keys IN ACCESS EXCLUSIVE MODE")
    # SQL로 검사해야 --sql로 만든 downgrade 스크립트를 실행할 때도 보호가 유지된다.
    op.execute(
        """
        DO $command_code_keys_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM command_code_keys) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: command_code_keys contains key mappings.',
                    HINT = 'Keep this revision; key mapping history must not be deleted.';
            END IF;
        END;
        $command_code_keys_guard$;
        """
    )
    # 트리거와 인덱스는 테이블과 함께 사라진다.
    op.drop_table("command_code_keys")
