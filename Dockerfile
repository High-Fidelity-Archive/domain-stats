FROM ubuntu:18.04

RUN apt-get update -y
RUN apt-get install -y python-pip
RUN pip install influxdb requests
RUN mkdir /app

COPY . /app

CMD /app/domain-stats.py
