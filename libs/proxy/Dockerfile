
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

ARG PRODUCT_ID
ARG ISSUER_FOOTPRINT
ENV PROD_ID=$PRODUCT_ID
ENV ISSUER_FT=$ISSUER_FOOTPRINT

# Install required tools and Poetry
RUN apt-get clean && apt-get update && \
    apt-get install -y curl && \
    curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry && \
    poetry config virtualenvs.create false

# Set work directory
WORKDIR /proxy

# Copy only pyproject.toml and poetry.lock to install dependencies first
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --no-root --no-dev

# Copy the remaining application code
COPY . /proxy

# Set PYTHONPATH
ENV PYTHONPATH=/proxy

RUN pip install -e .

# Run the application
EXPOSE 50001
CMD ["llmstudio-proxy", "server"]


