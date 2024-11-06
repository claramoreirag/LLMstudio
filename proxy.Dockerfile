
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

# Install required tools and Poetry
RUN apt-get clean && apt-get update && \
    apt-get install -y curl && \
    curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry && \
    poetry config virtualenvs.create false

# Set work directory
WORKDIR /proxy

# Copy only pyproject.toml and poetry.lock to install dependencies first
COPY ./libs/proxy/pyproject.toml ./libs/proxy/poetry.lock ./
RUN poetry install --no-root

# Copy the remaining application code
COPY ./libs/proxy /proxy

# Set PYTHONPATH
ENV PYTHONPATH=/proxy

# Run the application
CMD ["python", "llmstudio_proxy/server.py"]


