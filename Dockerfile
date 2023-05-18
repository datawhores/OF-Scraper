FROM docker.io/library/alpine:edge
RUN apk --no-cache add python3 py3-pip gcc python3-dev musl-dev
RUN python3 -m pip install git+https://github.com/datawhores/ofscraper.git 

WORKDIR /opt
ENTRYPOINT ["ofscraper"]