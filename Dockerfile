# ==========================================
# STAGE 1: THE BUILDER (Compiling the heavy ML wheels)
# ==========================================
FROM python:3.10-slim as builder

WORKDIR /build

# Install C++ compilers required to build LightGBM and GeoAlchemy2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Reach into your specific server folder
COPY server/requirements.txt .

# Force pip to download the CPU-only version of PyTorch (saves ~2GB)
# and compile everything into standalone binary wheels
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# ==========================================
# STAGE 2: THE RUNNER (Your final, lightweight image)
# ==========================================
FROM python:3.10-slim

# Keep your strict Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install only the runtime C-libraries required by PostGIS/psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Grab the pre-compiled binaries from the Builder stage
COPY --from=builder /build/wheels /wheels
COPY server/requirements.txt .

# Install the dependencies instantly without downloading anything
RUN pip install --no-cache /wheels/*

# Keep your explicit Redis install (though adding it to requirements.txt is safer!)
RUN pip install --no-cache-dir redis

# Finally, copy your application logic into the container
COPY server/ .

# Note: The CMD instruction will be injected by your Kubernetes deployment files 
# depending on whether this container is acting as the API node or the Celery worker.