# 고객 서비스 호출 기록 연동 규격

고객 서비스가 OpenRouter 호출을 마칠 때마다 Patron의 기록 API로 한 건씩 보내는 규격이다. 고객 서비스는 OpenRouter를 직접 호출하고, Patron은 호출 중간에 들어가지 않는다. Patron이 멈춰도 고객 서비스의 AI 기능은 멈추지 않는다.

## 요약

| 항목 | 값 |
|---|---|
| 주소 | `POST <Patron 주소>/api/usage-records` |
| 인증 | 헤더 `X-Patron-Ingest-Token: <기록 API 전용 토큰>` (없거나 틀리면 401) |
| 본문 | JSON 한 건 (아래 필드) |
| 보내는 때 | 호출이 끝난 직후. 성공, 실패, timeout 모두 보낸다 |
| 재전송 | 같은 `request_id`로 다시 보내도 한 번만 저장된다 |

로컬 개발에서는 `http://localhost:8000/api/usage-records` 로 보내면 된다. 배포된 공개 주소는 다른 서버에서 도는 실제 고객 서비스를 연결할 때만 필요하다.

## 보내지 않는 것

- 프롬프트와 답변 원문은 보내지 않는다. 알 수 없는 필드가 있으면 요청 전체를 거절한다.
- OpenRouter Key 원문은 보내지 않는다. Patron이 Key를 등록할 때 알려 준 `key_id`만 보낸다.

## 필드

| 필드 | 필수 | 설명 |
|---|---|---|
| `request_id` | 필수 | 고객 서비스가 호출마다 직접 만드는 UUID. timeout처럼 OpenRouter 응답 id가 없는 호출도 이것으로 구분한다 |
| `openrouter_generation_id` | 선택 | OpenRouter 응답 id. 응답을 받은 경우에만 보낸다 |
| `key_id` | 필수 | Key를 등록할 때 Patron이 알려 준 숫자 ID |
| `customer_code` | 필수 | 고객 코드(예: `CUST-001`). `key_id`에 연결된 고객과 같아야 한다 |
| `task_ref` | 필수 | 고객이 돈을 내는 작업 한 건의 ID(예: 상세페이지 1건). 한 작업에서 AI를 여러 번 부르면 같은 값을 보낸다 |
| `task_type` | 필수 | 작업 종류(예: `상세페이지 생성`) |
| `model` | 필수 | 요청한 OpenRouter 모델 ID(예: `openai/gpt-4o-mini`) |
| `actual_model`, `actual_provider` | 선택 | 실제로 처리한 모델과 서버 업체. 응답을 받은 경우에만 |
| `requested_at` | 필수 | 호출을 시작한 시각. 시간대가 있는 ISO 8601(예: `2026-10-10T01:00:00Z`) |
| `completed_at` | 선택 | 호출이 끝난 시각. timeout처럼 모르면 보내지 않는다 |
| `latency_ms` | 선택 | 걸린 시간(밀리초). 없으면 `requested_at`과 `completed_at`의 차이로 계산한다 |
| `status` | 필수 | `SUCCESS`, `FAILED`, `TIMEOUT` 중 하나 |
| `error_type` | 조건부 | `FAILED`이면 필수, `TIMEOUT`이면 생략하면 `TIMEOUT_ERROR`, `SUCCESS`이면 보낼 수 없다 |
| `http_status` | 선택 | OpenRouter가 준 HTTP 상태 코드(100~599) |
| `finish_reason` | 선택 | 응답의 종료 이유 |
| `input_tokens`, `output_tokens`, `cached_tokens`, `reasoning_tokens` | 선택 | 0 이상의 정수. 캐시 토큰은 입력 토큰 이하, 추론 토큰은 출력 토큰 이하 |
| `cost_usd` | 선택 | OpenRouter 응답에 있는 비용(USD). 문자열이나 숫자 모두 가능 |

`error_type` 값: `AUTH_ERROR`, `RATE_LIMIT`, `TIMEOUT_ERROR`, `PROVIDER_ERROR`, `NETWORK_ERROR`, `INVALID_RESPONSE`, `UNSUPPORTED_INPUT`, `UNKNOWN_ERROR`.

### 비용 규칙

- 성공한 호출에 `cost_usd`가 있으면 확정 비용으로 저장한다.
- `cost_usd`가 없으면 0이 아니라 **미확인**으로 저장한다. 비용을 모를 때 0을 보내지 않는다.
- 실패와 timeout 호출은 `cost_usd`를 보내도 항상 미확인으로 저장한다.

