FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Prisma schema and generate client
COPY prisma ./prisma
RUN prisma generate

# Copy application files
COPY server.py .
COPY dashboard.html .
COPY public/ ./public/

# Set environment variables
ENV PORT=8080

EXPOSE 8080

# Run database migrations and start server
CMD prisma db push --skip-generate && uvicorn server:app --host 0.0.0.0 --port 8080
