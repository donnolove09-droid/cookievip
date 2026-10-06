FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium && playwright install-deps chromium

COPY . .

ENV PORT=8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "-k", "gthread", "--threads", "4", "--timeout", "300", "web:app"]