## 응답

| 상태 | 뜻 | 고객 서비스가 할 일 |
|---|---|---|
| 201 | 새로 저장했다. 본문 `{"request_id": "...", "stored": true}` | 없음 |
| 200 | 같은 `request_id`가 이미 저장되어 있다. `stored: false` | 없음(성공으로 본다) |
| 401 | 토큰이 없거나 틀렸다 | 토큰을 확인한다. 다시 보내도 같은 결과다 |
| 409 | `openrouter_generation_id`가 다른 `request_id`의 기록에 이미 쓰였다 | 같은 호출을 다른 `request_id`로 보냈는지 확인한다 |
| 422 | 형식이 틀렸거나 모르는 `key_id`, 또는 `customer_code`가 Key와 맞지 않는다 | 보내는 값을 고친다. 그대로 다시 보내도 소용없다 |
| 5xx, 연결 실패 | Patron 쪽 문제 | 같은 `request_id`로 다시 보낸다 |

재전송은 `request_id`를 바꾸지 않고 그대로 보낸다. 처음 저장된 값은 다시 보내도 바뀌지 않는다.

## 고객 구분

- Key에 연결된 고객과 `customer_code`가 같으면 그 고객의 사용량으로 저장한다.
- 다르거나 등록되지 않은 고객 코드는 거절한다. 임의로 다른 고객에 붙이지 않는다.
- 프로젝트 Key로 들어온 고객 서비스 호출은 고객을 알 수 없으므로 **미분류**로 저장한다.

## 예시

```
curl -X POST http://localhost:8000/api/usage-records \
  -H "Content-Type: application/json" \
  -H "X-Patron-Ingest-Token: <기록 API 전용 토큰>" \
  -d '{
    "request_id": "0b9c3b64-6f61-4f8e-9d2c-2f1a9e3d7c10",
    "openrouter_generation_id": "gen-abc123",
    "key_id": 3,
    "customer_code": "CUST-001",
    "task_ref": "detail-page-1001",
    "task_type": "상세페이지 생성",
    "model": "openai/gpt-4o-mini",
    "requested_at": "2026-10-10T01:00:00Z",
    "completed_at": "2026-10-10T01:00:02Z",
    "status": "SUCCESS",
    "input_tokens": 120,
    "output_tokens": 30,
    "cost_usd": "0.000045"
  }'
```

timeout 호출은 응답 id와 완료 시각이 없다.

```
{
  "request_id": "7d2a1c58-3b44-4c0e-8e0a-5b1f2d9e6a21",
  "key_id": 3,
  "customer_code": "CUST-001",
  "task_ref": "detail-page-1001",
  "task_type": "상세페이지 생성",
  "model": "openai/gpt-4o-mini",
  "requested_at": "2026-10-10T01:00:05Z",
  "status": "TIMEOUT"
}
```

## 로컬에서 확인하는 방법

1. `docker compose up -d db`로 DB를 띄우고 백엔드를 실행한다.
2. 기록을 받을 고객·서비스·Key를 등록한다(`customer-create`, `service-create`, `key-register`). `key-register`가 알려 주는 `key_id`를 쓴다.
3. 위 예시를 `curl`로 보내고 응답이 201인지, 같은 요청을 다시 보내면 200인지 확인한다.
4. 고객 AI 사용 현황 화면에서 호출 수, 실패 수, timeout 수가 맞게 나오는지 본다.

## 아직 구현하지 않은 것 (추후 구현)

- **기록 누락 확인**: OpenRouter의 `/activity`로 Key별 하루 비용을 가져와 받은 기록의 비용 합계와 비교하고, 차이가 크면 화면에 경고로 보여 준다.
- **업체 순서 정책 API**: Patron이 모델별 업체 순서(예상 비용순)와 허용 조건(양자화 정도, 최근 가동률)을 계산해 고객 서비스에 제공한다. 고객 서비스는 이를 받아 `provider: { order: [...], allow_fallbacks: true }`로 OpenRouter를 호출한다. 정책을 받지 못하면 마지막으로 받은 정책으로 호출하고, 받은 정책이 없으면 `provider` 없이 OpenRouter 기본 라우팅으로 호출한다.
- **서비스별 토큰**: 지금은 기록 API 전용 토큰 하나로 인증한다.
