# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application file
COPY app.py vprotect_exporter.py

# Expose the Prometheus metrics port
EXPOSE 9176

# Run the exporter
CMD ["python", "vprotect_exporter.py"]
