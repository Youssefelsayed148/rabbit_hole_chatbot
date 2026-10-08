FROM python:3.12-slim AS runtime
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY widget.js demo.html ./
RUN useradd -m rag && chown -R rag /srv
USER rag
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=180s --retries=12 CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://localhost:8000/health', timeout=2))['status'] == 'ok'"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

FROM runtime AS tests
USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests ./tests
COPY pytest.ini docker-compose.yml .
RUN mkdir -p /results && chown -R rag /srv /results
USER rag
ENTRYPOINT ["python", "-m", "scripts.container_tests"]

# Default builds remain the small production image.
FROM runtime AS service

