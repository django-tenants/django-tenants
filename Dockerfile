FROM ubuntu:16.04
MAINTAINER Przemek Kamiński <cgenie@gmail.com>

RUN apt-get update && apt-get -y upgrade

RUN apt-get -y install postgresql libpq-dev postgresql-client postgresql-client-common python3-pip git netcat

VOLUME /code
WORKDIR /code
