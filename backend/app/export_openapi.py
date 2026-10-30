"""OpenAPI 문서를 파일로 내보낸다. 서버를 띄우지 않고도 프론트엔드 타입을 만들 수 있게 한다.

사용: uv --directory backend run python -m app.export_openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import app


def export_openapi(output: Path) -> None:
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("사용법: python -m app.export_openapi <출력 파일 경로>", file=sys.stderr)
        return 2
    export_openapi(Path(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
