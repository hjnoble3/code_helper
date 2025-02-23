# dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from src/
COPY src/ /app/

# Expose Gradio port
EXPOSE 7860

# Command to run the Gradio app
CMD ["python", "gradio_interface.py"]