FROM ubuntu:14.04
MAINTAINER Przemek Kamiński <cgenie@gmail.com>

RUN apt-get update && apt-get -y upgrade

RUN apt-get -y install python-pip python-psycopg2 git

WORKDIR /code

ADD . /code

RUN python setup.py develop
