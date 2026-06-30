FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ARG KAGGLE_USERNAME
ARG KAGGLE_KEY
RUN pip install kaggle && \
    mkdir -p /root/.kaggle && \
    echo "{\"username\":\"$KAGGLE_USERNAME\",\"key\":\"$KAGGLE_KEY\"}" > /root/.kaggle/kaggle.json && \
    chmod 600 /root/.kaggle/kaggle.json && \
    mkdir -p data && \
    kaggle datasets download -d shuyangli94/cocktails-hotaling-co -p data --unzip

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]