FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy project files
COPY . .

# Create output directory
RUN mkdir -p output

# Expose port
EXPOSE 5000

# Set environment variable for Flask
ENV FLASK_APP=ui.app
ENV PYTHONUNBUFFERED=1

# Run with gunicorn (300s timeout for long pipeline operations)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "2", "ui.app:app"]
