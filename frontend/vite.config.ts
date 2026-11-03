/// <reference types="vitest/config" />
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// fastapi dev 기본 포트. 배포에서는 nginx가 /api를 backend로 넘긴다.
const DEV_BACKEND_URL = "http://localhost:8000";
// 한 테스트가 화면 대기를 여러 번 해도 setup.ts의 대기 시간보다 먼저 끊기지 않게 넉넉히 둔다.
const TEST_TIMEOUT_MS = 15_000;
// 16코어 PC의 기본값에서는 한 테스트가 0.3초에서 9초대까지 느려졌고 전체 시간도 4개일 때보다 길었다.
const TEST_MAX_WORKERS = 4;

export default defineConfig({
  plugins: [
    // TanStack Router 문서: 라우터 플러그인은 @vitejs/plugin-react보다 먼저 와야 한다.
    // 코드 분할은 빌드에서만 켠다. 테스트에서 켜면 화면 컴포넌트가 첫 렌더링 때 동적 import로 불려와
    // 테스트 파일마다 첫 테스트가 그 변환·로딩 시간을 화면 대기 시간 안에서 치르고, 느린 CI에서 대기를 넘긴다.
    tanstackRouter({ target: "react", autoCodeSplitting: !process.env.VITEST }),
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  server: {
    proxy: { "/api": DEV_BACKEND_URL },
  },
  test: {
    maxWorkers: TEST_MAX_WORKERS,
    setupFiles: ["./src/test/setup.ts"],
    testTimeout: TEST_TIMEOUT_MS,
  },
});
