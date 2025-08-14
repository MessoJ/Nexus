FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip cache purge && \
    pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY app ./app

CMD ["python", "-m", "app.main"]
