FROM python:3.11-slim

# Instalar dependencias del sistema incluyendo libX11
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libx11-dev \
    libx11-6 \
    libopenblas-dev \
    liblapack-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p backend/photos backend/captures

EXPOSE 8000

CMD cd backend && uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
