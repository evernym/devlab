FROM ubuntu:focal
  
# ARGS and ENVS
ENV DEBIAN_FRONTEND=noninteractive

ARG PACKAGES="apt-transport-https curl file git gnupg jq python3 python3-pip python python-pip-whl unzip"
ARG PIPS="yamllint pylint"
ARG APT="/usr/bin/apt-get -o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef"

# Install packages
RUN $APT update && $APT install -y --no-install-recommends $PACKAGES && \
    pip3 --disable-pip-version-check install $PIPS && \
    rm -rf /var/lib/apt/lists/*

# Provide Evernym CA
RUN mkdir -p /usr/local/share/ca-certificates/ && \
echo '-----BEGIN CERTIFICATE-----\n\
MIIFJTCCAw2gAwIBAgIUMI0Z8YSLeRq8pZks40O3Dq2m8TIwDQYJKoZIhvcNAQEL\n\
BQAwGjEYMBYGA1UEAxMPRXZlcm55bSBSb290IENBMB4XDTE3MTAxMTIwMTAxMFoX\n\
DTQ3MTAwNDIwMTAzOVowGjEYMBYGA1UEAxMPRXZlcm55bSBSb290IENBMIICIjAN\n\
BgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA1kjmtmMfLJfsqUNaco44N3brW8Vu\n\
b02lAeEwbxc65mwfAG8kAjW7kYhI/fDXFOYXUvoa3Dg7bFeEatdIjHOahZssGM27\n\
HsQZ4PfRhPE6HtXFszmDwXWuEekVxoyueTqL7ExnNZ+BRTXvPfm5nw1E7L3o3xHF\n\
GSOtWFCyHfKd1LwMKzAVSjxlawEZnfk3WK3NxrC4UYMlQaDme7m3rCMfO+KBQk69\n\
bFXsgn6/EihVeQ8T1+T8gogofzh5b4Z7kS6e6GMqotbGFg4agejkRVsIglSpaQLk\n\
2Ztn/MP1dwgyvO4uvplB4sxZSC2FhhovlwPETmbKsnpj020+m0+YU4FPKwjroMiH\n\
tP//YqiNKsLxtjhffW7XFToyy0qQttW5RMWnyx4MXs9Hwcy29gY1izeGMSzz3zV5\n\
HG8JSJikuYbYiGJRVS0egovkVjja6lrVk0Q4Hm5pbw4l7LYCd6bkDLMsRaS1QnWs\n\
9iz6XEf5SpIu1FuqHmlhj1ABehUyGIg5oC6egML3q78yk0mCW523qMFa9Kjnk871\n\
mmXSCn3p/3DCrwWYfpcibxtVaKyJj6ISYIcl+Zu65Uzmhf+nj56x3gkNgEOva7JS\n\
Xge+FxPxsaXBGyeSH09nNIoNmh/UucuzpNY2UyCpJuqXHtR5jaACSdsqNxG8tcDg\n\
K9v98D/DFiShghECAwEAAaNjMGEwDgYDVR0PAQH/BAQDAgEGMA8GA1UdEwEB/wQF\n\
MAMBAf8wHQYDVR0OBBYEFOrH4oUpB94gNDNqdGG92kdVZ3qkMB8GA1UdIwQYMBaA\n\
FOrH4oUpB94gNDNqdGG92kdVZ3qkMA0GCSqGSIb3DQEBCwUAA4ICAQCwjN3ggZ98\n\
BXT39fKkCX3FHb0++aFcIyMKWrcZIpYrl3GoZsNKZK4QNQ+uJOP8xmqgyrCoMfch\n\
VIGPQ0RDN/IzqCLhc/U3pDmk2hXa3xTxD3gpCQZ6Bz04KlcLfZd5jzbI741bVDyF\n\
a1n46bEyuqV4SsNJWI/FGokJCNcZH66njBQBaQAccZ7xB9vWU9yjIYtGQDDvSm6J\n\
SC2knrQri0vv4QLUSc1LS6AlWWSQxcCpcdO+OzIFGsf5bVmYN6J4R3COY5NyQ+yn\n\
pOSN2NOh5h3ZrYAxm3i4Il0orVLveVcTVDGeAgZUII4YLJi/01RHGqit3aCuApSh\n\
bzFTZ5FldFss+JX9iAhqpFDbHLgae0F3QmYEnGilt/PzO4j23QJo3FZKeruQLH7P\n\
L9aOgN6S2+Akbbm9YTc59yzU5TZMxANwTdaYFWFqk/8nKgZiBR1l8jnWTlWnm86A\n\
qVssH3DLKwiYrWSOHRzGuN5BmPXxxtKQJlwAXt0wJE3puUkaJSRo7CJQ3QNMoKDe\n\
OjzXc9WvkFIXr3Eui8UTiHB/WT7N4o8hmVN404akGfWE0YNwRVfWpjGdew6g0tZi\n\
lFnjUUk49av67um43JHcinT5NFPuleZzkjaL/D8ueOrjXQDy05rwVdgmw9pXog4B\n\
Tw6APXtEnjfD2H8HOpOX/7ef4gWK0O1Q7A==\n\
-----END CERTIFICATE-----\n' > /usr/local/share/ca-certificates/Evernym_Root_CA.crt && \
/usr/sbin/update-ca-certificates
