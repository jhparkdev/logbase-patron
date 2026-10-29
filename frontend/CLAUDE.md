# 프론트엔드 지침

`frontend/**` 작업에 적용한다. 루트 `CLAUDE.md`의 규칙 위에 더해지는 지침이다. 스택은 React 19, React Compiler, TypeScript, Vite, TanStack Router(파일 기반 라우팅), TanStack Query, React Hook Form, Zod 4, Tailwind CSS v4, Recharts, Biome, Vitest다. 브라우저에서만 동작하는 SPA이며 서버 데이터는 모두 `/api`에서 받는다. UX와 UI는 TDS를 참고해 만든 우리 디자인 시스템을 따른다(아래 "디자인 기준" 참고).

## 이 제품에서 지켜야 하는 것
- 관리자용 웹 콘솔이다. 화면은 로그인과 P-01~P-05 다섯 개다. 화면 정의는 기능 명세서를 따른다. 기준 해상도는 데스크톱 1280px 이상이고 모바일 대응은 하지 않는다.
- 비용은 확정·추정·미확인을 항상 구분한다. 미확인(`null`)을 0이나 "-"로 표시하지 않는다. 확정+추정 합계에는 "추정 포함"을 붙이고, 미확인이 있으면 "미확인 N건 미반영"을 함께 보여 준다. 예산이 없으면 0%가 아니라 "미설정"이다. 확정은 일반 글꼴, 추정은 `≈` 접두와 "추정" 배지, 미확인은 금액 대신 "미확인" 배지로 표시한다.
- 금액은 API가 주는 문자열을 그대로 다룬다. `Number()`로 바꿔 더하지 않는다. 합산은 서버가 하고 화면에서 다시 합산하지 않는다.
- 시각은 UTC로 받아 KST로 표시한다. 변환과 포맷(날짜, USD 금액, 비용 상태 라벨)은 `shared/lib`의 순수 함수로만 하고 단위 테스트를 둔다.
- 실행 상태와 비용 상태는 별도 배지로 보여 준다. 로딩, 조회 결과 없음, 조회 실패, 비용 미확인, 잘못된 입력을 서로 구분해 표시한다.
- 조회 조건, 정렬, 페이지는 URL 검색 파라미터에 둔다. 전체보기와 상세로 이동해도 조건이 유지되고 링크를 공유할 수 있어야 한다.
- 표의 정렬과 페이지는 서버가 한다. 화면에서 전체 결과를 다시 정렬하지 않는다.
- Key 원문, 세션 토큰, 내부 오류 문구를 화면이나 콘솔에 출력하지 않는다.
- 시뮬레이터는 실행 중 전체 취소와 모델별 취소를 모두 제공한다. 취소된 호출의 비용은 0이 아니라 "미확인"으로 표시한다.

## 도구
- 패키지 매니저는 pnpm만 쓴다. `npm install`, `yarn`, `npx` 대신 `pnpm add`, `pnpm remove`, `pnpm dlx`를 쓴다. lockfile은 `frontend/pnpm-lock.yaml` 하나다.
- pnpm은 의존성의 설치 스크립트를 기본으로 막는다. 빌드가 꼭 필요한 패키지만 `pnpm approve-builds`로 허용한다.
- `package.json` 스크립트 이름은 `dev`, `build`, `typecheck`, `lint`, `test`, `gen:api`(`openapi.json`에서 타입 생성)다. 루트에서 `pnpm --dir frontend <스크립트>`로 부른다.
- React Compiler는 `@vitejs/plugin-react`와 `@rolldown/plugin-babel`의 `reactCompilerPreset()`으로 켠다. `@vitejs/plugin-react` 6부터는 `react({ babel })` 옵션이 없어졌으므로 옛 설정 예시를 따라 쓰지 않는다.
- Tailwind CSS는 `@tailwindcss/vite` 플러그인으로 연결하고 CSS 파일에서 `@import "tailwindcss";`로 불러온다. `tailwind.config.js` 대신 CSS의 `@theme`에 디자인 토큰을 정의한다.
- 타입 검사는 `tsc --noEmit`, 린트와 포매팅은 Biome으로 한다.
- React Compiler 규칙 검사가 필요하면 ESLint와 `eslint-plugin-react-hooks`(`recommended-latest`)를 쓴다. 이 조합은 typescript-eslint에 의존하므로, typescript-eslint가 TypeScript 7을 지원할 때까지 TypeScript 6.0 계열을 유지한다.
- 개발 서버는 Vite `server.proxy`로 `/api`를 백엔드(`http://localhost:8000`)에 넘긴다. 배포에서는 nginx가 같은 일을 한다. 코드는 항상 `/api`를 상대 경로로 부른다.

