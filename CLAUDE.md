# 프로젝트: BASE Patron (Super Admin) PoC

이 저장소는 `backend/`(Python, FastAPI)와 `frontend/`(React, TypeScript) 두 앱으로 구성된다. 데이터베이스는 PostgreSQL이고 배포 대상은 GCP Cloud Run이다. 백엔드 패키지는 uv가, 프론트엔드 패키지는 pnpm이 관리한다. 각 앱 코드를 작업할 때는 그 폴더의 `CLAUDE.md`(`backend/CLAUDE.md`, `frontend/CLAUDE.md`)도 따른다. 두 지침이 충돌하면 더 가까운 폴더의 지침을 우선한다.

## 기준 문서
- 구조와 데이터 흐름은 `docs/ARCHITECTURE.md`다.
- 협업 규칙과 테스트 배치는 `CONTRIBUTING.md`다.
- 외부 라이브러리와 API의 동작은 프로젝트가 실제로 쓰는 버전의 공식 문서로 확인한다. 기억에 의존해 옛 버전의 사용법을 쓰지 않는다.

## 기술 스택
- 백엔드: Python 3.14, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x(async), Alembic, httpx(async), Ruff, pytest(실제 PostgreSQL)
- 프론트엔드: Node.js LTS(24 이상), pnpm, React 19, React Compiler, TypeScript, Vite, TanStack Router, TanStack Query, React Hook Form, Zod 4, Tailwind CSS v4, Recharts, Biome, Vitest
- 디자인: TDS(토스 디자인 시스템)를 참고해 웹 대시보드용 디자인 시스템을 직접 만든다. TDS 패키지는 설치하지 않는다. 세부 규칙은 `frontend/CLAUDE.md`와 `docs/design/`을 따른다.
- DB: PostgreSQL 18. AI 연동: OpenRouter API
- 인프라: Docker, docker compose, GCP(Cloud Run·Cloud SQL·Cloud Storage·Artifact Registry·Secret Manager·Cloud Build), GitHub Actions(PR 검사), Cloud Build(배포, `cloudbuild.yml`)
- 새 의존성, 새 패키지, 폴더 구조 변경, 배포 설정 변경은 사용자 승인 후 진행한다.

## pnpm과 uv를 함께 쓰는 방법
- 프론트엔드 의존성은 pnpm으로만, 백엔드 의존성은 uv로만 설치한다. `backend/`에 `package.json`을 두지 않고, `frontend/`에 Python 패키지를 두지 않는다.
- lockfile은 `frontend/pnpm-lock.yaml`과 `backend/uv.lock` 두 개만 커밋한다. `package-lock.json`, `yarn.lock`, `requirements.txt`를 따로 만들지 않는다.
- 도구 버전은 `frontend/package.json`의 `packageManager` 필드(pnpm)와 `backend/.python-version`(Python)에 적는다.
- 명령은 저장소 루트에서 `pnpm --dir frontend <스크립트>`와 `uv --directory backend run <명령>`으로 부른다. 백엔드는 `backend/`에서 uv만으로도 설치하고 실행할 수 있어야 한다.

## 명령어
PR을 올리기 전에 아래 명령이 모두 통과해야 한다. CI도 같은 명령을 실행한다. 모든 명령은 저장소 루트에서 실행한다.
```
uv --directory backend run ruff check                # 백엔드 린트
uv --directory backend run ruff format --check       # 백엔드 포매팅 검사
uv --directory backend run pytest -q                 # 백엔드 테스트
pnpm --dir frontend typecheck                        # 프론트엔드 타입 검사 (tsc --noEmit)
pnpm --dir frontend lint                             # 프론트엔드 린트 (biome)
pnpm --dir frontend test                             # 프론트엔드 테스트 (vitest run)
pnpm --dir frontend build                            # 프론트엔드 빌드
```
- 프론트엔드 명령 4개는 `frontend/package.json`이 생긴 뒤부터 실행한다.
- 백엔드 테스트 전에 `docker compose up -d db`로 PostgreSQL을 띄워 둔다. 이미 실행 중인 컨테이너를 재사용하고, 승인 없이 Dockerfile이나 추가 컨테이너를 만들거나 `--build`, `--force-recreate`로 다시 띄우지 않는다.
- 개발 서버는 `uv --directory backend run fastapi dev app/main.py`와 `pnpm --dir frontend dev`로 띄운다.
- API 계약을 바꾸면 `uv --directory backend run python -m app.export_openapi ../frontend/openapi.json`으로 OpenAPI 문서를 다시 만들고, `pnpm --dir frontend gen:api`로 프론트엔드 타입을 갱신한다. 그다음 두 쪽 검사를 모두 실행한다.

