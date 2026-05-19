FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data reports \
    && useradd --create-home --shell /bin/sh aei \
    && chown -R aei:aei /app
USER aei

CMD ["python", "-m", "integration.coordinator", "--config", "config/corridor_config.yaml", "--duration", "3600", "--output", "reports/container_metrics.json"]
