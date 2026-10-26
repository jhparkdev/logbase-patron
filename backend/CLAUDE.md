# 백엔드 지침

`backend/**` 작업에 적용한다. 루트 `CLAUDE.md`의 규칙 위에 더해지는 지침이다. 스택은 Python 3.14, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x(async, asyncpg), Alembic, httpx, Ruff, pytest(pytest-asyncio)다.

## 도구
- 의존성은 uv로만 관리한다. `uv add`, `uv remove`로 `pyproject.toml`과 `uv.lock`을 함께 갱신하고 `pip install`을 직접 쓰지 않는다. 개발 전용 도구는 `uv add --dev`로 넣는다.
- Python 버전은 `.python-version`(3.14)에 고정하고 `uv sync`로 `.venv`를 만든다. `.venv`는 커밋하지 않는다.
- 개발 서버는 `uv --directory backend run fastapi dev app/main.py`로 띄운다. 컨테이너에서는 uvicorn으로 실행한다.
- 린트와 포매팅 도구는 Ruff뿐이다. 다른 도구를 추가하지 않는다.
- 모든 함수에 타입 힌트를 붙인다. `Any`는 외부 라이브러리 경계에서만 쓰고 바로 좁힌다.
- OpenAPI 문서는 `app/export_openapi.py`처럼 `app.openapi()` 결과를 파일로 쓰는 명령으로 만든다. 서버를 띄우지 않고도 프론트엔드 타입을 생성할 수 있어야 한다.

## 구조
```
app/
  main.py              # FastAPI 앱 생성, lifespan, 라우터 등록
  config.py            # pydantic-settings. 환경변수와 Secret은 여기서만 읽는다
  db.py                # 엔진 하나, async_sessionmaker, 요청 단위 세션 의존성
  models.py            # SQLAlchemy ORM 전체 (한 파일)
  cli.py               # user-create, seed 같은 운영 명령
  schemas/<도메인>.py   # 요청·응답 Pydantic 모델 (API 계약의 정본). api/와 짝을 맞춘다
  api/<도메인>.py       # 라우터. 입력 검증·인증 확인·응답 변환만 한다
  services/<도메인>.py  # 업무 규칙, 계산, 트랜잭션
  openrouter/client.py # OpenRouter를 부르는 유일한 곳
tests/                 # 구현 코드와 분리한다. app/ 폴더 구조를 그대로 비춘다
  conftest.py          # 공통 fixture: DB 세션, 가짜 OpenRouter, 로그인한 클라이언트, 고정 시각
  test_models.py       # app/models.py 의 테스트
  api/ services/ schemas/ openrouter/   # app/<폴더>/<이름>.py → tests/<폴더>/test_<이름>.py
```
- 의존 방향은 `api → services → models`다. 라우터에서 DB를 직접 조회하지 않는다.
- 규칙의 책임 모듈은 정해져 있다. AIRequest 생성·상태 전이·비용 기록은 `services/requests.py`, P-01·P-02 집계는 `services/aggregation.py`, 모델 상태 전이는 `services/model_registry.py`, Simulation 실행과 전체 상태는 `services/simulation.py`다.
- 순수 판단 함수(비용 상태 결정, 예산 사용률·상태, Simulation 전체 상태, JSON·Schema 검증)는 DB 세션 없이 호출할 수 있게 분리한다.
- 운영 작업(계정 생성, seed, 데이터 보정)은 HTTP 경로를 늘리지 않고 `cli.py` 명령으로 만든다.
- seed는 앱 시작 시 자동으로 넣지 않고 명시적 명령으로만 실행한다. 고정 ID를 써서 여러 번 실행해도 중복이 생기지 않게 한다.
- 시작과 종료 처리(오래 남은 PENDING·RUNNING 정리 등)는 `lifespan`에 둔다. 폐기된 `@app.on_event`는 쓰지 않는다.

## 설정과 의존성 주입
- CRITICAL: `.env`와 `.env.*` 파일은 절대 읽거나 열거나 출력하지 않는다(`cat`, `head`, Read 도구 모두 금지). 키가 필요하면 변수 이름만 쓰고, 값은 실행 중인 코드가 pydantic-settings로 불러온다. 이유: 키가 대화 기록에 노출된다.
- 환경변수는 `config.py`의 `BaseSettings` 한 곳에서 읽는다. 기능 코드에서 `os.environ`을 직접 읽지 않는다.
- 의존성은 `Annotated[타입, Depends(...)]` 형태로 선언하고, 자주 쓰는 것은 `SessionDep`, `CurrentUserDep`, `OpenRouterDep`처럼 별칭으로 묶는다.
- 현재 시각은 의존성으로 주입한다. 테스트에서는 `app.dependency_overrides`로 고정 시각을 넣어 KST 월 경계와 세션 만료 판단을 결정적으로 재현한다.
- OpenRouter 클라이언트도 의존성으로 주입한다. 테스트는 가짜 클라이언트로 바꿔 끼운다.

