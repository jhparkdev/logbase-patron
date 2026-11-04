# 협업 규칙

## 1. 브랜치 구조

```text
main ← dev ← feature/*
```

### `main`
- 발표 또는 배포 가능한 안정 버전만 둔다.
- 직접 작업하지 않고, 직접 `push`하지 않는다.
- `dev`에서 검증된 내용만 PR로 병합한다.
- `main`은 배포하지 않는다. 배포는 `dev` 기준으로만 한다. 개발 환경에서 통합 테스트를 확인한 뒤에만 병합한다.

### `dev`
- 팀 통합 브랜치이고, 기능 통합과 테스트의 기준이다.
- 모든 기능 브랜치는 PR로 `dev`에 병합한다.
- 직접 `push`하지 않는다.
- `dev`에 병합되면 **개발 환경**에 자동 배포된다. 병합한 뒤 개발 환경에서 동작을 확인한다.

### `feature/*`
- 기능 하나당 브랜치 하나가 원칙이다.
- 이름: `feature/<영역>-<기능>`. 영역은 `be`, `fe`, `devops`, `docs` 중 하나다.
  - 예: `feature/be-auth`, `feature/fe-customer-usage`, `feature/devops-ci`

---

## 2. 기본 작업 순서

### 작업 시작 전
항상 최신 `dev`를 기준으로 시작한다.

```bash
git checkout dev
git pull origin dev
git checkout -b feature/be-auth      # 새 브랜치
# 이미 만든 브랜치라면
git checkout feature/be-auth
git merge dev                        # 최신 dev 반영
```

### 작업 후 Commit

```bash
git status
git add <파일>
git commit -m "feat: 로그인 API 추가"
git push origin feature/be-auth
```

---

## 3. Commit Message 규칙

| Prefix | 의미 |
|---|---|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `refactor` | 기능 변화 없는 코드 구조 개선 |
| `docs` | 문서 작성 및 수정 |
| `test` | 테스트 코드 및 테스트 관련 수정 |
| `chore` | 설정, 패키지, 환경 관련 작업 |
| `style` | 코드 포맷팅 및 스타일 수정 |

- 형식: `<prefix>: <무엇을 했는지>`
- 메시지만 보고 무엇을 했는지 바로 알 수 있게 쓴다.
  - 좋은 예: `feat: 기록 API에 request_id 중복 처리 추가`
  - 나쁜 예: `feat: 수정`, `fix: 버그`

---

## 4. Pull Request 규칙

```text
feature/*  →  Pull Request  →  dev
```

- 작업이 끝나면 본인 브랜치에서 `dev`로 PR을 만든다.
- 직접 `dev`에 merge하지 않는다.
- 최소 1명의 팀원이 코드를 확인한 뒤 merge한다.

### PR 제목
담당 영역을 앞에 표시한다. 형식은 `[영역] 내용`이다.
- 예: `[BE] 로그인·세션 API`, `[FE] 고객 사용 현황 화면`, `[DevOps] CI 워크플로 추가`, `[Docs] 배포 절차 문서 추가`

### PR 내용
최소한 아래 네 항목을 쓴다.

```markdown
## 구현 내용
- 무엇을 왜 만들었는지

## 변경 파일
- 주요 파일과 역할

## 테스트
- 추가한 테스트, 실행한 명령과 결과

## 확인 필요
- 리뷰어가 특히 봐 줬으면 하는 점, 공용 인터페이스 변경 여부, 남은 작업
```

---

## 5. Merge 규칙

아래 조건을 모두 만족할 때만 merge한다.

- CI가 통과했다.
- 코드 실행에 문제가 없다.
- 기존 기능이 깨지지 않았다.
- 최소 1명이 리뷰했다.
- 공용 인터페이스 변경 여부를 확인했다.
- 충돌을 모두 해결했다.

본인이 만든 PR을 본인이 바로 merge하지 않는 것이 원칙이다.

---

## 6. 충돌(Conflict) 규칙

- 충돌이 났을 때 상대방 코드를 임의로 지우지 않는다.
- 먼저 어떤 파일에서 충돌했는지 확인한다.

  ```bash
  git status
  ```

- 다른 팀원이 작성한 코드와 충돌했다면 반드시 그 팀원과 확인한 뒤 고친다.

---

## 7. 공용 인터페이스 변경

아래는 합의 없이 바꾸지 않는다. 바꿔야 하면 팀에 먼저 알리고, PR의 "확인 필요"에 적는다.

- API 요청·응답 구조
- DB 스키마와 마이그레이션
- JSON Schema
- 공통 컴포넌트
- `docs/`와 `CLAUDE.md`

---

## 8. `.env` 관리

- API Key, Token, 비밀번호는 절대 GitHub에 올리지 않는다.
- 실제 값이 든 `.env`는 Git에서 제외한다. 필요한 변수 목록은 `.env.example`에 값 없이 적는다.
- 실수로 Key를 커밋했다면 바로 팀에 알리고, 해당 Key를 폐기한 뒤 새로 발급한다.

---

## 9. 올리지 않는 파일

- 모델 파일, 대용량 데이터 파일
- `.venv/`, `node_modules/`, 빌드 결과물, 캐시

---

## 10. 패키지 설치 규칙

