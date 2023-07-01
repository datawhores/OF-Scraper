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
RUN apt-get install curl python3.10 pip git python3.10-venv -y
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN python3.10 -m venv .venv
RUN pip install dunamai
RUN /root/.local/bin/poetry version $(dunamai from git --format "{base}" --pattern default-unprefixed)
RUN /root/.local/bin/poetry install
ENV PATH="$PATH:/root/ofscraper/.venv/bin/ofscraper"
WORKDIR /root
ENTRYPOINT ["/root/ofscraper/.venv/bin/ofscraper"]
