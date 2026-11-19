FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV IMS_DB_ENABLED=false

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install \
    --no-cache-dir \
    --upgrade pip \
    && python -m pip install \
    --no-cache-dir \
    -r requirements.txt

COPY app ./app
COPY knowledge_base ./knowledge_base
COPY opsresolve_ai_app.py .
COPY .env.example .

RUN mkdir -p /app/data

EXPOSE 8610

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8610/health', timeout=4)"

CMD [
    "python",
    "-m",
    "uvicorn",
    "opsresolve_ai_app:application",
    "--host",
    "0.0.0.0",
    "--port",
    "8610"
]