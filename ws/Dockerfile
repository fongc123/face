FROM python:3

COPY ws /app/ws

COPY requirements.txt /app/requirements.txt

COPY .env /app/.env

RUN pip install -r /app/requirements.txt

WORKDIR /app/ws

CMD ["python", "-u", "app_ws.py", "--receive", "--insert"]