## 계약은 한 곳에서만 정의한다
- HTTP API 계약의 정본은 백엔드의 Pydantic 모델이다. FastAPI가 이 모델로 OpenAPI 문서를 만들고, 프론트엔드는 그 문서에서 TypeScript 타입을 생성해 쓴다.
- 같은 필드를 프론트엔드에서 손으로 `type`이나 `interface`로 다시 쓰지 않는다. 생성된 타입 파일은 직접 고치지 않고 생성 명령으로만 갱신한다.
- 두 쪽에서 같은 의미로 쓰는 값(상태 값, 오류 코드, 모델 수 범위 같은 한도)은 백엔드 계약에 한 번 정의하고 OpenAPI의 enum이나 응답으로 프론트엔드에 전달한다.
- 외부에서 들어오는 값은 신뢰 경계에서 검증한 뒤에만 안쪽 코드로 넘긴다. 타입 선언만으로는 실제 값이 검증되지 않는다.
- 비슷해 보인다는 이유만으로 서로 다른 규칙을 하나로 합치거나, 쓰일지 모른다는 이유만으로 공용 모듈을 만들지 않는다.

## 아키텍처 규칙
- 백엔드는 `api`(입출력) → `services`(규칙·계산) → `models.py`(ORM) 순서로 의존한다. 라우터에서 쿼리를 직접 쓰지 않는다.
- 요청·응답 모델은 `backend/app/schemas/<도메인>.py`에 둔다. 도메인은 `api/` 파일과 짝을 맞춘다. 여러 도메인이 쓰는 타입만 `schemas/common.py`에 둔다.
- OpenRouter 호출은 `backend/app/openrouter/client.py`에서만 한다. 테스트에서는 가짜 클라이언트를 주입한다.
- AIRequest 생성과 상태·비용 변경은 `backend/app/services/requests.py`만 한다.
- P-01·P-02 집계는 `backend/app/services/aggregation.py`만 한다. 화면과 라우터에서 따로 합산하지 않는다.
- 금액과 단가는 `Decimal`과 `NUMERIC(20,12)`로 다룬다. float을 쓰지 않는다. API에서는 금액을 문자열로 주고받는다. (OpenRouter 단가가 토큰당 소수 10자리까지 나오는 것을 검증으로 확인함)
- 시각은 UTC(`timestamptz`)로 저장하고, KST 변환은 화면(`frontend/src/shared/lib`)에서 한다. 월 경계 집계는 서버에서 KST 기준으로 계산한다.
- DB 스키마 변경은 Alembic 마이그레이션(`backend/migrations/`)으로만 한다.
- 프론트엔드는 `/api`만 상대 경로로 호출한다. 개발은 Vite proxy가, 배포는 frontend 컨테이너(nginx)가 `/api/*`를 backend로 프록시한다. 조회 조건·정렬·페이지는 URL 검색 파라미터에 둔다.
- 업로드 이미지 파일은 `backend/app/services/image_storage.py`의 `ImageStorage`로만 저장한다. 개발·테스트는 로컬 폴더(`LocalImageStorage`), 배포는 GCS 버킷이다. DB(`InputAsset`)에는 저장소 키(버킷·폴더 이름 없는 상대 경로)와 해시만 둔다. 컨테이너 파일시스템은 임시 저장소라 배포에서 쓰지 않는다. 저장한 파일은 덮어쓰거나 지우지 않는다.
- 배포 설정(`backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf.template`, `docker-compose.yml`, `.github/workflows/`, `cloudbuild.yml`, `deploy/README.md`)은 다음 구성을 따른다. 컨테이너는 frontend(nginx)와 backend(FastAPI) 둘이고, nginx가 `/api/*`만 backend로 프록시한다. 배포 환경은 `dev` 브랜치가 개발, `main` 브랜치가 운영 둘이다. GitHub Actions(`ci.yml`)는 PR 검사만 하고, 배포는 브랜치에 병합되면 Cloud Build 트리거가 `cloudbuild.yml`로 실행한다. Claude Code로 GCP 리소스를 만들거나 배포 명령(`gcloud run deploy` 등)을 실행하지 않는다. 배포는 Cloud Build 트리거와 `deploy/README.md` 절차로 한다. GCP를 조회할 일이 있으면 먼저 `gcloud auth list`와 `gcloud config get-value project`로 계정과 프로젝트를 확인한다.
- CRITICAL: OpenRouter Key와 Ingest 토큰 원문은 환경변수나 Secret Manager로만 받는다. DB, API 응답, 화면, 로그, 예외 메시지에 넣지 않는다. 이유: Key가 새면 외부 과금 사고가 난다.
- CRITICAL: 다음 이력은 삭제하거나 덮어쓰지 않는다. 이유: 실패·과거 이력이 사라지면 비용 집계와 비교 결과를 검증할 수 없다.
  - 대상: AIRequest, SimulationRun, SimulationResult, ModelRegistry, ModelPrice, InputAsset과 저장소의 이미지 파일, User. User는 `is_active=false`로만 비활성화한다
  - 재실행은 새 ID로 만든다. 가격 변경은 새 행으로 남긴다. 종료된 AIRequest의 실행 상태는 바꾸지 않는다.
  - 종료된 AIRequest의 비용은 OpenRouter 대조(reconcile)로만 갱신한다. 갱신할 때는 기존 값·새 값·근거·시각을 정정 이력으로 남기고 `reconciled_at`을 기록한다. 확정(CONFIRMED) 비용을 현재 가격으로 다시 계산하지 않는다.
