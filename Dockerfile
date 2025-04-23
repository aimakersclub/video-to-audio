FROM python:3.9-slim

WORKDIR /app

# Instalar FFmpeg e dependências para MoviePy e Whisper
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    git \
    cmake \
    pkg-config \
    libsndfile1 \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verificar a instalação do FFmpeg
RUN ffmpeg -version

# Criar diretório para cache do modelo Whisper
RUN mkdir -p /root/.cache/whisper

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create temp directory for storing files
RUN mkdir -p /tmp/audio_extractor

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]