
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


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver


# Copy application source code
COPY src/ ./src/
# COPY chroma_data/ ./chroma_data/

# Copy environment file if it exists
COPY .env* ./

# Expose port for FastAPI
EXPOSE 8001 9001


# Run the application
CMD ["python", "-m", "src.main"]








# FROM python:3.11-slim AS builder

# # Uncomment and install system dependencies if needed
# # RUN apt-get update && apt-get install -y \
# #     chromium chromium-driver \
# #     curl wget gnupg unzip \
# #     fonts-liberation libnss3 libgbm1 libasound2 \
# #     --no-install-recommends && \
# #     rm -rf /var/lib/apt/lists/*

# # WORKDIR /app
# COPY requirements.txt .
# RUN python -m pip install --no-cache-dir -r requirements.txt

# FROM python:3.11-slim AS final

# Uncomment and install system dependencies if needed
# RUN apt-get update && apt-get install -y \
#     chromium chromium-driver \
#     curl wget gnupg unzip \
#     fonts-liberation libnss3 libgbm1 libasound2 \
#     --no-install-recommends && \
# #     rm -rf /var/lib/apt/lists/*

# ENV PYTHONUNBUFFERED=1 \
#     PYTHONDONTWRITEBYTECODE=1 \
#     CHROME_BIN=/usr/bin/chromium \
#     CHROMEDRIVER_PATH=/usr/bin/chromedriver

# WORKDIR /app
# # COPY --from=builder /app/. /app/
# COPY . .

# EXPOSE 8001 9001

# CMD ["python", "-m", "src.main"]