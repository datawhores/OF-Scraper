FROM ubuntu:latest
RUN mkdir -p /root/.config
RUN mkdir -p /root/Data
RUN mkdir -p /root/Data/ofscraper
RUN mkdir -p /root/ofscraper
WORKDIR /root
COPY / ./ofscraper
WORKDIR ./ofscraper
RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get install curl python3 pip git -y
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN pip install dunamai
RUN /root/.local/bin/poetry version $(dunamai from git --format "{base}" --pattern default-unprefixed)
RUN /root/.local/bin/poetry install
WORKDIR /root
ENTRYPOINT ["ofscraper"]
