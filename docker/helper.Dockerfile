FROM devlab_base:latest
LABEL "com.lab.devlab"="base"
LABEL "last_modified"=1597871407


ARG APT="/usr/bin/apt-get --no-install-recommends -o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef"
ARG PACKAGES="docker.io python python3 python-yaml python3-yaml mysql-client netcat"
ENV DEBIAN_FRONTEND=noninteractive

RUN $APT update && \
    $APT upgrade -y && \
    $APT install -y $PACKAGES && \
    rm -rf /var/lib/apt/lists/*
