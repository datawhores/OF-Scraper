FROM ubuntu:latest
RUN apk --no-cache add python3 py3-pip gcc python3-dev musl-dev git
RUN pip install .
WORKDIR /opt
ENTRYPOINT ["ofscraper"]
