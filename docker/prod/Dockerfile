# docker/prod/Dockerfile: 构建生产环境 API 与 document_jobs Worker 共用镜像。
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# poppler-utils 提供 pdfinfo/pdftoppm，供缺表格 HTML 时从源 PDF 裁切占位图。
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

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
