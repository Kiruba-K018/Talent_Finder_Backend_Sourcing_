
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including Chromium
RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    curl wget gnupg unzip \
    fonts-liberation libnss3 libgbm1 libasound2 libxss1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel before installing requirements
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements file
COPY requirements.txt ./

# Install Python dependencies (psycopg needs libpq-dev to be installed first)
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (required for Chromium automation)
RUN pip install --no-cache-dir playwright && \
    playwright install chromium && \
    playwright install-deps chromium


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver


# Copy application source code
COPY src/ ./src/

# Copy environment file if it exists
COPY .env* ./

# Expose port for FastAPI
EXPOSE 8001 9001

RUN useradd -m appuser 

USER appuser

# Run the application
CMD ["python", "-m", "src.main"]