## 입력과 응답 계약
- 요청 body, query, path 값은 Pydantic 모델이나 `Annotated` 제약으로 검증한다. 검증된 모델을 서비스에 넘기고 같은 필드를 dict나 별도 클래스로 복제하지 않는다.
- 응답은 `response_model` 또는 반환 타입 힌트로 출력 모델을 명시한다. ORM 객체, 비밀번호 해시, 세션 토큰 해시, Key 환경변수 이름 같은 서버 전용 값을 그대로 내보내지 않는다.
- 입력 모델과 출력 모델을 분리한다(`BudgetCreate`, `BudgetRead`). 입력용 변환 로직을 응답 검증에 재사용하지 않는다.
- 스키마는 데이터 형태와 입력 제약만 담당한다. 인증, 권한, 상태 전이, DB 상태에 의존하는 판단은 의존성과 서비스에서 한다.
- 금액은 `Decimal` 필드로 받고 문자열로 직렬화한다. 미확인 비용은 `null`이다. 0으로 바꾸지 않는다.
- 정렬 컬럼과 방향은 화면별 허용 목록에 있는 값만 받는다. 그 밖의 값은 거절한다.
- 오류 응답은 정해진 오류 코드와 사용자에게 보여 줄 문구로 통일한다. 스택 트레이스, SQL, 내부 예외 메시지, Key 원문을 응답에 넣지 않는다.

## 데이터베이스
- 엔진은 프로세스마다 하나만 만들고 `async_sessionmaker(expire_on_commit=False)`로 세션을 연다. 요청마다 세션 하나를 의존성으로 주입한다.
- 모델은 `Mapped[...]`와 `mapped_column()`으로 타입을 명시한다. async에서는 지연 로딩이 오류를 내므로 관계는 `selectinload`로 명시적으로 불러온다.
- 상태값은 PostgreSQL ENUM 대신 `String` 컬럼과 `CheckConstraint`로 표현한다. ENUM은 값을 추가할 때마다 별도 migration이 필요하다.
- 불변조건은 DB 제약으로도 지킨다. 예: `cost_status='UNKNOWN'` ⇔ `cost_usd IS NULL` CHECK, `request_id`와 `openrouter_model_id` 고유 제약.
- 금액과 단가는 `NUMERIC(20,12)`, 시각은 `DateTime(timezone=True)`(timestamptz), ID는 UUID, 테이블과 컬럼 이름은 `snake_case`다.
- `MetaData(naming_convention=...)`로 제약 이름 규칙을 정해 두어 Alembic이 매번 같은 이름을 만들게 한다.
- 쿼리는 SQLAlchemy 바인딩으로만 만든다. 문자열을 이어 붙여 SQL을 만들지 않는다.

## Migration 순서
1. 모델을 바꾼 뒤 `uv --directory backend run alembic revision --autogenerate -m "설명"`으로 migration을 만든다.
2. 생성된 파일을 직접 읽고 검토한다. autogenerate는 이름 변경, 타입 세부 변경, 데이터 이전을 놓칠 수 있다.
3. `uv --directory backend run alembic upgrade head`로 로컬 개발 DB에 적용하고, `uv --directory backend run alembic check`로 모델과 DB 사이에 남은 차이가 없는지 확인한다.
4. 이미 적용되었거나 병합된 migration 파일은 고치지 않는다. 바꿀 것이 있으면 새 migration을 추가한다.
5. 데이터를 지우는 migration(컬럼·테이블 삭제)은 만들지 않는다. 검증을 위해 기존 로컬 데이터를 초기화하지 않는다.

## 인증과 보안
- 비밀번호는 `pwdlib[argon2]`로 Argon2id 해시만 저장한다. 원문은 저장하거나 로그에 남기지 않는다.
- 로그인하면 `secrets.token_urlsafe(32)` 세션 토큰을 발급하고 DB에는 SHA-256 해시만 둔다. 토큰은 JSON body로 돌려주지 않고 `HttpOnly`, `SameSite=Lax`, 배포 시 `Secure` 쿠키로만 전달한다. 만료는 12시간이고, 토큰 수명과 쿠키 수명은 같은 상수에서 가져온다. 쿠키를 지울 때는 발급 때와 같은 `path`를 쓴다.
- 사용자 상태는 매 요청마다 DB에서 확인한다. 비활성화된 사용자의 세션은 거절하고, 로그아웃이나 비활성화 시 세션을 삭제한다.
- 로그인·health·기록 API를 뺀 모든 `/api` 라우트에 `CurrentUserDep`을 건다. 기록 API는 `X-Patron-Ingest-Token`을 `hmac.compare_digest`로 비교하고, 없거나 틀리면 401이다.
- 상태를 바꾸는 요청(POST/PUT/PATCH/DELETE)은 `Origin` 헤더가 `ALLOWED_ORIGIN`과 같을 때만 받는다. 기록 API는 쿠키를 쓰지 않으므로 제외한다. CORS 미들웨어는 켜지 않는다.
- 계정 존재 여부를 드러내지 않는다. 계정 없음과 비밀번호 틀림은 같은 상태 코드와 같은 문구로 돌려주고, 계정이 없어도 더미 해시로 검증을 한 번 수행해 응답 시간을 맞춘다. 새 인증 경로를 만들 때는 이 경로가 계정 존재 여부를 드러내는지 먼저 확인한다.
- 인증 방식(세션 쿠키 대 Bearer 토큰, 역할 유무)은 API 명세서와 차이가 있어 검토 중이다. 바꾸려면 사용자 확인을 받는다.

