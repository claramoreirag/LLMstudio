
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

# Install required tools and Poetry
RUN apt-get clean && apt-get update && \
    apt-get install -y curl && \
    curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry && \
    poetry config virtualenvs.create false

# Set work directory
WORKDIR /tracker

# Copy only pyproject.toml and poetry.lock to install dependencies first
COPY ./libs/tracker/pyproject.toml ./libs/tracker/poetry.lock ./
RUN poetry install --no-root

# Copy the remaining application code
COPY ./libs/tracker /tracker

# Set PYTHONPATH
ENV PYTHONPATH=/tracker

# Run the application
CMD ["python", "llmstudio_tracker/server.py"]