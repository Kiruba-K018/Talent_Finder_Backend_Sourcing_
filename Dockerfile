FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    curl wget gnupg unzip \
    fonts-liberation libnss3 libgbm1 libasound2 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001 9001

CMD ["python", "-m", "src.main"]