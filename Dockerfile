FROM python:3.12-slim

WORKDIR /app

COPY requirements-api.txt ./requirements-api.txt
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/api ./src/api
COPY sumo/bengaluru_osm/bengaluru_model.py ./sumo/bengaluru_osm/bengaluru_model.py
COPY docker_entrypoint.py ./docker_entrypoint.py

ENV QUEUE_MODEL_PATH=/models/bengaluru_queue_hurdle_v1_2026-11.joblib \
    QUEUE_MODEL_METADATA_PATH=/app/src/api/bengaluru_deployment_metadata.json \
    QUEUE_MODEL_SHA256=167b523fc8c89199f6a8bf0689475272654db96b59b8a1da9b8a9986bff0b13b \
    PORT=8000
EXPOSE 8000

RUN useradd --create-home --uid 10001 apiuser
USER apiuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT','8000'), timeout=3)"]

CMD ["python", "docker_entrypoint.py"]
