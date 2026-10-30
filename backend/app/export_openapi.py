"""OpenAPI 문서를 파일로 쓴다. 서버를 띄우지 않고 프론트엔드 타입을 생성하기 위해서다.

uv --directory backend run python -m app.export_openapi ../frontend/openapi.json
그다음 pnpm --dir frontend gen:api 로 프론트엔드 타입을 갱신한다.
"""

import argparse
import json
from pathlib import Path

from app.main import create_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.export_openapi")
    parser.add_argument("output", type=Path, help="OpenAPI 문서를 쓸 파일 경로")
    args = parser.parse_args(argv)
    document = create_app().openapi()
    # 한국어 설명을 그대로 두고 키 순서를 유지해, 계약이 바뀐 줄만 diff 에 드러나게 한다
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