## 구조
```
src/
  routes/            # TanStack Router 파일 기반 라우트. 화면 조합과 데이터 선로딩만 한다
  features/<기능>/   # auth, customer-usage(P-01), internal-budget(P-02), models(P-03), simulator(P-04), simulation-history(P-05)
    components/      # 화면 블록. 서버 호출과 판단 로직을 두지 않는다
    hooks/           # 서버 상태와 화면 동작을 조합한다(TanStack Query 사용)
    lib/             # 순수 판단과 변환 로직. 단위 테스트로 검증한다
    api/             # 요청 함수와 queryOptions. 컴포넌트에서 직접 import하지 않는다
  shared/
    components/ui/   # 디자인 토큰 기준 공용 UI primitive(버튼, 입력, 표, 상태 배지, 비용 표시, 상세 패널)
    api/             # 생성된 API 타입과 공용 fetch 클라이언트
    lib/             # KST 날짜·USD 금액·비용 상태 포맷 함수
  assets/            # 로고, 아이콘 같은 정적 이미지
  test/              # 여러 테스트가 함께 쓰는 도구(예: 주소를 지정해 앱을 띄우는 renderAt)
```
- 의존 방향은 `routes → features → shared`다. 다른 기능의 내부 파일을 직접 import하지 않는다.
- 컴포넌트는 props와 hook 결과만 렌더링한다. 필터, 라벨 계산, 상태 판정, 제출값 조립은 `lib`로 옮긴다.
- 라우트 파일 트리(`routeTree.gen.ts`)는 플러그인이 생성하므로 직접 고치지 않는다.
- 테스트 파일은 구현 파일 옆에 `*.test.ts` 또는 `*.test.tsx`로 둔다(`CONTRIBUTING.md` 11절). `routes/` 안의 테스트는 이름을 `-`로 시작한다(예: `-index.test.tsx`). 그래야 라우터가 화면으로 인식하지 않는다.

## React Compiler
- 컴파일러가 메모이제이션을 자동으로 하므로 새 코드에 `useMemo`, `useCallback`, `React.memo`를 습관적으로 넣지 않는다. 기존 메모이제이션은 동작을 확인하기 전까지 지우지 않는다.
- 컴포넌트와 hook은 순수하게 작성한다. 렌더링 중에 props, state, 외부 변수를 바꾸거나 `ref.current`를 읽고 쓰지 않는다.
- 파생 값은 state에 복사하지 않고 렌더링 중에 계산한다. `useEffect`는 외부 시스템과 동기화할 때만 쓴다.
- 컴파일 후 문제가 생긴 컴포넌트에만 임시로 `"use no memo"`를 붙이고, 이유와 해결 계획을 주석으로 남긴다.

## 서버 데이터
- 서버 상태는 TanStack Query로만 다룬다. 같은 데이터를 위한 별도 전역 store, 직접 만든 캐시, 두 번째 fetch 래퍼를 만들지 않는다.
- 조회는 `features/<기능>/api`에 `queryOptions()`로 정의하고 queryKey도 그곳에서만 만든다. 라우트 `loader`에서 `queryClient.ensureQueryData()`로 미리 불러오고, 컴포넌트는 같은 queryOptions로 `useSuspenseQuery`를 쓴다.
- 로그인 사용자 정보는 `GET /api/auth/me` 쿼리로 얻는다. 로그인하지 않은 상태로 어떤 화면에 들어가도 로그인 화면으로 보내고, 로그인하면 원래 가려던 화면으로 돌아간다.
- 폴링은 `setInterval` 대신 `refetchInterval`로 하고, 필요한 조건에서만 켠다. 시뮬레이션 진행 조회는 상태가 PENDING·RUNNING일 때만 폴링하고 종료되면 끈다.
- mutation이 성공하면 응답으로 캐시를 직접 갱신하거나 영향을 받는 키만 `invalidateQueries`로 무효화한다. 관계없는 캐시 전체를 무효화하지 않는다.
- `staleTime`과 재조회 정책은 데이터 성격에 맞게 명시한다. 캐시가 있는 백그라운드 조회(`isFetching`)를 최초 로딩(`isPending`)처럼 다루지 않는다.
- 로그아웃이나 계정 변경이 확인되면 이전 사용자의 요청을 취소하고 캐시를 지워서, 다른 사람의 데이터가 다시 보이지 않게 한다.

