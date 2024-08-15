FROM python:3.11 AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.7.1

WORKDIR /app

RUN python -m ensurepip --upgrade

RUN apt-get update && apt-get -y dist-upgrade

RUN apt-get update && apt-get install ffmpeg cmake wget -y

FROM base AS builder

RUN pip3 install "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY poetry.lock pyproject.toml ./
RUN poetry export -f requirements.txt | /venv/bin/pip --no-cache-dir install -r /dev/stdin

COPY . .
RUN  pip install dunamai
RUN poetry version $(poetry run dunamai from git --format "{base}" --pattern "(?P<base>\d+\.\d+\.\w+)")
RUN poetry build && /venv/bin/pip install dist/*.whl

FROM base AS bento4

RUN wget https://github.com/axiomatic-systems/Bento4/archive/refs/tags/v1.6.0-641.tar.gz

RUN tar -xvf v1.6.0-641.tar.gz

WORKDIR /app/Bento4-1.6.0-641/

RUN mkdir cmakebuild

WORKDIR /app/Bento4-1.6.0-641/cmakebuild

RUN cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local ..

RUN make -j4

RUN make install

FROM base AS final

ARG TARGETPLATFORM
ARG BUILDARCH

COPY --from=builder /venv /venv

RUN mkdir -p /temp_usr_local

COPY --from=bento4 /app/Bento4-1.6.0-641/cmakebuild/install_manifest.txt /app/install_manifest.txt

COPY --from=bento4 /usr/local /temp_usr_local

RUN while read -r line; do \
        temp_line="/temp_usr_local${line#/usr/local}"; \
        dir=$(dirname "$line"); \
        mkdir -p "$dir"; \
        cp --preserve=all "$temp_line" "$line"; \
    done < /app/install_manifest.txt


RUN rm -f /app/install_manifest.txt

RUN rm -rf /temp_usr_local

ENV PATH="/venv/bin:${PATH}" \
    VIRTUAL_ENV="/venv"

RUN addgroup --gid 1000 ofscraper && \
    adduser --uid 1000 --ingroup ofscraper --home /home/ofscraper --shell /bin/sh --disabled-password --gecos "" ofscraper

RUN USER=ofscraper && \
    GROUP=ofscraper && \
    LATEST_VERSION=$(curl -s https://api.github.com/repos/boxboat/fixuid/releases/latest | grep "tag_name"| cut -d'v' -f2 | cut -d'"' -f1) && \
    curl -SsL "https://github.com/boxboat/fixuid/releases/latest/download/fixuid-$LATEST_VERSION-linux-$BUILDARCH.tar.gz" | tar -C /usr/local/bin -xzf - && \
    chown root:root /usr/local/bin/fixuid && \
    chmod 4755 /usr/local/bin/fixuid && \
    mkdir -p /etc/fixuid && \
    printf "user: $USER\ngroup: $GROUP\npaths:\n  - /home/ofscraper/\n" > /etc/fixuid/config.yml
USER ofscraper:ofscraper

ENTRYPOINT ["fixuid","-q"]
