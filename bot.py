import os
import re
import logging
import sys
from aiohttp import web
from vkbottle import Bot
from vkbottle.bot import Message

# ====== НАСТРОЙКИ ЛОГИРОВАНИЯ ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ====== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ======
TOKEN = os.environ.get("API_TOKEN")
if not TOKEN:
    raise ValueError("❌ Переменная API_TOKEN не найдена!")

CONFIRMATION_CODE = os.environ.get("CONFIRMATION_CODE")
if not CONFIRMATION_CODE:
    raise ValueError("❌ Переменная CONFIRMATION_CODE не найдена!")

SECRET_KEY = os.environ.get("SECRET_KEY", "")

# ====== ИНИЦИАЛИЗАЦИЯ БОТА ======
bot = Bot(TOKEN)

async def is_admin(peer_id: int, user_id: int) -> bool:
    try:
        members = await bot.api.messages.get_conversation_members(peer_id=peer_id)
        for member in members.items:
            if member.member_id == user_id:
                return member.is_admin or member.is_owner
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
    return False

def extract_mention_id(text: str):
    match = re.search(r"\[id(\d+)\|", text)
    return int(match.group(1)) if match else None

def mention(user_id: int, name: str = "") -> str:
    return f"[id{user_id}|{name or '@user'}]"

# ====== КОМАНДЫ ======
@bot.on.message(command="пинг")
async def ping(message: Message):
    await message.answer("🏓 Понг! Бот работает!")

@bot.on.message(command="ник")
async def set_nickname(message: Message):
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        if not await is_admin(message.peer_id, message.from_id):
            return await message.answer("⛔ Только администратор может менять ники.")
        
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.answer("⚠ Использование: !ник @пользователь Новый ник")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        await bot.api.messages.set_chat_member_nickname(
            chat_id=message.chat_id,
            member_id=user_id,
            nick=args[2][:50]
        )
        await message.answer(f"✅ Ник изменён.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка.")

@bot.on.message(command="упомяни")
async def mention_user(message: Message):
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.answer("⚠ Использование: !упомяни @пользователь [текст]")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        text = args[1].split("]", 1)[1].strip() if "]" in args[1] else "привет!"
        await message.answer(f"{mention(user_id)}, {text}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка.")

@bot.on.message(command="кик")
async def kick_user(message: Message):
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        if not await is_admin(message.peer_id, message.from_id):
            return await message.answer("⛔ Нужны права администратора.")
        
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("⚠ Использование: !кик @пользователь")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        await bot.api.messages.remove_chat_user(
            chat_id=message.chat_id,
            member_id=user_id
        )
        await message.answer(f"🚫 Пользователь исключён.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка.")

@bot.on.message(command="бан")
async def ban_user(message: Message):
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        if not await is_admin(message.peer_id, message.from_id):
            return await message.answer("⛔ Нужны права администратора.")
        
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.answer("⚠ Использование: !бан @пользователь [причина]")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        reason = args[2][:100] if len(args) > 2 else "Нарушение правил"
        
        await bot.api.messages.ban_chat_member(
            chat_id=message.chat_id,
            member_id=user_id,
            reason=reason
        )
        await message.answer(f"🔨 Пользователь заблокирован.")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Произошла ошибка.")

# ====== CALLBACK ======
async def callback_handler(request):
    try:
        data = await request.json()
        
        if SECRET_KEY and request.headers.get("X-Secret") != SECRET_KEY:
            return web.Response(status=403)
        
        if data.get("type") == "confirmation":
            return web.Response(text=CONFIRMATION_CODE)
        
        await bot.emulate(data, confirmation_token=CONFIRMATION_CODE)
        return web.Response(text="ok")
    except Exception as e:
        logger.exception("Ошибка callback")
        return web.Response(status=500)

app = web.Application()
app.router.add_post("/callback", callback_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🚀 Бот запущен на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)
