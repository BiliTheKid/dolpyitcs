FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY dashboard.html .
COPY public/ ./public/

# Create data directory
RUN mkdir -p /data

# Set environment variables
ENV PORT=8080
ENV DATA_DIR=/data

EXPOSE 8080

# Run the server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
