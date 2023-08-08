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
RUN /root/.local/bin/poetry version $(dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\d+)")
RUN /root/.local/bin/poetry install
ENV PATH="$PATH:/root/ofscraper/.venv/bin/"
# debian / ubuntu
RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" docker
RUN USER=ofscraper && \
    GROUP=ofscraper && \
    curl -SsL https://github.com/boxboat/fixuid/releases/download/v0.5.1/fixuid-0.5.1-linux-amd64.tar.gz | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\n" > /etc/fixuid/config.yml
USER docker:docker
WORKDIR /home/ofscraper
ENTRYPOINT ["fixuid"]
CMD ["/root/ofscraper/.venv/bin/ofscraper"]
