# Use a smaller base image - miniconda3 with slim Python
FROM continuumio/miniconda3:latest AS builder

# Set working directory
WORKDIR /app

# Copy environment file first for better Docker layer caching
COPY enviroment.yml .

# Create conda environment from environment file and clean up in single layer
RUN conda env create -f enviroment.yml && \
    conda clean -afy && \
    find /opt/conda/ -follow -type f -name '*.a' -delete && \
    find /opt/conda/ -follow -type f -name '*.pyc' -delete && \
    find /opt/conda/ -follow -type f -name '*.js.map' -delete && \
    find /opt/conda/envs/c-mask-detection/lib/python*/site-packages/ -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/conda/envs/c-mask-detection/lib/python*/site-packages/ -name "test" -exec rm -rf {} + 2>/dev/null || true

# Final stage - use miniconda3 slim for compatibility
FROM continuumio/miniconda3:latest

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Clean up conda installation and remove unnecessary packages
RUN conda clean -afy && \
    rm -rf /opt/conda/pkgs/* && \
    rm -rf /tmp/* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy only the conda environment from builder stage
COPY --from=builder /opt/conda/envs/c-mask-detection /opt/conda/envs/c-mask-detection

# Set up environment paths and make conda environment available
ENV PATH="/opt/conda/envs/c-mask-detection/bin:$PATH"
ENV CONDA_DEFAULT_ENV=c-mask-detection

# Initialize conda for the environment
RUN echo "conda activate c-mask-detection" >> ~/.bashrc

# Set working directory
WORKDIR /app

# Copy the application source code (only what's needed)
COPY src/ ./src/
COPY prisma/ ./prisma/

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Create Prisma cache directory and set proper permissions
RUN mkdir -p /home/appuser/.cache/prisma-python && \
    chown -R appuser:appuser /home/appuser/.cache

# Set environment variables for Prisma
ENV PRISMA_QUERY_ENGINE_BINARY_CACHE_DIR=/home/appuser/.cache/prisma-python
ENV PRISMA_SCHEMA_ENGINE_BINARY_CACHE_DIR=/home/appuser/.cache/prisma-python

# Give appuser write permissions to conda environment for Prisma generation
RUN chown -R appuser:appuser /opt/conda/envs/c-mask-detection

# Switch to appuser before generating Prisma client to ensure correct cache location
USER appuser

# Generate Prisma client as appuser to ensure binaries are cached in correct location
RUN prisma generate

# Switch back to root for final setup
USER root

# Set ownership of app directory
RUN chown -R appuser:appuser /app

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R appuser:appuser /app

USER appuser

# Set the default command to run your application
CMD ["python", "src/main.py"]
