# Dockerfile: 构建 API 与 document_jobs Worker 共用的 P0 后端镜像。
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY app /app/app
COPY scripts /app/scripts
COPY template /app/template
COPY template_configs /app/template_configs
COPY config.py run_api.py run_worker.py run_document_worker.py sitecustomize.py /app/

RUN mkdir -p /app/data \
    && useradd --create-home --shell /usr/sbin/nologin md2word \
    && chown -R md2word:md2word /app/data

USER md2word

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
