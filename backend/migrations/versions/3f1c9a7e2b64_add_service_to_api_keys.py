"""OpenRouter Key가 어느 서비스의 것인지 연결하는 칸을 추가한다.

여러 서비스가 함께 쓰는 Key가 있어 NULL을 허용하며, 기존 행은 NULL로 남는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f1c9a7e2b64"
down_revision: str | Sequence[str] | None = "264258125f67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "service_id",
            sa.BigInteger(),
            nullable=True,
            comment="이 Key를 쓰는 서비스. 여러 서비스가 함께 쓰는 Key는 NULL",
        ),
    )
    op.create_foreign_key(
        op.f("api_keys_service_id_fkey"),
        "api_keys",
        "services",
        ["service_id"],
        ["service_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Key와 서비스의 연결이 있으면 중단한다. 칸이 비어 있을 때만 되돌린다."""
    op.execute("LOCK TABLE api_keys IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $mapping_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM api_keys WHERE service_id IS NOT NULL) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: API keys are linked to a service.',
                    HINT = 'Keep this revision; do not erase key mappings to downgrade.';
            END IF;
        END;
        $mapping_guard$;
        """
    )
    op.drop_constraint(op.f("api_keys_service_id_fkey"), "api_keys", type_="foreignkey")
    op.drop_column("api_keys", "service_id")
