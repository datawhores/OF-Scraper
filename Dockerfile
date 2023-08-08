RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install curl python3.11 pip git python3.11-venv -y

RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN USER=ofscraper && \
    GROUP=ofscraper && \
    curl -SsL https://github.com/boxboat/fixuid/releases/download/v0.5.1/fixuid-0.5.1-linux-amd64.tar.gz | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\n" > /etc/fixuid/config.yml
USER ofscraper:ofscraper

ENV POETRY_HOME=/home/ofscraper/local/share/pypoetry
RUN mkdir -p /home/ofscraper/app
WORKDIR /home/ofscraper/app
COPY /pyproject.toml ./ 
COPY --chown=ofscraper:ofscraper /poetry.lock ./
COPY --chown=ofscraper:ofscraper /.git ./.git
COPY --chown=ofscraper:ofscraper / .
RUN rm -rf .venv
RUN curl -sSL https://install.python-poetry.org | python3.11 -

USER ofscraper:ofscraper
RUN python3.11 -m venv .venv
RUN ${POETRY_HOME}/bin/poetry install --with build
RUN ${POETRY_HOME}/bin/poetry version $(${POETRY_HOME}/bin/poetry run dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\w+)")

ENV PATH="$PATH:/home/ofscraper/app/.venv/bin/"
WORKDIR /home/ofscraper/app
ENTRYPOINT ["fixuid","-q"]
