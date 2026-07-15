FROM python:3.11-slim

WORKDIR /app

# System deps for document ingestion:
#   tesseract-ocr  → OCR text extraction from scanned images
#   poppler-utils  → PDF → image rasterization (pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Entrypoint runs `alembic upgrade head` then serves. Pre-create upload dirs.
RUN chmod +x docker-entrypoint.sh \
    && mkdir -p /app/uploads /app/uploads/_chunks

# Drop root for runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
