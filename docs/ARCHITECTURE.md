# 아키텍처

## 디렉토리 구조
아래는 목표 구조이고, 각 항목은 기능 브랜치에서 구현하면서 추가한다. 파일 단위 구성은 기능을 구현하면서 정한다. 어느 모듈이 어떤 규칙을 책임지는지는 CLAUDE.md와 backend/CLAUDE.md를 따른다.
```
backend/                    # Python · FastAPI 서버 (uv 프로젝트)
├── pyproject.toml          # uv 프로젝트 설정과 의존성
├── Dockerfile              # backend 이미지 (uvicorn, /api만 처리)
├── migrations/             # Alembic 마이그레이션
├── tests/                  # 테스트. app/ 폴더 구조를 그대로 비춘다. 배치 규칙은 CONTRIBUTING.md
└── app/                    # 앱 진입점, 설정(환경변수·Secret), DB 세션, ORM 모델(한 파일), CLI
    ├── schemas/            # Pydantic 요청·응답 모델. 도메인별 파일로 나누고 api/와 짝을 맞춘다
    ├── api/                # 라우터. 입력 검증·인증 확인·응답 변환만 한다
    ├── services/           # 비즈니스 로직. DB 세션을 받아 동작한다
    └── openrouter/         # OpenRouter HTTP 클라이언트. 외부 AI 호출은 여기서만 한다
frontend/                   # React 19 · Vite · TypeScript SPA (pnpm). 화면 디자인이 나온 뒤 만든다
├── Dockerfile              # frontend 이미지 (Node 빌드 → nginx 실행)
├── nginx.conf.template     # / 는 정적 파일 + SPA fallback, /api/* 는 ${BACKEND_URL}로 프록시
├── openapi.json            # 백엔드가 내보낸 API 계약. gen:api가 타입을 생성한다
└── src/
    ├── routes/             # TanStack Router 파일 기반 라우트. 화면 조합과 데이터 선로딩만 한다
    ├── features/<기능>/    # auth, customer-usage(P-01), internal-budget(P-02), models(P-03), simulator(P-04), simulation-history(P-05)
    │   ├── components/     # 화면 블록. 서버 호출과 판단 로직을 두지 않는다
    │   ├── hooks/          # 서버 상태와 화면 동작을 조합한다(TanStack Query)
    │   ├── lib/            # 순수 판단과 변환 로직. 단위 테스트로 검증한다
    │   └── api/            # 요청 함수와 queryOptions. 컴포넌트에서 직접 import하지 않는다
    └── shared/
        ├── components/ui/  # 공용 UI primitive(버튼, 입력, 표, 상태 배지, 비용 표시, 상세 패널)
        ├── api/            # 생성된 API 타입과 공용 fetch 클라이언트
        └── lib/            # KST 날짜·USD 금액·비용 상태 포맷 함수
docker-compose.yml          # db(PostgreSQL 18), backend, frontend. 평소 개발은 db만 띄운다
db/init/                    # db 컨테이너 첫 실행 시 테스트 DB(patron_test)를 만드는 스크립트
.env.example                # 필요한 환경변수 목록 (값 없음)
deploy/                     # GCP 최초 준비 절차 (README.md)
.github/workflows/          # ci.yml(PR의 린트·테스트·빌드). 배포는 하지 않는다
cloudbuild.yml              # Cloud Build 배포(dev·main 병합 시 트리거): 빌드 → 푸시 → 마이그레이션 → backend → frontend
```

## 데이터 흐름
아래 경로 이름은 설계안이다. 최종 경로와 요청·응답 형태는 백엔드 Pydantic 모델을 정본으로 구현하면서 확정한다.
```
[시뮬레이션]
P-04 화면 → POST /api/simulations → services/simulation
  → SimulationRun 저장(PENDING) → 모델별 AIRequest 저장(PENDING, usage_origin=SIMULATION, user_id=로그인 사용자)
  → 백그라운드: 각 AIRequest RUNNING → openrouter/client 병렬 호출
  → 응답마다 AIRequest 종료 상태·Token·비용·실제 Provider 기록 → SimulationResult(응답 원문·JSON/Schema 검증) 저장
  → 모든 호출 종료 후 SimulationRun 전체 상태 계산 → 화면은 폴링으로 결과 표시

[연결 테스트]
P-03 화면 → POST /api/models/{id}/test → AIRequest(usage_origin=SYSTEM_TEST) → OpenRouter 호출
  → 결과 기록 → ModelRegistry.last_test_status / last_tested_at 갱신

[외부 호출 기록]
외부 시스템 → POST /api/usage-records (Ingest 토큰) → services/requests
  → 귀속은 Key 단위(customer_id·project_id)로 한다. 알 수 없으면 미분류. 호출 단위 개인 사용자 식별은 하지 않는다
  → request_id가 이미 있으면 기존 기록 반환(같은 내용) 또는 409(다른 내용), 없으면 저장

[조회]
P-01/P-02 화면 → GET /api/usage/... (필터) → services/aggregation
  → 같은 필터로 요약·추이·그룹별 표·상세 목록 계산 → 화면 표시(UTC→KST 변환은 화면에서)

[시뮬레이터 이미지]
P-04 화면 → 이미지 업로드 → services/image_storage(ImageStorage)에 새 키로 저장(덮어쓰기 거절)
  → InputAsset에 저장소 키·해시만 기록 → 실행 때 저장소에서 읽고 해시를 대조한 뒤 모델에 전달
  → 저장소: 개발·테스트는 로컬 폴더, 배포는 GCS 버킷(컨테이너 디스크는 임시라 쓰지 않는다)
```

API 계약의 정본은 백엔드 Pydantic 모델이다. `app/export_openapi.py`가 OpenAPI 문서를 `frontend/openapi.json`으로 내보내고, 프론트엔드는 그 문서에서 TypeScript 타입을 생성한다. 손으로 타입을 쓰지 않는다.