새 패키지를 설치했다면 반드시 프로젝트 의존성에도 반영하고, 그 변경을 Commit한다.

```bash
# Python (backend): pyproject.toml, uv.lock 변경을 Commit
uv --directory backend add <패키지명>

# Frontend: package.json, pnpm-lock.yaml 변경을 Commit
pnpm --dir frontend add <패키지명>
```

`pip install`만 하고 끝내지 않는다. 프론트엔드에 `npm install`이나 `yarn`을 쓰지 않는다.

---

## 11. 테스트 배치

테스트할 구현 파일마다 짝 테스트 파일을 둔다. 위치는 아래 규칙을 따른다.
- **백엔드**: 구현 코드(`backend/app/`)와 분리해 `backend/tests/`에 두고, 폴더 구조는 `app/`을 그대로 비춘다. 규칙: `app/<폴더>/<이름>.py` → `tests/<폴더>/test_<이름>.py`
  - 예: `backend/app/services/cost.py` → `backend/tests/services/test_cost.py`
  - 예: `backend/app/models.py` → `backend/tests/test_models.py`
  - 예: `backend/app/schemas/usage.py` → `backend/tests/schemas/test_usage.py`. 이 테스트는 검증 규칙(금액 문자열, 범위, 필수값)을 확인한다
  - 기능 단위 통합 시나리오(예: 예산 등록부터 사용률 조회까지)는 해당 라우터의 테스트 파일(`tests/api/test_budgets.py`)에 둔다.
  - 공통 fixture는 `backend/tests/conftest.py`에 둔다. DB 세션, 가짜 OpenRouter 클라이언트, 로그인한 테스트 클라이언트, 고정 시각이 여기 들어간다.
  - `tests/`와 하위 폴더마다 `__init__.py`를 둔다. 다른 폴더에 같은 이름의 테스트 파일이 있어도 충돌하지 않게 하기 위해서다.
- **DB 테스트**: 실제 PostgreSQL을 쓴다.
  - 테스트용 DB(`patron_test`)는 `docker compose up -d db`로 띄운 컨테이너 안에 둔다.
  - 테스트마다 트랜잭션을 롤백해서 서로 격리한다.
- **프론트엔드**: 같은 폴더에 둔다. 예: `frontend/src/shared/lib/format.ts` → `frontend/src/shared/lib/format.test.ts`. Vitest와 Testing Library로 테스트한다.
  - 판단이나 동작이 있는 코드만 테스트한다(`lib` 함수, 값에 따라 표시가 달라지는 컴포넌트, 라우팅, 폼). 받은 값을 그대로 그리기만 하는 컴포넌트는 테스트를 두지 않는다. 기준은 `frontend/CLAUDE.md` 테스트 절이다.
  - `routes/` 안의 테스트는 이름을 `-`로 시작한다(예: `-index.test.tsx`). 라우터가 화면으로 인식하지 않게 하기 위해서다.
- **순수 함수 우선**: 다음은 DB 없이 단위 테스트할 수 있는 순수 함수로 만든다.
  - 비용 상태 결정
  - 예산 사용률·경고 상태 계산
  - Simulation 전체 상태 계산
  - JSON·Schema 검증

---

## 12. 하루 작업 종료 시

작업을 끝내기 전에 최소한 현재 코드를 Commit하고 Push한다.

```bash
git status
git add <파일>
git commit -m "feat: 작업 내용"
git push origin feature/본인브랜치
```

작업 중간 상태라도 다른 팀원이 알아볼 수 있는 Commit 메시지를 쓴다.

---

## 13. 절대 하지 않는 것

아래 작업은 팀원 협의 없이 하지 않는다.

```text
main 직접 push
dev 직접 push
force push (git push --force)
다른 사람 브랜치 삭제
다른 사람 코드 임의 삭제
공용 DB Schema 임의 변경
.env 업로드
검증하지 않은 코드 dev merge
```

특히 아래 명령은 사용 전에 반드시 팀원과 확인한다.

```bash
git push --force
git reset --hard
git clean -fd
```

---

## 14. 작업 흐름 요약

```text
dev 최신화
   ↓
feature 브랜치 생성
   ↓
개별 기능 개발
   ↓
Commit → Push
   ↓
Pull Request (→ dev)
   ↓
CI 통과 + 팀원 Review
   ↓
dev Merge → 개발 환경 자동 배포
   ↓
개발 환경에서 통합 테스트
   ↓
dev → main PR
   ↓
main Merge
```

---

## 15. 핵심 규칙 요약

> `main`은 안정 버전용, `dev`는 통합·배포용으로 사용한다. 배포는 `dev` 기준으로만 한다.

> 모든 개발은 `feature/*` 브랜치에서 진행한다.

> `main`, `dev`에는 직접 push하지 않는다.

> 기능 개발 후 PR을 통해 `dev`에 병합한다.

> 최소 1명이 코드 확인 후 merge한다.

> 충돌 발생 시 상대방 코드를 임의로 삭제하지 않는다.

> API, JSON Schema 등 공용 Interface는 합의 없이 변경하지 않는다.

> 작업 시작 전 최신 `dev`를 반영한다.

> 작업 종료 전 Commit과 Push를 진행한다.
