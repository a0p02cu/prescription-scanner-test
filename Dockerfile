FROM ubuntu:latest
MAINTAINER Abhijeet Panda
RUN apt-get update -y
RUN apt-get install ffmpeg -y
RUN apt-get install -y python3-pip python3-dev build-essential
EXPOSE 5000
EXPOSE 8000
COPY . /app
WORKDIR /app
RUN pip3 install -r requirements.txt
CMD ./run.sh
