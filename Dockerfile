# Georgian RAG API - Production Dockerfile
# Multi-stage build for optimized image size

#  builder
FROM python:3.10-slim AS builder

# install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# set working directory
WORKDIR /app

# copy requirements
COPY requirements.txt .

# install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# download NLTK data
RUN python -c "import nltk; nltk.download('stopwords', download_dir='/root/nltk_data'); nltk.download('punkt', download_dir='/root/nltk_data')"

# runtime
FROM python:3.10-slim

# install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# create non-root user
RUN useradd -m -u 1000 raguser && \
    mkdir -p /app && \
    chown -R raguser:raguser /app

# set working directory
WORKDIR /app

# copy Python dependencies from builder
COPY --from=builder /root/.local /home/raguser/.local

# copy NLTK data from builder
COPY --from=builder /root/nltk_data /home/raguser/nltk_data

# copy application code
COPY --chown=raguser:raguser . .

# switch to non-root user
RUN mkdir -p /home/raguser/.cache/huggingface/hub && \
    chown -R raguser:raguser /home/raguser/.cache
USER raguser

# set NLTK data path
ENV NLTK_DATA=/home/raguser/nltk_data

# Add local bin to PATH
ENV PATH=/home/raguser/.local/bin:$PATH

# expose port
EXPOSE 8000

# health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# run application
CMD ["python", "fastapi_dashboard.py"]
