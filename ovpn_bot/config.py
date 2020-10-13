import os
from argparse import ArgumentParser, Namespace
from logging import getLogger
from os import environ
from typing import Dict

from confuse import Configuration, String, Integer, Number, Filename

log = getLogger(__name__)

SECRETS_DIR = os.environ.get("SECRETS_DIR", "/run/secrets")


def load_secrets() -> Dict[str, str]:
    secrets = {}
    if os.path.isdir(SECRETS_DIR):
        for filename in os.listdir(SECRETS_DIR):
            if os.path.isfile(os.path.join(SECRETS_DIR, filename)):
                current = secrets
                labels = filename.split('.')
                while labels:
                    label = labels.pop(0)
                    if labels:
                        current = current.setdefault(label, {})
                    else:
                        with open(os.path.join(SECRETS_DIR, filename), "r") as file:
                            current[label] = file.read()
    return secrets


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "--bot-token",
        default=environ.get("BOT_TOKEN"))

    parser.add_argument(
        "--customers-group-id",
        default=environ.get("CUSTOMERS_GROUP_ID"))

    parser.add_argument(
        "--database.host",
        default=environ.get("DATABASE_HOST"))

    parser.add_argument(
        "--database.port",
        type=int,
        default=environ.get("DATABASE_PORT"))

    parser.add_argument(
        "--database.name",
        default=environ.get("DATABASE_NAME"))

    parser.add_argument(
        "--database.username",
        default=environ.get("DATABASE_USERNAME"))

    parser.add_argument(
        "--database.password",
        default=environ.get("DATABASE_PASSWORD"))

    parser.add_argument(
        "--database.timeout",
        type=float,
        default=environ.get("DATABASE_TIMEOUT"))

    parser.add_argument(
        "--database.wait",
        type=float,
        default=environ.get("DATABASE_WAIT"))

    parser.add_argument(
        "--database.pool.minsize",
        type=int,
        default=environ.get("DATABASE_POOL_MINSIZE"))

    parser.add_argument(
        "--database.pool.maxsize",
        type=int,
        default=environ.get("DATABASE_POOL_MAXSIZE"))

    parser.add_argument(
        "--database.pool.recycle",
        type=int,
        default=environ.get("DATABASE_POOL_RECYCLE"))

    parser.add_argument(
        "--pki.ca",
        default=environ.get("PKI_CA"))

    parser.add_argument(
        "--pki.cert",
        default=environ.get("PKI_CERT"))

    parser.add_argument(
        "--pki.pkey",
        default=environ.get("PKI_PKEY"))

    parser.add_argument(
        "--pki.passphrase",
        default=environ.get("PKI_PASSPHRASE"))

    parser.add_argument(
        "--pki.tls-auth",
        default=environ.get("PKI_TLS_AUTH"))

    parser.add_argument(
        "--server.host",
        default=environ.get("SERVER_HOST"))

    parser.add_argument(
        "--server.port",
        type=int,
        default=environ.get("SERVER_PORT"))

    parser.add_argument(
        "--default.max-devices",
        type=int,
        default=environ.get("DEFAULT_MAX_DEVICES"))

    parsed_args = parser.parse_args()

    log.info("Arguments parsed")
    return parsed_args


def load_config() -> Configuration:
    template = {
        "bot_token": String(),
        "customers_group_id": String(),
        "database": {
            "host": String(default="localhost"),
            "port": Integer(default=5432),
            "name": String(default="postgres"),
            "username": String(default="postgres"),
            "password": String(default=""),
            "timeout": Number(default=60.0),
            "wait": Number(default=30.0),
            "pool": {
                "minsize": Integer(default=2),
                "maxsize": Integer(default=10),
                "recycle": Integer(default=-1)
            }
        },
        "pki": {
            "ca": Filename(default="certs/ca.crt"),
            "cert": Filename(default="certs/root.crt"),
            "pkey": Filename(default="certs/root.key"),
            "passphrase": String(default=None),
            "tls_auth": Filename(default="certs/ta.key")
        },
        "server": {
            "host": String(default="127.0.0.1"),
            "port": Integer(default=1443)
        },
        "default": {
            "max_devices": Integer(default=6)
        }
    }

    config = Configuration("VpnBot", __name__)
    config.set(load_secrets())
    config.set_args(parse_args(), dots=True)

    log.info("Configuration loaded")
    return config.get(template)
