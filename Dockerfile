FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium is required by the UI test stage (Playwright).
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8080

CMD ["python", "cloud_start.py"]
