FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/settings.py config/settings.py
COPY run.py .

EXPOSE 80

CMD ["gunicorn", "-b", "0.0.0.0:80", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "run:app"]
