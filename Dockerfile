FROM python:3.12.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY src/ ./src/
RUN pip install --no-cache-dir -c requirements.lock ".[dev]"
COPY config/ ./config/
COPY sql/ ./sql/
COPY app/ ./app/
COPY .streamlit/ ./.streamlit/

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
