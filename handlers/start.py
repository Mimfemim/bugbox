from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="start")


WELCOME_MESSAGE = (
    "👋 سلام!\n\n"
    "این ربات Bug Inbox هست.\n"
    "هر چیزی که فکر می‌کنی باگه، همینجا بفرست:\n\n"
    "• متن\n"
    "• اسکرین‌شات\n"
    "• ویدیو\n"
    "• ویس\n"
    "• فایل\n"
    "• هر پیامی که forward کنی\n\n"
    "🤖 هوش مصنوعی خودکار دسته‌بندی می‌کنه.\n"
    "لازم نیست فرم پر کنی یا چیزی انتخاب کنی."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_MESSAGE)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(WELCOME_MESSAGE)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    username = f"@{user.username}" if user.username else "—"
    await message.answer(
        f"🆔 آیدی عددی تو: {user.id}\n"
        f"یوزرنیم: {username}\n\n"
        "برای دسترسی به پنل ادمین، این عدد باید توی متغیر ADMIN_IDS باشه."
    )
