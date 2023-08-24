FROM python:3

COPY flask /app/flask

COPY requirements.txt /app/requirements.txt

COPY .env /app/.env

RUN pip install -r /app/requirements.txt

WORKDIR /app/flask

CMD ["python", "app_http.py"]