## OpenRouter 호출
- `openrouter/client.py`만 OpenRouter를 부른다. `httpx.AsyncClient`를 앱 수명 동안 하나 만들어 재사용하고, 모든 호출에 timeout을 명시한다.
- HTTP 오류, timeout, 네트워크 오류를 성공으로 처리하지 않는다. 오류는 `error_type` 8종으로 분류하고 매핑 표는 이 모듈 한 곳에 둔다.
- 성공 여부는 응답의 여러 필드(실제 모델, Token, 비용)로 확인한다. 빈 응답을 성공으로 보지 않는다. 비용은 응답의 `usage.cost`만 쓴다(CONFIRMED). 모델 목록 가격은 직접 계산에 쓰지 않는다. 응답에 비용이 없으면 UNKNOWN으로 두고 대조(reconcile)로 갱신한다.
- 시뮬레이션과 연결 테스트는 자동 재시도하지 않는다. 비교 조건이 바뀌고 비용이 중복되기 때문이다.
- API 키는 응답, 예외 메시지, 로그에 남기지 않는다. httpx 로깅에서 Authorization 헤더를 지우고, 로그에는 호스트, 경로, 상태 코드, `request_id`만 남긴다. Prompt와 응답 원문은 로그에 쓰지 않는다.
- 실제 응답 형태는 문서와 다를 수 있으므로 실제 호출로 확인한다. 확인하지 못했으면 보고에 그렇게 적는다. 실제 호출은 사용자가 요청했을 때 PoC Key로만 한다.

## 테스트
- pytest와 `httpx.AsyncClient(transport=ASGITransport(app=app))`로 API를 검증한다. async 테스트는 pytest-asyncio를 쓴다.
- DB가 필요한 테스트는 `patron_test` DB에서만 돌린다. `TEST_DATABASE_URL`이 다른 DB를 가리키면 conftest에서 거부한다. 테스트마다 트랜잭션을 롤백해 격리한다.
- OpenRouter는 가짜 클라이언트로 바꿔 끼운다. 테스트와 seed는 실제 OpenRouter를 부르지 않는다.
- 테스트는 `app/` 밖의 `tests/`에 두고 폴더 구조를 `app/`과 같게 한다. `app/<폴더>/<이름>.py`의 테스트는 `tests/<폴더>/test_<이름>.py`다. 공통 fixture(DB 세션, 가짜 OpenRouter, 로그인한 클라이언트, 고정 시각)는 `tests/conftest.py`에 둔다. `tests/`와 하위 폴더마다 `__init__.py`를 둔다.
- `pyproject.toml`의 `[tool.pytest.ini_options]`에 `testpaths = ["tests"]`와 `pythonpath = ["."]`를 둔다. 명령을 저장소 루트에서 실행해도 `import app`이 되게 하기 위해서다.
- 순수 정책 함수는 DB 없이 검증한다. 집계는 seed의 기대 합계와 비교하고, 같은 조건의 요약과 상세 목록 합계가 같은지 확인한다.
- 계정 열거 방어는 두 경로의 상태 코드와 응답 본문이 실제로 같은지 비교한다. 유효한 토큰이라도 사용자가 비활성화되면 인증이 거절되는지 검사한다.

## 배포 (Cloud Run)
- 컨테이너는 uv 공식 이미지 패턴으로 의존성 층과 코드 층을 나눠 빌드하고 Artifact Registry에 올린다.
- Cloud SQL에는 Cloud Run의 Cloud SQL 연결(unix socket)로 접속하고, DB를 공개 IP로 열어 두지 않는다.
- migration은 앱 시작 시 실행하지 않고 배포 전에 Cloud Run Job으로 한 번 실행한다. Job이 실패하면 배포를 멈춘다.
- 비밀값은 Secret Manager에서 환경변수로 주입한다. 서비스마다 최소 권한의 서비스 계정을 쓴다.
- backend는 `--max-instances=1 --no-cpu-throttling`으로 띄운다. 백그라운드 시뮬레이션 실행과 미완료 정리가 인스턴스 1대를 전제하기 때문이다.
- 컨테이너 파일시스템은 임시 저장소다. 업로드 이미지는 DB의 InputBlob에 저장한다.
- 로그는 표준 출력에 JSON 한 줄로 남겨 Cloud Logging에서 검색할 수 있게 한다.
- Claude Code는 `gcloud run deploy` 같은 배포 명령을 실행하지 않는다. 배포는 CI/CD와 `deploy/README.md` 절차로 한다.
