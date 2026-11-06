# docker/prod/Dockerfile: 构建生产环境 API 与 document_jobs Worker 共用镜像。
FROM docker.io/library/python:3.11.18-slim-trixie@sha256:b701198cb708b68d9413ca67d6311bd97c9389a2c5fe4da0511fc652642366cd AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# poppler-utils 提供 pdfinfo/pdftoppm，供缺表格 HTML 时从源 PDF 裁切占位图。
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/locks/cp311-linux-amd64.txt /tmp/requirements.lock
COPY requirements/wheels/ /tmp/wheels/
RUN python -m pip --isolated install --no-index --find-links=/tmp/wheels \
    --require-hashes --only-binary=:all: -r /tmp/requirements.lock \
    && rm -rf /tmp/wheels

COPY app /app/app
COPY scripts /app/scripts
COPY resources /app/resources
COPY sitecustomize.py /app/

RUN mkdir -p /app/var /app/deploy \
    && useradd --create-home --shell /usr/sbin/nologin md2word \
    && chmod -R a+rX /app/app /app/scripts /app/resources \
    && chmod a+r /app/sitecustomize.py \
    && chown -R md2word:md2word /app/var /app/deploy

USER md2word

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
