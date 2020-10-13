FROM ubuntu:18.04

RUN apt-get update && apt-get install -y \
    openvpn \
    iptables \
    && rm -rf /var/lib/apt/lists/*

COPY setup.sh /setup.sh

WORKDIR /app
RUN /usr/bin/env bash /setup.sh

EXPOSE 443

CMD ["/usr/bin/env", "openvpn", "server.conf"]