FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire src directory to /app/src
COPY src/ ./src/

# Switch to backend directory so gunicorn finds app.py
# and Flask's static_folder="../frontend" resolves to /app/src/frontend
WORKDIR /app/src/backend

EXPOSE 5000

# Run production server with gunicorn
# --workers 2: suitable for HF cpu-basic (2 vCPU)
# --timeout 120: allow time for Gemini API + image analysis calls
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