## 로딩과 낙관적 업데이트
- 제목, 내비게이션, 조회 조건 같은 화면 틀은 먼저 그리고, Suspense와 Skeleton은 실제로 기다리는 데이터 블록(요약 카드, 차트, 표)에만 둔다. 화면 전체를 Skeleton으로 덮지 않는다.
- Skeleton은 실제 컴포넌트와 같은 크기와 배치로 만든다. 조회 조건을 바꾸는 동안에는 기존 결과를 유지하고 결과 영역에만 진행 표시를 한다.
- 되돌릴 수 있는 편집은 TanStack Query mutation으로 낙관적 업데이트를 하고, 실패하면 해당 항목만 되돌린다. 늦게 도착한 이전 응답이 더 최신 편집을 덮지 않게 한다.
- 시뮬레이션 실행, 모델 상태 전환, 연결 테스트처럼 서버 검증과 외부 호출이 필요한 동작은 낙관적 표시로 확정하지 않는다. 실행 버튼은 확인창 뒤 누르는 즉시 비활성화한다.
- 연속 입력은 모아서 저장하고 같은 대상의 요청은 순서대로 보낸다. 저장 중이라는 이유로 관계없는 버튼을 비활성화하지 않는다.

## API 함수와 타입
- API 타입은 백엔드 OpenAPI 문서(`openapi.json`)에서 `openapi-typescript`로 생성하고, 요청은 생성 타입과 연결된 `openapi-fetch` 클라이언트로 보낸다. 응답 필드를 추측해 만든 타입을 추가하지 않는다.
- 생성 타입 위에 `as`로 다른 타입을 덮어씌우지 않는다. 화면에 필요한 부분은 `Pick`, `Omit`으로 파생한다.
- 우리 API가 아닌 외부 입력(URL 검색 파라미터, `localStorage`, 외부 서비스 응답)은 `unknown`으로 받아 Zod로 검증한다. TanStack Router의 검색 파라미터는 `validateSearch`에 Zod 스키마를 넘겨 검증한다.
- 화면 전용 상태를 API 계약 타입에 넣지 않는다.

## 폼
- 새 폼(예산, 구독료, 모델 등록, 시뮬레이션 입력)은 React Hook Form, Zod, `@hookform/resolvers`의 `zodResolver`로 만든다.
- 폼 값 타입은 스키마에서 파생한다. 입력 중인 값은 `z.input`, 검증과 변환이 끝난 제출값은 `z.output`을 쓰고 `useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>`처럼 구분한다.
- 별도 요구가 없으면 검증은 제출할 때만 한다(`mode: "onSubmit"`, `reValidateMode: "onSubmit"`). 입력 중에 오류를 새로 띄우지 않는다.
- `<form>`에는 `noValidate`를 붙여 브라우저 기본 검증 대신 같은 스키마 검증을 쓴다.
- 입력이 불완전하다는 이유로 제출 버튼을 막지 않는다. 사용자가 제출해야 어떤 필드가 틀렸는지 알 수 있다. 단 시뮬레이션 실행 버튼은 모델 수 2~4개 조건을 어기면 비활성화한다.
- 오류 문구는 한국어로 쓰고 내부 코드, 영문 기본 메시지, 사용자가 입력한 값을 노출하지 않는다. 오류는 사용자가 고칠 수 있는 위치에 표시한다.
- 클라이언트 검증은 사용자 편의를 위한 것이다. 백엔드 검증을 대신하지 않는다.

