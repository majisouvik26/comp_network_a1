FROM python:3.9-slim

WORKDIR /app

COPY . /app

EXPOSE 1500 1501 1502 2000 2001

CMD [ "bash" ]

