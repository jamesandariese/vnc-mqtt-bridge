FROM alpine:latest

RUN apk add python3 py3-pip curl mosquitto-clients

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY grab.py /grab.py

WORKDIR /

CMD ["python3", "/grab.py"]

COPY health.sh /health.sh
HEALTHCHECK CMD /health.sh
