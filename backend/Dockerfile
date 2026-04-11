FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema para trimesh/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
