FROM python:3-slim-stretch

RUN apt-get update \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -U pipenv pip

ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/opt/app

WORKDIR $APP_HOME

COPY Pipfile $APP_HOME
COPY Pipfile.lock $APP_HOME
RUN pipenv install --deploy --system

COPY . $APP_HOME
