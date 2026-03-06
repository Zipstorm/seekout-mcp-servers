# -- Base ---------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# -- Dependencies -------------------------------------------------------
FROM base AS deps

COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# -- Development --------------------------------------------------------
FROM base AS dev

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY . .
RUN uv sync

EXPOSE 8001

CMD ["uv", "run", "python", "-m", "seekout_mcp_search"]

# -- Production ---------------------------------------------------------
FROM base AS production

COPY --from=deps /app/.venv ./.venv
COPY pyproject.toml ./
COPY seekout_mcp_search/ ./seekout_mcp_search/

RUN uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8001

CMD ["python", "-m", "seekout_mcp_search"]
