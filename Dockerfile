FROM python:3.13-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip install .

FROM python:3.13-slim-bookworm
RUN groupadd --gid 10001 msa && useradd --uid 10001 --gid msa --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin msa
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER msa
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:factory --factory --host 0.0.0.0 --port ${PORT}"]
