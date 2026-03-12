import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


class MessageManager:
    """
    Keeps chat clean by tracking the last bot message per chat.

    Text → text:  edit in place (instant, no flicker).
    * → photo:    delete + send (can't edit media type).
    photo → text: delete + send (previous was a photo, can't edit to text).
    Falls back to delete + send if edit fails for any reason.
    """

    _MAX_TRACKED = 10_000  # prevent unbounded growth

    def __init__(self) -> None:
        self._last: dict[int, int] = {}           # chat_id -> message_id
        self._last_is_photo: dict[int, bool] = {}  # chat_id -> was the last message a photo?

    async def send_message(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str | None = "HTML",
        **kwargs,
    ):
        prev_id = self._last.get(chat_id)
        prev_is_photo = self._last_is_photo.get(chat_id, False)

        if prev_id and not prev_is_photo:
            # Previous message was text — attempt edit in place
            if await self._try_edit_text(bot, chat_id, prev_id, text, reply_markup, parse_mode):
                self._last_is_photo[chat_id] = False
                return  # edited successfully, message_id unchanged

        # Fallback: delete old message and send a new one
        await self._delete_last(bot, chat_id)
        if len(self._last) >= self._MAX_TRACKED:
            self._last.clear()
            self._last_is_photo.clear()
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
        self._last[chat_id] = msg.message_id
        self._last_is_photo[chat_id] = False
        return msg

    async def send_photo(
        self,
        bot: Bot,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
        parse_mode: str | None = "HTML",
        **kwargs,
    ):
        # Photos always use delete + send (can't edit media type or swap file_id cleanly)
        await self._delete_last(bot, chat_id)
        if len(self._last) >= self._MAX_TRACKED:
            self._last.clear()
            self._last_is_photo.clear()
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
        self._last[chat_id] = msg.message_id
        self._last_is_photo[chat_id] = True
        return msg

    async def delete_last(self, bot: Bot, chat_id: int) -> None:
        await self._delete_last(bot, chat_id)

    async def _delete_last(self, bot: Bot, chat_id: int) -> None:
        msg_id = self._last.pop(chat_id, None)
        self._last_is_photo.pop(chat_id, None)
        if not msg_id:
            return
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest as e:
            lowered = str(e).lower()
            if "message to delete not found" in lowered or "message can't be deleted" in lowered:
                pass
            else:
                logger.warning("Failed to delete msg %d in chat %d: %s", msg_id, chat_id, e)
        except Exception as e:
            logger.warning("Unexpected error deleting msg %d in chat %d: %s", msg_id, chat_id, e)

    async def _try_edit_text(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
        parse_mode: str | None,
    ) -> bool:
        """
        Attempt to edit an existing text message in place.
        Returns True on success (including MessageNotModified — screen is already correct).
        Returns False if editing is impossible; caller should fall back to delete+send.
        """
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return True
        except TelegramBadRequest as e:
            lowered = str(e).lower()
            if "message is not modified" in lowered:
                # Content unchanged — the message on screen is already correct
                return True
            if (
                "message to edit not found" in lowered
                or "message can't be edited" in lowered
                or "chat not found" in lowered
            ):
                logger.debug("Cannot edit msg %d in chat %d, falling back: %s", message_id, chat_id, e)
                return False
            logger.warning("Unexpected TelegramBadRequest editing msg %d in chat %d: %s", message_id, chat_id, e)
            return False
        except Exception as e:
            logger.warning("Unexpected error editing msg %d in chat %d: %s", message_id, chat_id, e)
            return False

    async def delete_user_message(self, bot: Bot, chat_id: int, message_id: int) -> None:
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception:
            pass


message_manager = MessageManager()
