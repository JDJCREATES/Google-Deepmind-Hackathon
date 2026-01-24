# FINAL ROOT DOCKERFILE - CACHE BUST 3
# This allows Cloud Run to build from root without "Context Directory" settings.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy from the DEEP subfolder structure
# "shift-intelligence-system/linewatch-ai-backend"
COPY shift-intelligence-system/linewatch-ai-backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app source code
COPY shift-intelligence-system/linewatch-ai-backend/app ./app

# Expose port (Cloud Run defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Command to run the application
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
