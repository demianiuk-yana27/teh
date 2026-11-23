FROM python:3.10-slim

# apt-get тут працює без обмежень, бо білд образу виконується з правами root
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MALLOC_ARENA_MAX=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Kyiv

# One worker keeps the in-process lock meaningful when Cloud Run
# is configured with max-instances=1 and concurrency=1.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 3600"]
