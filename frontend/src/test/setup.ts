import { configure } from "@testing-library/react";

// 재설치 직후처럼 캐시가 없거나 CI 장비가 느리면 지연 로딩되는 화면이 기본 대기 시간 1초를 넘길 수 있다.
const ASYNC_UTIL_TIMEOUT_MS = 5_000;

configure({ asyncUtilTimeout: ASYNC_UTIL_TIMEOUT_MS });
