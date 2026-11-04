# Builder | 의존성 설치 및 프로젝트 빌드
FROM python:3.14-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv

# Python 및 uv 환경 설정
# 기반 이미지의 python 사용, 캐시 마운트 환경에서 패키지 복사, 개발 의존성 제외
ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /app

# 의존성 파일만 먼저 복사하여 Docker 레이어 캐시 활용
COPY pyproject.toml uv.lock ./

# 의존성만 설치해 빌드 캐시 활용
# --locked: uv.lock이 pyproject.toml과 어긋나면 빌드를 실패시킨다.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

# 프로젝트 코드 복사
COPY . /app

# 프로젝트 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


# Runtime | 실제 어플리케이션 실행
FROM python:3.14-slim-trixie

# 컨테이너가 침해돼도 root 권한을 갖지 않도록 전용 사용자로 실행한다.
RUN useradd --system --uid 10001 --no-create-home app

WORKDIR /app

# Builder에서 설치한 의존성, 소스코드 복사
COPY --from=builder /app /app

# 로컬 이미지 저장소 및 파일 권한 설정
RUN mkdir -p /app/uploads \
    && chown app:app /app/uploads

# 가상환경 실행 경로 및 로그 지연되지 않도록 설정
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app

# 컨테이너가 사용하는 포트 (Cloud Run 기본 포트)
EXPOSE 8080

# FastAPI 실행(PORT 환경변수 지원)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
