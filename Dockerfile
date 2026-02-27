# ── Builder stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Final stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS final

LABEL maintainer="PDE Africa" \
      version="1.0.0" \
      description="Age Calculator Strands Agent on AWS AgentCore"

# MODEL_ARN must be supplied at runtime — never bake credentials into the image.
# Example: docker run -e MODEL_ARN=arn:aws:bedrock:... agent:local
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY --from=builder /install /usr/local

RUN useradd --uid 1000 --no-create-home --shell /bin/false agentuser

COPY --chown=agentuser:agentuser age_calculator/ ./age_calculator/
COPY --chown=agentuser:agentuser main.py .

USER agentuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import age_calculator; print('ok')" || exit 1

ENTRYPOINT ["python", "main.py"]
