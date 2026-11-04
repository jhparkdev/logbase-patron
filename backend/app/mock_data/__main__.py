"""mock seed SQL을 다시 만든다. 네트워크와 DB를 쓰지 않는다.

사용법 (저장소 루트에서):
    uv --directory backend run python -m app.mock_data
"""

import sys

from app.mock_data.dataset import build_dataset
from app.mock_data.sql import SEED_FILE, render_seed


def main() -> int:
    dataset = build_dataset()
    SEED_FILE.write_text(render_seed(dataset), encoding="utf-8", newline="\n")
    for table, rows in dataset.items():
        print(f"{table}: {len(rows)}")
    print(f"작성 완료: {SEED_FILE} ({SEED_FILE.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
