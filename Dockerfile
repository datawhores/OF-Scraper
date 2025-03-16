ARG PYTHON_VERSION="3.11"
FROM python:$PYTHON_VERSION AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.8.3

WORKDIR /app

RUN python -m ensurepip --upgrade

RUN apt-get update && apt-get -y dist-upgrade

ARG SIZE="minimal"

RUN apt-get update && \
    if [ "$SIZE" = "full" ]; then \
        apt-get install ffmpeg -y; \
    fi

RUN apt-get clean

FROM base AS builder

RUN pip3 install "poetry==$POETRY_VERSION" poetry-plugin-export
RUN python -m venv /venv

COPY poetry.lock pyproject.toml ./
RUN poetry export -f requirements.txt  -o requirements.txt --ansi --without-hashes

RUN /venv/bin/pip --no-cache-dir install -r requirements.txt

RUN rm requirements.txt

COPY . .
RUN  pip install dunamai
RUN poetry version $(poetry run dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\w+)")
RUN poetry build && /venv/bin/pip install dist/*.whl

FROM base AS final

ARG TARGETARCH

COPY --from=builder /venv /venv

ENV PATH="/venv/bin:${PATH}" \
    VIRTUAL_ENV="/venv"

RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN USER=ofscraper && \
    GROUP=ofscraper && \
    LATEST_VERSION=$(curl -s https://api.github.com/repos/boxboat/fixuid/releases/latest | grep "tag_name"| cut -d'v' -f2 | cut -d'"' -f1) && \
    curl -SsL "https://github.com/boxboat/fixuid/releases/latest/download/fixuid-$LATEST_VERSION-linux-$TARGETARCH.tar.gz" | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\npaths:\n  - /home/ofscraper/\n" > /etc/fixuid/config.yml
USER ofscraper:ofscraper

ENTRYPOINT ["fixuid","-q"]
