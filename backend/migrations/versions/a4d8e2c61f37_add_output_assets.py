"""이미지 생성 결과를 가리키는 output_assets 테이블 추가

결과 이미지 파일은 저장소에 두고 DB에는 경로·해시만 둔다. 기존 테이블은 바꾸지 않는다.

리비전 ID: a4d8e2c61f37
이전 리비전: 3f1c9a7e2b64
생성 시각: 2026-11-02 11:01:48.009590

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Alembic이 사용하는 리비전 식별 정보.
revision: str = "a4d8e2c61f37"
down_revision: str | Sequence[str] | None = "3f1c9a7e2b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "output_assets",
        sa.Column("output_asset_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            nullable=False,
            comment="한 호출이 돌려준 이미지 순서(0부터)",
        ),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "file_size_bytes >= 0", name="output_assets_file_size_bytes_check"
        ),
        sa.CheckConstraint("sort_order >= 0", name="output_assets_sort_order_check"),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["ai_requests.request_id"],
            name=op.f("output_assets_request_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("output_asset_id", name=op.f("output_assets_pkey")),
        sa.UniqueConstraint(
            "request_id", "sort_order", name="uq_output_assets_request_order"
        ),
        comment="이미지 생성 결과 참조. 파일은 저장소에 보관, DB에는 경로·해시만",
    )


def downgrade() -> None:
    """결과 이미지 기록이 있으면 중단한다. 테이블이 비어 있을 때만 되돌린다."""
    # 검사 이후 새 행이 들어오는 것을 막고, 뒤의 DDL과 같은 잠금을 잡는다.
    op.execute("LOCK TABLE output_assets IN ACCESS EXCLUSIVE MODE")
    # SQL로 검사해야 --sql로 만든 downgrade 스크립트를 실행할 때도 보호가 유지된다.
    op.execute(
        """
        DO $output_assets_guard$
        BEGIN
            IF EXISTS (SELECT 1 FROM output_assets) THEN
                RAISE EXCEPTION USING ERRCODE = '23514',
                    MESSAGE = 'Cannot downgrade: output_assets contains output images.',
                    HINT = 'Keep this revision; output image history must not be deleted.';
            END IF;
        END;
        $output_assets_guard$;
        """
    )
    op.drop_table("output_assets")
