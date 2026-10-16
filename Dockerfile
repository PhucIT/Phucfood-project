FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home appuser
COPY . .
RUN mkdir -p /app/data /app/uploads && chown -R appuser:appuser /app/data /app/uploads
USER appuser
ENV PHUC_DATA_DIR=/app/data PHUC_UPLOAD_DIR=/app/uploads PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--timeout", "60", "wsgi:app"]
