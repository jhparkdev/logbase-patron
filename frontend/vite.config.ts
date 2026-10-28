import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// fastapi dev 기본 포트. 배포에서는 nginx가 /api를 backend로 넘긴다.
const DEV_BACKEND_URL = "http://localhost:8000";

export default defineConfig({
  plugins: [
    // TanStack Router 문서: 라우터 플러그인은 @vitejs/plugin-react보다 먼저 와야 한다.
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  server: {
    proxy: { "/api": DEV_BACKEND_URL },
  },
});
