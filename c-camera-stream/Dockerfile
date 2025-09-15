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
    find /opt/conda/envs/camera-stream/lib/python*/site-packages/ -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/conda/envs/camera-stream/lib/python*/site-packages/ -name "test" -exec rm -rf {} + 2>/dev/null || true

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
COPY --from=builder /opt/conda/envs/camera-stream /opt/conda/envs/camera-stream

# Set up environment paths and make conda environment available
ENV PATH="/opt/conda/envs/camera-stream/bin:$PATH"
ENV CONDA_DEFAULT_ENV=camera-stream

# Initialize conda for the environment
RUN echo "conda activate camera-stream" >> ~/.bashrc

# Set working directory
WORKDIR /app

# Copy the application source code (only what's needed)
COPY src/ ./src/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Set the default command to run your application
CMD ["python", "src/main.py"]
