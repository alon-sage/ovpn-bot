import logging
from asyncio import run
from logging import basicConfig

from ovpn_bot.bot import create_bot, create_bot_dispatcher, create_storage
from ovpn_bot.config import load_config
from ovpn_bot.service import create_vpn_service


async def main():
    basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s [%(levelname)-8s] %(name)-20s: %(message)s")

    config = load_config()
    bot = await create_bot(config)
    storage = await create_storage(config)
    async with create_vpn_service(config) as vpn_service:
        try:
            dispatcher = await create_bot_dispatcher(bot, storage, vpn_service, config)
            await dispatcher.start_polling()
        finally:
            await bot.close()


if __name__ == '__main__':
    try:
        run(main())
    except KeyboardInterrupt:
        pass
