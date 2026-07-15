FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

EXPOSE 8080

# Default entrypoint — overridden in service.yaml to wrap with MicroEnforcer
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "80", "--timeout", "120", "app:app"]
