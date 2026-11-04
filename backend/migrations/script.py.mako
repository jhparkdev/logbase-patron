"""${message}

리비전 ID: ${up_revision}
이전 리비전: ${down_revision | comma,n}
생성 시각: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Alembic이 사용하는 리비전 식별 정보.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """DB 스키마에 이번 변경을 적용한다."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """DB 스키마를 이전 리비전으로 되돌린다."""
    ${downgrades if downgrades else "pass"}