- CRITICAL: 비용 미확인을 0으로 기록하거나 0으로 표시하지 않는다(`cost_status=UNKNOWN` ⇔ `cost_usd IS NULL`). 과거 확정 비용을 현재 가격으로 다시 계산하지 않는다. 이유: 실제 지출을 축소하거나 왜곡해 보고하게 된다.
- CRITICAL: 고객 사용량(CUSTOMER_SERVICE)과 내부·시뮬레이션·테스트 비용을 섞지 않는다. 고객·프로젝트(Key)를 알 수 없는 호출은 미분류로 두고, 임의로 귀속하지 않는다. 호출 단위의 개인 사용자 식별은 하지 않는다(Key 단위로 식별). 이유: 고객별 원가와 내부 예산이 틀어진다.
- CRITICAL: 로그인·health·기록 API를 뺀 모든 `/api` 라우트는 로그인 세션을 요구한다. 기록 API는 Ingest 토큰을 요구한다. 이유: 고객 사용 데이터와 Prompt가 인증 없이 노출된다.

## 코드 규칙
- 주석은 의도, 제약, 판단 이유가 코드만으로 드러나지 않을 때만 남긴다. 유효한 기존 주석은 지우지 않는다.
- 매직넘버 대신 이름이 의미를 설명하는 상수, 설정값, 입력에서 계산한 값을 쓴다.
- 파일이 100줄을 넘으면 응집도를 해치지 않는 범위에서 분리를 검토한다. 단 `backend/app/models.py`는 한 파일로 둔다.
- 빈 `except`나 빈 `catch`로 오류를 숨기지 않는다. 복구하거나 사용자에게 보여 줄 오류로 바꿀 수 있을 때만 예외를 잡는다.
- 사용자가 요청한 범위 밖의 코드를 함께 고치지 않는다. 발견한 문제는 보고에 따로 적는다.

