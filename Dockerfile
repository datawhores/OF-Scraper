FROM python:3.11 as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.7.1

WORKDIR /app

RUN python -m ensurepip --upgrade

FROM base as builder

RUN pip3 install "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY poetry.lock pyproject.toml ./
RUN poetry export -f requirements.txt | /venv/bin/pip --no-cache-dir install -r /dev/stdin

COPY . .
RUN  pip install dunamai
RUN poetry version $(poetry run dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\w+)")
RUN poetry build && /venv/bin/pip install dist/*.whl

FROM base as final

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:${PATH}" \
    VIRTUAL_ENV="/venv"

RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN USER=ofscraper && \
    GROUP=ofscraper && \
    curl -SsL https://github.com/boxboat/fixuid/releases/download/v0.5.1/fixuid-0.5.1-linux-amd64.tar.gz | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\npaths:\n  - /home/ofscraper/\n" > /etc/fixuid/config.yml
USER ofscraper:ofscraper

ENTRYPOINT ["fixuid","-q"]
