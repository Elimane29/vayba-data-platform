# Vayba · one image for every pipeline task: ingestion (ingestion/run.py) and dbt.
# Build from the repository root:
#   docker build -f docker/pipeline/Dockerfile -t vayba-pipeline:1.0.0 .
FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer stays cached while requirements.txt does not change
COPY requirements.txt .
RUN pip install -r requirements.txt

# Then the code, which changes often. No key, no .env: secrets are mounted at run time.
COPY ingestion/ ingestion/
COPY dbt/ dbt/

# Do not run as root
RUN useradd --create-home --uid 1000 vayba && chown -R vayba /app
USER vayba

CMD ["python", "ingestion/run.py", "--help"]
