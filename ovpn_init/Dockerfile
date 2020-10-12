FROM ubuntu:18.04

RUN apt-get update && apt-get install -y \
    wget \
    openvpn \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/OpenVPN/easy-rsa/releases/download/v3.0.8/EasyRSA-3.0.8.tgz && \
    mkdir -p /easyrsa/bin && tar -xvzf EasyRSA-3.0.8.tgz -C /easyrsa/bin --strip-components 1 && \
    rm EasyRSA-3.0.8.tgz

COPY setup.sh /setup.sh

WORKDIR /easyrsa
ARG EASYRSA_REQ_COUNTRY="RU"
ARG EASYRSA_REQ_PROVINCE="MOSCOW"
ARG EASYRSA_REQ_CITY="MOSCOW"
ARG EASYRSA_REQ_ORG="Automated IM"
ARG EASYRSA_REQ_EMAIL="ovpn.bot@automated.im"
RUN /usr/bin/env bash /setup.sh

VOLUME /easyrsa/pki /easyrsa/server_certs /easyrsa/bot_certs

CMD ["/usr/bin/env", "bash", "-c", "echo 'PKI ready to use'"]
