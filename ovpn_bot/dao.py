from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from typing import List, Optional
from uuid import UUID

from aiopg import Pool

log = getLogger(__name__)


@dataclass
class Device:
    id: UUID
    user_id: int
    name: str
    pkey: str
    cert_req: str
    cert: str
    cert_sn: int
    created_at: datetime
    removed: bool


class DeviceRepository:
    def __init__(self, pool: Pool):
        self.__pool = pool
        log.info("Device repository created")

    async def next_cert_sn(self) -> int:
        with await self.__pool.cursor() as cur:
            await cur.execute("select nextval('certs_sn')")
            return (await cur.fetchone())[0]

    async def count(self, user_id: int) -> int:
        with await self.__pool.cursor() as cur:
            await cur.execute("select count(*) from devices where user_id = %s and not removed", [user_id])
            return (await cur.fetchone())[0]

    async def list(self, user_id: int) -> List[Device]:
        with await self.__pool.cursor() as cur:
            await cur.execute("select * from devices where user_id = %s and not removed", [user_id])
            return [Device(*record) for record in await cur.fetchall()]

    async def create(self, user_id: int, name: str, pkey: str, cert_req: str, cert: str, cert_sn: int) -> Device:
        with await self.__pool.cursor() as cur:
            await cur.execute(
                """
                insert into devices (user_id, name, pkey, cert_req, cert, cert_sn) 
                values (%s, %s, %s, %s, %s, %s) returning *
                """,
                [user_id, name, pkey, cert_req, cert, cert_sn])
            return Device(*await cur.fetchone())

    async def get(self, user_id: int, device_id: UUID) -> Optional[Device]:
        with await self.__pool.cursor() as cur:
            await cur.execute(
                "select * from devices where user_id = %s and id = %s and not removed",
                [user_id, device_id])
            result = await cur.fetchone()
            return None if result is None else Device(*result)

    async def remove(self, user_id: int, device_id: UUID) -> Optional[Device]:
        with await self.__pool.cursor() as cur:
            await cur.execute(
                "update devices set removed = true where user_id = %s and id = %s and not removed returning *",
                [user_id, device_id])
            result = await cur.fetchone()
            return None if result is None else Device(*result)
