FROM ubuntu:20.04

LABEL "last_modified"=1625675491

EXPOSE 80

RUN apt-get update &&\
    apt-get install -y --no-install-recommends \
        nginx \
        less \
        vim \
    && \
    rm -rf /var/lib/apt/lists/*

CMD [ "/usr/sbin/nginx", "-g", "daemon off;" ]
