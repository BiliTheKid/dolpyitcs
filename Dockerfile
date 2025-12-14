FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for Prisma CLI - needed for db push)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Prisma schema
COPY prisma ./prisma

# Generate Prisma Python client
RUN python -m prisma generate

# Copy application files
COPY server.py .
COPY dashboard.html .
COPY public/ ./public/

# Set environment variables
ENV PORT=8080

EXPOSE 8080

# Run database migrations and start server
# Use shell form to allow || fallback if db push fails
CMD sh -c "npx prisma db push --skip-generate || echo 'DB push failed, continuing...' && uvicorn server:app --host 0.0.0.0 --port 8080"
