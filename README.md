# OpenVPN Telegram Bot

This repository provides OpenVPN-server and simple Telegram bot to manage it. 

Bot supports multiple users authorized against the membership 
in private group. Each authorized user can register up to 6 devices 
(this number is configurable). Each device will obtain it's unique
client certificate bundled with appropriate OpenVPN-client configuration.

## Quick start

1.  [Register your Telegram bot](http://t.me/BotFather). 
    Store your bot's token as it will be needed in next steps.

1.  Create private group to manage your users and 
    add your bot to it as administrator.

1.  Obtain your group id by sending `/chat_id` command to bot.
    It will be used in next steps.

1.  Clone project:
    ```bash
    git clone git@github.com:alon-sage/ovpn-bot.git
    cd ovpn-bot
    ```

1.  Make copy of example secrets and settings and provide your own values:
    ```bash
    cp -R secrets.example secrets
    cp -R settings.example settings
    ```
   
    `secrets/bot_token.txt` - bot's token obtained at step 1.
   
    `secrets/database_password.txt` - password for bot database. Just generate new random.
   
    ‼️ Secret files should not contains any extra whitespace characters 
    nor empty lines at the end as it interpreted as a part of secret value. ‼️
   
    `settings/ovpn_bot.env` - bot settings
       
    ```bash
    # your private group id obtained at step 3
    USERS_GROUP_ID=-623742742672
    
    # IP-address or hostname which client should connect to
    SERVER_HOST=your.awesome.domain.com
    # or
    SERVER_HOST=127.0.0.1
   
    # Port which client should connect to.
    SERVER_PORT=443
   
    # Max number of devices user may register.
    DEFAULT_MAX_DEVICES=6
    ```

1.  [Install Docker](https://docs.docker.com/engine/install/)

1.  [Install Docker Compose](https://docs.docker.com/compose/install/)

1.  Build images:
    ```bash
    docker-compose build
    ```
   
1.  In `docker-compose.yaml` comment out service `ipv6_nat` if your host has no IPv6 address.

    ```yaml
    #  ipv6_nat:
    #    image: robbertkl/ipv6nat
    #    restart: unless-stopped
    #    network_mode: "host"
    #    volumes:
    #      - "/var/run/docker.sock:/var/run/docker.sock:ro"
    #    cap_drop:
    #      - ALL
    #    cap_add:
    #      - NET_ADMIN
    #      - NET_RAW
    #    command: ["--retry", "--debug", "--cleanup"]
    ```

1.  In `docker-compose.yaml` change section `ports` of `ovpn_server` service 
    in order to bind OpenVPN server to appropriate addresses.

    For example, with settings shown beneath OpenVPN server will be listen on all 
    available IPv4 interfaces:

    ```yaml
      ovpn_server:
        ...
        ports:
          - "0.0.0.0:443:443"
    ```

1. Start services:
    ```bash
   docker-compose up -d
    ```
   
# Architecture

![](http://www.plantuml.com/plantuml/proxy?src=https://raw.githubusercontent.com/alon-sage/ovpn-bot/main/docs/architecture.plantuml)
 
 ## TODO
 
 * [ ] Revocation of removed devices' certificates
