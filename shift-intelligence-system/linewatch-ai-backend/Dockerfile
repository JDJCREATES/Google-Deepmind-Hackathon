# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (Cloud Run defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Command to run the application
# Cloud Run injects PORT env var, we must listen on 0.0.0.0
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
