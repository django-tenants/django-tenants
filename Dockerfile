FROM python:3.10
#ENV PYTHONUNBUFFERED 1
RUN mkdir /code
VOLUME /code
WORKDIR /code
COPY requirements.txt /code/
RUN apt-get update && apt-get -y install postgresql libpq-dev postgresql-client postgresql-client-common python3-pip git netcat-traditional
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code/