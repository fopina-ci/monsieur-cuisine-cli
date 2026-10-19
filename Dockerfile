# Container image for the Monsieur Cuisine CLI.
FROM python:3.10-slim AS base

# --- builder
FROM base AS builder
WORKDIR /app
COPY monsieur_cuisine_cli /src/monsieur_cuisine_cli
COPY pyproject.toml README.md /src/
RUN pip install --target=/app /src

# --- main
FROM base
COPY --from=builder /app /app
ENV PYTHONPATH=/app

ENTRYPOINT ["python3", "-m", "monsieur_cuisine_cli"]
