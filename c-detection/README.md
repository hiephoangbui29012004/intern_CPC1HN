# C Camera Stream

A Python project for camera streaming functionality.

## Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution)

## Setup with Miniconda

### 1. Install Miniconda

If you don't have Miniconda installed, download and install it from the [official website](https://docs.conda.io/en/latest/miniconda.html).

**For macOS:**

```bash
# Intel Macs
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
bash Miniconda3-latest-MacOSX-x86_64.sh

# Apple Silicon Macs (M1/M2)
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh
```

**For Linux:**

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**For Windows:**
Download the installer from the [Miniconda website](https://docs.conda.io/en/latest/miniconda.html) and run it.

### 2. Create the Environment

Navigate to the project directory and create the conda environment using the provided environment file:

```bash
cd /path/to/c-camera-stream
conda env create -f enviroment.yml
```

### 3. Activate the Environment

```bash
conda activate camera-stream
```

### 4. Verify Installation

Check that the environment is properly set up:

```bash
python --version
conda list
```

## Running the Project

Once the environment is activated, you can run the main script:

```bash
python src/main.py
```

## Environment Management

### Updating the Environment

If you need to update the environment with new dependencies:

```bash
conda env update -f enviroment.yml
```

### Deactivating the Environment

When you're done working on the project:

```bash
conda deactivate
```

### Removing the Environment

To completely remove the environment:

```bash
conda env remove -n camera-stream
```

## Project Structure

```
c-camera-stream/
├── .dockerignore           # Docker ignore file
├── .env                    # Environment variables (not in git)
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore file
├── .vscode/               # VS Code configuration
├── Dockerfile             # Docker container configuration
├── README.md              # This file
├── docker-compose.yml     # Docker Compose configuration
├── enviroment.yml         # Conda environment specification
├── logs/                  # Application logs directory
└── src/                   # Source code directory
    ├── __init__.py        # Python package initialization
    ├── main.py           # Main application entry point
    ├── certs/            # SSL certificates directory
    │   └── ca.crt        # Certificate authority certificate
    └── kafka/            # Kafka-related modules
        ├── __init__.py   # Kafka package initialization
        └── camera_stream_producer.py  # Kafka producer for camera streams
```

## Dependencies

This project uses Python 3.13 and includes the following key dependencies:

- confluent-kafka (2.11.0) - Apache Kafka client
- Various conda packages for core functionality

For a complete list of dependencies, see `enviroment.yml`.
