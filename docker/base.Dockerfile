FROM ubuntu:24.04
LABEL "com.lab.devlab"="base"
LABEL "last_modified"=1713305264

ARG APT="/usr/bin/apt-get --no-install-recommends -o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef"
ARG PACKAGES="sudo less screen tmux vim ca-certificates git curl iproute2 less gnupg2"
ENV DEBIAN_FRONTEND=noninteractive

RUN $APT update && \
    $APT upgrade -y && \
    $APT install -y $PACKAGES && \
    rm -rf /var/lib/apt/lists/*
