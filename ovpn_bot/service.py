import textwrap
from asyncio import sleep
from asyncio import wait_for
from contextlib import asynccontextmanager
from io import BytesIO
from logging import getLogger
from typing import List, Union
from uuid import UUID

from aiopg import connect, create_pool
from emoji import demojize
from psycopg2.errors import UniqueViolation, OperationalError

from ovpn_bot.certs import CertManager, dump_key, dump_cert_req, dump_cert, create_cert_manager
from ovpn_bot.dao import DeviceRepository, Device

log = getLogger(__name__)


def maybe_uuid(value):
    if isinstance(value, UUID):
        return value
    elif isinstance(value, str):
        return UUID(value)
    else:
        raise ValueError("Inappropriate uuid value")


class NamedBytesIO(BytesIO):
    def __init__(self, content: bytes, name: str):
        super(NamedBytesIO, self).__init__(content)
        self.__name = name

    @property
    def name(self) -> str:
        return self.__name


class VPNServiceError(Exception):
    pass


class DeviceDuplicatedError(VPNServiceError):
    pass


class DeviceNotFoundError(VPNServiceError):
    pass


class VPNService:
    def __init__(
            self,
            device_repository: DeviceRepository,
            cert_manager: CertManager,
            server_host: str,
            server_port: int
    ):
        self.__device_repository = device_repository
        self.__cert_manager = cert_manager
        self.__server_host = server_host
        self.__server_port = server_port
        log.info("VPN service created")

    async def count_devices(self, user_id: int) -> int:
        return await self.__device_repository.count(user_id)

    async def list_devices(self, user_id: int) -> List[Device]:
        return await self.__device_repository.list(user_id)

    async def create_device(self, user_id: int, name: str) -> Device:
        pkey = self.__cert_manager.create_private_key()

        common_name = f"{user_id} {demojize(name)}"
        cert_req = self.__cert_manager.create_certificate_request(common_name, pkey)

        serial_number = await self.__device_repository.next_cert_sn()
        cert = self.__cert_manager.sign_certificate_request(cert_req, serial_number)

        try:
            return await self.__device_repository.create(
                user_id,
                name,
                dump_key(pkey),
                dump_cert_req(cert_req),
                dump_cert(cert),
                serial_number)
        except UniqueViolation as e:
            raise DeviceDuplicatedError from e

    async def get_device(self, user_id: int, device_id: Union[str, UUID]) -> Device:
        device_id = maybe_uuid(device_id)
        device = await self.__device_repository.get(user_id, device_id)
        if device is None:
            raise DeviceNotFoundError
        else:
            return device

    async def remove_device(self, user_id: int, device_id: Union[str, UUID]) -> Device:
        device_id = maybe_uuid(device_id)
        device = await self.__device_repository.remove(user_id, device_id)
        if device is None:
            raise DeviceNotFoundError
        else:
            return device

    async def generate_device_config(self, user_id: int, device_id: Union[str, UUID]) -> NamedBytesIO:
        device = await self.get_device(user_id, device_id)
        content = textwrap.dedent(f"""
            client
            dev tun
            proto tcp
            remote {self.__server_host} {self.__server_port}
            resolv-retry infinite
            nobind
            user nobody
            group nogroup
            persist-key
            persist-tun
            remote-cert-tls server
            key-direction 1
            cipher AES-256-CBC
            auth SHA256
            verb 3
            
            ; script-security 2
            ; up /etc/openvpn/update-resolv-conf
            ; down /etc/openvpn/update-resolv-conf
            
            ; script-security 2
            ; up /etc/openvpn/update-systemd-resolved
            ; down /etc/openvpn/update-systemd-resolved
            ; down-pre
            ; dhcp-option DOMAIN-ROUTE .

            <ca>\n{textwrap.indent(self.__cert_manager.dump_ca().strip(), " " * 12)}
            </ca>
            <cert>\n{textwrap.indent(device.cert.strip(), " " * 12)}
            </cert>
            <key>\n{textwrap.indent(device.pkey.strip(), " " * 12)}
            </key>
            <tls-auth>\n{textwrap.indent(self.__cert_manager.dump_tls_auth().strip(), " " * 12)}
            </tls-auth>
        """).strip()
        return NamedBytesIO(content.encode("utf-8"), demojize(device.name) + ".ovpn")


async def wait_for_db(db_config):
    holder = type("", (), {})()
    holder.error = None

    async def do_connect():
        while True:
            try:
                async with connect(
                        host=db_config["host"],
                        port=db_config["port"],
                        dbname=db_config["name"],
                        user=db_config["username"],
                        password=db_config["password"],
                        timeout=db_config["timeout"]
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                break
            except (OSError, OperationalError) as e:
                holder.error = e
                await sleep(0.5)

    try:
        return await wait_for(do_connect(), db_config["wait"])
    except TimeoutError:
        raise TimeoutError('Waited too long for the database.') from holder.error


@asynccontextmanager
async def create_vpn_service(config) -> VPNService:
    db_config = config["database"]
    db_pool = db_config["pool"]
    server_config = config["server"]

    cert_manager = create_cert_manager(config)
    log.info("Cert manager created")

    log.info("Waiting for database...")
    await wait_for_db(db_config)
    async with create_pool(
            host=db_config["host"],
            port=db_config["port"],
            dbname=db_config["name"],
            user=db_config["username"],
            password=db_config["password"],
            timeout=db_config["timeout"],
            minsize=db_pool["minsize"],
            maxsize=db_pool["maxsize"],
            pool_recycle=db_pool["recycle"]
    ) as pool:
        device_repository = DeviceRepository(pool)
        log.info("Database pool created")

        yield VPNService(device_repository, cert_manager, server_config["host"], server_config["port"])
