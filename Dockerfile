# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas para psycopg2 y Selenium (sin navegador aquí)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    chromium \
    chromium-driver \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

ENV CHROME_BIN=/usr/bin/chromium
ENV PATH="/usr/lib/chromium:${PATH}"

# El comando real lo define docker-compose (scheduler + API)
CMD ["python", "api/json_api_server.py"]
