FROM ubuntu:latest

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install curl python3.10 pip git -y

ENV POETRY_HOME=/usr/local/share/pypoetry
ENV POETRY_VIRTUALENVS_CREATE=false
RUN curl -sSL https://install.python-poetry.org | python3 -

RUN mkdir -p /ofscraper/app
WORKDIR /ofscraper/app
COPY /pyproject.toml ./
COPY /poetry.lock ./
COPY /.git ./.git

RUN pip install dunamai

COPY / .

RUN /usr/local/share/pypoetry/bin/poetry version $(dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\d+)")
RUN /usr/local/share/pypoetry/bin/poetry install

WORKDIR /ofscraper

ENTRYPOINT ["ofscraper", "--config", "/ofscraper/config/config.json"]

VOLUME /ofscraper/config /ofscraper/bin /ofscraper/data
