# Builder | 의존성 설치 및 정적 파일 빌드
FROM node:24-slim AS builder

# CI와 동일한 pnpm 메이저 버전 사용
RUN npm install -g pnpm@12

WORKDIR /app

# 의존성 파일만 먼저 복사해 Docker 레이어 캐시 활용
COPY package.json pnpm-lock.yaml ./

# 잠금 파일을 기존으로 의존성 설치
# --frozen-lockfile: pnpm-lock.yaml이 package.json과 어긋나면 빌드 실패
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile

# 프로젝트 코드 복사
COPY . .

# React 정적 파일 빌드
RUN pnpm build

# Runtime | 정적 파일 제공 및 /api 프록시
FROM nginx/nginx-unprivileged:stable-alpine

# nginx 설정 템플릿 복사
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# 빌드 결과물 복사
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx 포트 및 API 프록시 설정
ENV PORT=8080 \
    BACKEND_URL=http://backend:8080 \
    BACKEND_HOST=backend \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_FILTER="^(PORT|BACKEND_URL|BACKEND_HOST|NGINX_LOCAL_RESOLVERS)$"

# Cloud Run 기본 포트
EXPOSE 8080
