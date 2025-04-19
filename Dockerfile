FROM python:3.11-slim

WORKDIR /app
COPY main.py .

RUN pip install requests paho-mqtt

VOLUME ["/data"]

CMD ["python", "main.py"]
