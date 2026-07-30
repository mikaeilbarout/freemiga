FROM python:3.12-slim

WORKDIR /app

# libpq-dev + gcc: needed to build psycopg2 (Postgres driver)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p app/static/uploads/banners \
    && chmod +x entrypoint.sh

EXPOSE 8001

CMD ["./entrypoint.sh"]
