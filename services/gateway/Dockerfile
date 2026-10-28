# SalesPilot 模型网关
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    GATEWAY_MODELS_FILE=/app/models.yaml

WORKDIR /app

# 先装依赖（利用缓存），只装运行依赖
# 国内网络下载 PyPI 容易超时：放宽超时、降低并发（只在构建时生效）
ARG UV_HTTP_TIMEOUT=300
ARG UV_CONCURRENT_DOWNLOADS=4
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
# 注册表随镜像复制；也可以在 docker-compose 里挂载覆盖：./services/gateway/models.yaml:/app/models.yaml:ro
COPY models.yaml ./models.yaml

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
