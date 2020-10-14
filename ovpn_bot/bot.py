from logging import getLogger
from typing import Union, Dict, Any, Optional

from aiogram import Dispatcher, Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Filter, ChatTypeFilter
from aiogram.dispatcher.filters.filters import AndFilter
from aiogram.dispatcher.storage import BaseStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Update, Chat, Message, ChatType
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


class GroupMemberFilter(Filter):
    def __init__(self, users_group: Chat):
        self.__users_group = users_group

    @classmethod
    def validate(cls, full_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise ValueError("That filter can't be used in filters factory!")

    async def check(self, obj: Union[Message, CallbackQuery]) -> bool:
        member = await self.__users_group.get_member(obj.from_user.id)
        is_chat_member = member.is_chat_member()
        if not is_chat_member:
            log.info(f"Unauthorized access from {obj.from_user.id} ({obj.from_user.username})")
            return False
        return is_chat_member


async def create_bot_dispatcher(
        bot: Bot,
        storage: BaseStorage,
        vpn_service: VPNService,
        config
) -> Dispatcher:
    authorized = AndFilter(
        ChatTypeFilter(ChatType.PRIVATE),
        GroupMemberFilter(await bot.get_chat(config["users_group_id"])))

    dispatcher = Dispatcher(bot=bot, storage=storage)

    devices_cb = CallbackData("device", "id", "action")

    @dispatcher.errors_handler()
    async def error_handler(update: Update, exc: BaseException):
        if update.message is not None:
            chat_id = update.message.from_user.id
        elif update.callback_query is not None:
            chat_id = update.callback_query.from_user.id

        log.exception(f"Bot failed to handle update from {chat_id}", exc_info=exc)

        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
        await bot.send_message(
            chat_id,
            "Oh sorry! 😞 There is error occurred. Please contact administrator to solve this problem.",
            parse_mode="markdown",
            reply_markup=keyboard_markup)

        if update.message is not None:
            await update.message.delete()
        elif update.callback_query is not None:
            await update.callback_query.message.delete()
            await update.callback_query.answer()

    @dispatcher.message_handler(authorized, commands=["start", "restart"])
    @dispatcher.callback_query_handler(authorized, lambda query: query.data == 'list', state="*")
    async def list_handler(event: Union[Message, CallbackQuery], state: FSMContext):
        await state.finish()

        if isinstance(event, Message):
            await event.delete()

        devices = await vpn_service.list_devices(event.from_user.id)
        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(
            InlineKeyboardButton("➕ Add new device", callback_data="add"),
            InlineKeyboardButton("🔄 Refresh", callback_data="list"))
        keyboard_markup.add(*(
            InlineKeyboardButton(device.name, callback_data=devices_cb.new(id=device.id, action="details"))
            for device in devices))
        await bot.send_message(
            event.from_user.id,
            "Choose one of your devices." if devices else "You have no devices.",
            reply_markup=keyboard_markup)

        if isinstance(event, CallbackQuery):
            await event.message.delete()
            await event.answer()

    @dispatcher.callback_query_handler(authorized, lambda query: query.data == 'add')
    async def add_handler(query: CallbackQuery, state: FSMContext):
        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
        if await vpn_service.has_device_quota(query.from_user.id):
            await state.set_state("device_name")
            message = await bot.send_message(
                query.from_user.id,
                f"Enter new device name:",
                reply_markup=keyboard_markup)
            async with state.proxy() as data:
                data['message_id'] = message.message_id
        else:
            await bot.send_message(
                query.from_user.id,
                f"Can't add more than *{vpn_service.get_device_quota()}* devices",
                parse_mode="markdown",
                reply_markup=keyboard_markup)

        await query.message.delete()
        await query.answer()

    @dispatcher.message_handler(authorized, lambda message: message.text, state="device_name")
    async def device_name_handler(message: Message, state: FSMContext):
        keyboard_markup = InlineKeyboardMarkup(row_width=2)
        keyboard_markup.add(InlineKeyboardButton("<< Back", callback_data="list"))
        try:
            device = await vpn_service.create_device(message.from_user.id, message.text.strip())
        except DeviceDuplicatedError:
            await message.answer(
                f"Device named *{message.text.strip()}* already exists.",
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

    @dispatcher.callback_query_handler(authorized, devices_cb.filter(action="details"))
    @dispatcher.callback_query_handler(authorized, devices_cb.filter(action="config"))
    async def details_handler(query: CallbackQuery):
        cb_data = devices_cb.parse(query.data)
        action = cb_data["action"]
        device_id = cb_data["id"]
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

    @dispatcher.callback_query_handler(authorized, devices_cb.filter(action="remove"))
    async def remove_handler(query: CallbackQuery):
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

    @dispatcher.callback_query_handler(authorized, devices_cb.filter(action="confirm_removal"))
    async def confirm_removal_handler(query: CallbackQuery):
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

    @dispatcher.message_handler(authorized, commands=["user_id"])
    async def chat_id_handler(message: Message):
        await message.answer(f"User ID: {message.from_user.id}")

    log.info("Bot dispatcher created")
    return dispatcher