## 디자인 기준 (필수)
- 화면을 만들거나 고치기 전에 `docs/design/`(TDS 참고 값, 토큰과 데스크톱 규격)을 먼저 읽는다. 이 규칙은 이 문서의 다른 UI 규칙보다 우선한다.
- 디자인 시스템은 TDS(토스 디자인 시스템)를 참고해 직접 만든다. TDS 패키지는 설치하지 않는다. 값은 TDS 공식 문서와 앱인토스 UI Kit에서 가져와 `docs/design/tds-reference.md`에 출처와 확인 날짜를 붙여 정리한다. 이 문서와 UI Kit 파일은 저장소에 올리지 않고(`.gitignore`) 팀에 따로 공유한다.
- 색, 글자 크기, 모서리는 `@theme`에 정의한 토큰만 쓴다(`docs/design/tokens.md`). 간격과 그림자는 Tailwind 기본 값을 쓴다.
- TDS 값은 모바일 기준이므로 데스크톱(1280px 이상)에 맞게 조정한다. TDS에 없는 요소(여러 열 표, 기간 선택, 사이드바, 마우스 올림·포커스 상태)는 같은 토큰으로 만들고, 정한 규격을 `docs/design/tokens.md`에 적는다.
- UX와 화면 문구는 토스가 공개한 디자인·라이팅 원칙(toss.tech, 토스피드)을 따른다. 모든 화면에서 지킬 것은 아래와 같다.
  - 화면마다 강조하는 주된 버튼은 하나만 둔다. 확인창은 되돌릴 수 없거나 비용이 드는 동작에만 둔다.
  - 문장은 해요체로 짧게 쓴다. 표 머리글, 라벨, 배지는 명사로, 버튼은 동사로 쓴다. 두 버튼 중 물러나는 쪽은 "닫기"다.
  - 빈 상태와 오류 문구는 무슨 일인지와 다음에 할 일을 함께 알려 준다. 예: "불러오지 못했어요. 다시 시도해 주세요." + [다시 시도]
  - 상태 값 같은 내부 코드명(`UNKNOWN`, `CUSTOMER_SERVICE`)을 화면에 쓰지 않고 "미확인", "고객 사용"처럼 바꿔 쓴다.
- 비용 표기, 실행 상태와 비용 상태 배지, 빈 상태와 오류 상태 구분 같은 "무엇을 보여 주는가"는 위 "이 제품에서 지켜야 하는 것"을 따른다.
- TDS 자료와 `docs/design/`으로 확인할 수 없는 디자인 결정은 임의로 정하지 않는다. 보고에 적고 사용자에게 묻는다.

## UI
- 새 UI는 `shared/components/ui`에서 먼저 찾고(variant 확장 우선), 없을 때만 디자인 원칙과 토큰으로 새로 만든다.
- 스타일은 Tailwind 유틸리티와 `@theme`에 정의한 디자인 토큰만 쓴다. CSS Module 같은 별도 스타일 체계를 추가하지 않고, inline style은 실행 중에 계산한 값에만 쓴다.
- 의미에 맞는 HTML 요소와 `label`을 쓰고 키보드로 조작할 수 있게 만든다. 디자인 시안과 접근성이 충돌하면 접근성을 우선한다.
- 숫자는 항상 `tabular-nums`로 표시한다. 금액, Token, 건수는 오른쪽 정렬이다.

## 환경변수와 보안
- `import.meta.env.VITE_*` 값은 빌드 결과에 그대로 들어가 누구나 볼 수 있다. 비밀값과 서버 인증정보를 넣지 않는다.
- 인증 토큰을 `localStorage`나 JavaScript 변수에 저장하지 않는다. 백엔드가 설정한 `HttpOnly` 쿠키를 그대로 쓴다.
- 개발 중에는 Vite `server.proxy`로 API를 같은 출처처럼 호출해 운영과 같은 쿠키 조건을 유지한다.
- 내부 오류, 토큰, 개인정보, Prompt 원문을 화면 밖(콘솔, 로그)에 출력하지 않는다.

## 테스트
- 루트 `CLAUDE.md`의 TDD 규칙은 판단이나 동작이 있는 코드에 적용한다. 대상은 `lib` 함수, 값에 따라 보여 주는 것이 달라지는 컴포넌트(비용·상태 표시 등), 라우팅과 URL 검색 파라미터, 폼이다. 받은 값을 그대로 그리기만 하는 컴포넌트(제목, 카드 틀, 버튼 모양)에는 테스트를 두지 않고, 판단이 생기면 그때 테스트를 먼저 쓴다.
- Vitest로 `lib`의 판단과 변환, 폼 스키마, 상태 전이, 회귀 버그를 검증한다. 기본 환경은 Node이고, DOM이 필요한 파일에만 `// @vitest-environment jsdom`을 붙인다.
- 컴포넌트 동작은 Testing Library로 사용자가 보는 텍스트와 역할을 기준으로 검사한다. 비용 표시 컴포넌트는 확정·추정·미확인 세 경우를 모두 검사한다.
- 제품 코드에 테스트용 분기나 Mock 계층을 넣지 않는다.
- 실제 백엔드와 연결해 확인하지 않았으면 연동 성공으로 보고하지 않는다.
