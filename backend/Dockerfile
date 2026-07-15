FROM python:3.11-slim

WORKDIR /app

# Install system deps for OCR (optional — only needed if using tesseract)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     tesseract-ocr tesseract-ocr-eng poppler-utils \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create upload directory
RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]