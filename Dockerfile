FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml .
COPY README.md .

RUN uv pip install --system -e .

COPY agent/ agent/
COPY api/ api/
COPY ui/ ui/
COPY db/ db/
COPY evals/ evals/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]