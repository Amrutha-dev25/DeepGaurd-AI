FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (OpenCV requires libgl1, libglib2.0-0)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy dependency files
COPY pyproject.toml .
# No uv.lock exists in this scaffold yet, but if it did we would copy it

# Install dependencies into system python via uv
RUN uv pip install --system -e .

# Copy application code
COPY app/ ./app/
COPY pyproject.toml ./

# Expose backend API and MCP Server ports
EXPOSE 8000 8090

# Default command starts the FastAPI server
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