## 테스트
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성한다(TDD).
- 구현 세부보다 계약과 보안 경계를 먼저 검증한다. 예: 로그인 실패 응답이 계정 존재 여부를 드러내지 않는지, 세션 삭제 뒤 토큰이 거절되는지, 같은 조건의 요약 합계와 상세 합계가 같은지.
- 시간과 횟수 경계(KST 월 경계, 세션 만료, 모델 2~4개, 조회 기간 366일)는 바로 전, 정확히 그 값, 바로 후를 모두 검사한다.
- 정책 판단(비용 상태, 예산 상태, Simulation 전체 상태, JSON·Schema 검증)은 현재 시각을 인자로 받는 순수 함수로 만들어 DB 없이 검증한다.
- 테스트 파일 배치는 `CONTRIBUTING.md` 11절을 따른다.
- 테스트, 디버깅, 검증을 위해 만든 임시 파일(스크립트, 출력물, 스크린샷, 임시 DB 데이터)은 용무가 끝나면 삭제한다. 추적 중인 파일과 사용자가 만든 파일은 건드리지 않는다.
- CRITICAL: 테스트와 seed는 실제 OpenRouter를 호출하지 않는다. 테스트는 `patron_test` DB에만 접속한다. 운영 환경(`APP_ENV=production`)의 seed는 `--confirm-production` 옵션이 있을 때만 실행한다. 이유: 의도하지 않은 과금과 데이터 오염이 생긴다.

## 비밀정보
- CRITICAL: `.env`와 `.env.*` 파일은 절대 읽거나 열거나 출력하지 않는다(`cat`, `head`, Read 도구 모두 금지). 키가 필요하면 변수 이름만 쓰고, 값은 실행 중인 코드가 pydantic-settings로 불러온다. 이유: 키가 대화 기록에 노출된다.
- `.env`, API 키, 토큰, 비밀번호, 개인정보, 운영 데이터를 커밋하거나 로그와 오류 메시지에 남기지 않는다.
- 운영 비밀값은 Secret Manager에만 두고 코드, Dockerfile, CI 설정에 적지 않는다. 로컬에서는 커밋하지 않는 `.env`를 쓰고, 필요한 키 이름만 `.env.example`에 적는다.
- 개발용 키와 운영용 키를 분리하고, 운영 키는 사용자가 명시한 운영 작업에서만 쓴다.

## 위험한 작업은 먼저 확인받는다
- 공용 인터페이스(API 응답 구조, `models.py`와 마이그레이션, JSON Schema, 공통 컴포넌트), 인증과 권한 경계, 되돌리기 어려운 마이그레이션, 운영 데이터를 바꾸는 작업은 시작 전에 영향을 설명하고 확인받는다.
- 파일이나 데이터를 지우거나 덮어쓰기 전에는 대상을 먼저 확인한다.

## Git
- 브랜치·PR·병합 규칙은 `CONTRIBUTING.md`를 따른다. `main`과 `dev`에서 직접 작업하거나 push하지 않는다. 브랜치는 최신 `dev`에서 `feature/<영역>-<기능>`으로 만든다.
- 커밋 메시지는 `<prefix>: <무엇을 했는지>` 형식이다. prefix는 feat, fix, refactor, docs, test, chore, style 중 하나다. 한 커밋에는 하나의 목적만 담는다.
- 기능 단위의 구현과 검증이 끝날 때마다 관심사별로 커밋한다. 사용자나 다른 작업자의 변경은 커밋에 넣지 않는다.

## 보고
- 결론을 첫 문장에 쓴다. 그다음 근거를 쓰고, 마지막에 남은 일과 사용자가 정할 것을 쓴다.
- 실행한 검증과 실행하지 않은 검증을 구분해 적는다. 로컬 빌드 성공을 배포 성공이나 외부 연동 성공으로 보고하지 않는다.
- 테스트가 실패했으면 실패한 출력을 그대로 보여 준다.
