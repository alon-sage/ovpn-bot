from functools import wraps
from io import BytesIO
from logging import getLogger
from typing import Union

from aiogram import Dispatcher, Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.storage import BaseStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.callback_data import CallbackData

from ovpn_bot.service import VPNService, DeviceDuplicatedError

log = getLogger(__name__)


async def create_bot(config) -> Bot:
    bot = Bot(token=config["bot_token"])

    bot_user = await bot.get_me()
    log.info(f"Bot created http://t.me/{bot_user['username']}")
    return bot


async def create_storage(config) -> BaseStorage:
    return MemoryStorage()


async def create_bot_dispatcher(
        bot: Bot,
        storage: BaseStorage,
        vpn_service: VPNService,
        config
) -> Dispatcher:
    customers_group = await bot.get_chat(config["customers_group_id"])

    def authorize_customer(wrapped):
        @wraps(wrapped)
        async def wrapper(event, *args, **kwargs):
            member = await customers_group.get_member(event.from_user.id)
            if member is None:
                log.info(
                    f"{event.get_command(True)} from {event.from_user.id} @{event.from_user.username}: unauthorized access")
                return
            return await wrapped(event, *args, **kwargs)

        return wrapper

    dispatcher = Dispatcher(bot=bot, storage=storage)

    devices_cb = CallbackData("device", "id", "action")

    @dispatcher.message_handler(commands=["start", "restart"])
    @dispatcher.callback_query_handler(lambda query: query.data == 'list', state="*")
    @authorize_customer
    async def list_handler(event: Union[types.Message, types.CallbackQuery], state: FSMContext):
        await state.finish()

        if isinstance(event, types.Message):
            await bot.delete_message(event.from_user.id, event.message_id)

        devices = await vpn_service.list_devices(event.from_user.id)
        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(
            InlineKeyboardButton("➕ Add new device", callback_data="add"),
            InlineKeyboardButton("🔄 Refresh", callback_data="list"))
        keyboard_markup.add(*(
            InlineKeyboardButton(device.name, callback_data=devices_cb.new(id=device.id, action="details"))
            for device in devices
        ))
        if devices:
            await bot.send_message(
                event.from_user.id,
                "Choose one of devices or add new.",
                reply_markup=keyboard_markup)
        else:
            await bot.send_message(
                event.from_user.id,
                "You have no devices.",
                reply_markup=keyboard_markup)

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            await event.answer()

    @dispatcher.callback_query_handler(lambda query: query.data == 'add')
    @authorize_customer
    async def add_handler(query: types.CallbackQuery, state: FSMContext):
        max_devices = config["default"]["max_devices"]
        if await vpn_service.count_devices(query.from_user.id) >= max_devices:
            keyboard_markup = InlineKeyboardMarkup(row_width=2)
            keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
            await bot.send_message(
                query.from_user.id,
                f"Can't add more than *{max_devices}* devices",
                parse_mode="markdown",
                reply_markup=keyboard_markup)
        else:
            await state.set_state("device_name")
            keyboard_markup = InlineKeyboardMarkup(row_width=2)
            keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
            message = await bot.send_message(
                query.from_user.id,
                f"Enter new device name:",
                reply_markup=keyboard_markup)
            async with state.proxy() as data:
                data['message_id'] = message.message_id

        await query.message.delete()
        await query.answer()

    @dispatcher.message_handler(lambda message: message.text, state="device_name")
    @authorize_customer
    async def device_name_handler(message: types.Message, state: FSMContext):
        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
        try:
            device = await vpn_service.create_device(message.from_user.id, message.text.strip())
        except DeviceDuplicatedError:
            await message.answer(
                f"Device named *{message.text.strip()}* already exists.",
                parse_mode="markdown",
                reply_markup=keyboard_markup)
        except Exception:
            log.exception(f"Failed to create device {message.text.strip()} of {message.from_user.id}")
            await message.answer(
                f"Failed to create device named *{message.text.strip()}*. Contact administrator to solve this problem.",
                parse_mode="markdown",
                reply_markup=keyboard_markup)
        else:
            await message.answer(
                f"Device named *{device.name}* successfully created.",
                parse_mode="markdown",
                reply_markup=keyboard_markup)

        await message.delete()
        async with state.proxy() as data:
            await bot.delete_message(message.from_user.id, int(data['message_id']))
        await state.finish()

    @dispatcher.callback_query_handler(devices_cb.filter(action="details"))
    @dispatcher.callback_query_handler(devices_cb.filter(action="config"))
    @authorize_customer
    async def details_handler(query: types.CallbackQuery):
        action = devices_cb.parse(query.data)["action"]
        device_id = devices_cb.parse(query.data)["id"]
        device = await vpn_service.get_device(query.from_user.id, device_id)

        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(
            InlineKeyboardButton("Get config", callback_data=devices_cb.new(id=device_id, action="config")),
            InlineKeyboardButton("✖️ Remove", callback_data=devices_cb.new(id=device_id, action="remove")),
            InlineKeyboardButton("<< Back", callback_data="list"))

        if action == "config":
            with await vpn_service.generate_device_config(query.from_user.id, device_id) as config_stream:
                await bot.send_document(
                    query.from_user.id,
                    config_stream,
                    caption=f"*{device.name}* config",
                    parse_mode="markdown",
                    reply_markup=keyboard_markup)
        else:
            await bot.send_message(
                query.from_user.id,
                f"What to do with device *{device.name}*?",
                parse_mode="markdown",
                reply_markup=keyboard_markup)

        await query.message.delete()
        await query.answer()

    @dispatcher.callback_query_handler(devices_cb.filter(action="remove"))
    @authorize_customer
    async def remove_handler(query: types.CallbackQuery):
        device_id = devices_cb.parse(query.data)["id"]
        device = await vpn_service.get_device(query.from_user.id, device_id)

        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(
            InlineKeyboardButton("✖️ Remove", callback_data=devices_cb.new(id=device_id, action="confirm_removal")),
            InlineKeyboardButton("<< Back", callback_data=devices_cb.new(id=device_id, action="details")))
        await bot.send_message(
            query.from_user.id,
            f"Are you sure to remove device *{device.name}*?",
            parse_mode="markdown",
            reply_markup=keyboard_markup)

        await query.message.delete()
        await query.answer()

    @dispatcher.callback_query_handler(devices_cb.filter(action="confirm_removal"))
    @authorize_customer
    async def confirm_removal_handler(query: types.CallbackQuery):
        device_id = devices_cb.parse(query.data)["id"]
        device = await vpn_service.remove_device(query.from_user.id, device_id)

        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
        await bot.send_message(
            query.from_user.id,
            f"Device *{device.name}* was removed.",
            parse_mode="markdown",
            reply_markup=keyboard_markup)

        await query.message.delete()
        await query.answer()

    @dispatcher.message_handler(commands=["chat_id"])
    async def chat_id_handler(message: types.Message):
        await message.answer(f"Chat ID: {message.chat.id}")

    log.info("Bot dispatcher created")
    return dispatcher
