FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir ".[web]" \
    && useradd --create-home --uid 10001 fillonce

USER fillonce
EXPOSE 8765
CMD ["fillonce", "serve", "--host", "0.0.0.0", "--port", "8765"]
