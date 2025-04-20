FROM python:3.11-slim

WORKDIR /app
COPY main.py requirements.txt .

RUN pip install -r requirements.txt

VOLUME ["/data"]

CMD ["python", "-u", "main.py"]
