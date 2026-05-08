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

# ====== ОТЛАДКА - ПОКАЗАТЬ ВСЕ ПЕРЕМЕННЫЕ ======
print("=== ДОСТУПНЫЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===")
for key, value in os.environ.items():
    if any(name in key.upper() for name in ['TOKEN', 'KEY', 'SECRET', 'CONFIRM', 'VK', 'BOT']):
        print(f"{key}: {value[:10]}... (обрезано)" if len(value) > 10 else f"{key}: {value}")
print("=== КОНЕЦ СПИСКА ===")

# ====== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (ВСЕ ВОЗМОЖНЫЕ ВАРИАНТЫ) ======
TOKEN = (
    os.environ.get("TOKEN") or
    os.environ.get("VK_TOKEN") or
    os.environ.get("token") or
    os.environ.get("BOT_TOKEN") or
    os.environ.get("VK_BOT_TOKEN") or
    os.environ.get("ACCESS_TOKEN")
)

CONFIRMATION_CODE = (
    os.environ.get("CONFIRMATION_CODE") or
    os.environ.get("VK_CONFIRMATION_CODE") or
    os.environ.get("confirmation_code") or
    os.environ.get("CONFIRMATION") or
    os.environ.get("VK_CONFIRMATION")
)

SECRET_KEY = (
    os.environ.get("SECRET_KEY") or
    os.environ.get("VK_SECRET_KEY") or
    os.environ.get("secret_key") or
    os.environ.get("VK_SECRET")
)

GROUP_ID = os.environ.get("GROUP_ID") or os.environ.get("VK_GROUP_ID") or "0"

# ====== ПРОВЕРКИ С ПОДРОБНЫМИ ОШИБКАМИ ======
if not TOKEN:
    error_msg = """
    ❌ ТОКЕН НЕ НАЙДЕН!
    
    Проверенные переменные:
    - TOKEN
    - VK_TOKEN
    - token
    - BOT_TOKEN
    - VK_BOT_TOKEN
    - ACCESS_TOKEN
    
    Доступные переменные окружения:
    {}
    """.format('\n    '.join(os.environ.keys()))
    raise ValueError(error_msg)

if not CONFIRMATION_CODE:
    error_msg = """
    ❌ КОД ПОДТВЕРЖДЕНИЯ НЕ НАЙДЕН!
    
    Проверенные переменные:
    - CONFIRMATION_CODE
    - VK_CONFIRMATION_CODE
    - confirmation_code
    - CONFIRMATION
    - VK_CONFIRMATION
    """
    raise ValueError(error_msg)

logger.info(f"✅ Токен загружен: {TOKEN[:10]}...")
logger.info(f"✅ Код подтверждения: {CONFIRMATION_CODE}")
logger.info(f"✅ ID группы: {GROUP_ID}")

# ====== ИНИЦИАЛИЗАЦИЯ БОТА ======
bot = Bot(TOKEN)

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
async def is_admin(peer_id: int, user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором беседы."""
    try:
        members = await bot.api.messages.get_conversation_members(peer_id=peer_id)
        for member in members.items:
            if member.member_id == user_id:
                return member.is_admin or member.is_owner
    except Exception as e:
        logger.error(f"Ошибка проверки прав администратора: {e}")
    return False

def extract_mention_id(text: str):
    """Извлекает ID пользователя из упоминания вида [id123|текст]."""
    match = re.search(r"\[id(\d+)\|", text)
    if match:
        return int(match.group(1))
    return None

def mention(user_id: int, name: str = "") -> str:
    """Создаёт строку упоминания."""
    return f"[id{user_id}|{name or '@user'}]"

# ====== КОМАНДА ДЛЯ ПРОВЕРКИ РАБОТЫ ======
@bot.on.message(command="пинг")
async def ping(message: Message):
    """Проверка работоспособности бота"""
    await message.answer("🏓 Понг! Бот работает!")

@bot.on.message(command="ник")
async def set_nickname(message: Message):
    """Установка ника: !ник @пользователь Новый ник"""
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
        
        new_nick = args[2][:50]
        
        await bot.api.messages.set_chat_member_nickname(
            chat_id=message.chat_id,
            member_id=user_id,
            nick=new_nick
        )
        await message.answer(f"✅ Ник для {mention(user_id)} изменён на «{new_nick}».")
    except Exception as e:
        logger.exception("Ошибка в команде !ник")
        await message.answer(f"❌ Произошла ошибка: {e}")

@bot.on.message(command="упомяни")
async def mention_user(message: Message):
    """Упоминание пользователя: !упомяни @пользователь [текст]"""
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.answer("⚠ Использование: !упомяни @пользователь [текст]")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        mention_end = re.search(r"\[id\d+\|[^\]]+\]", args[1])
        if mention_end:
            text = args[1][mention_end.end():].strip() or "привет!"
        else:
            text = "привет!"
        
        await message.answer(f"{mention(user_id)}, {text}")
    except Exception as e:
        logger.exception("Ошибка в команде !упомяни")
        await message.answer(f"❌ Произошла ошибка: {e}")

@bot.on.message(command="кик")
async def kick_user(message: Message):
    """Исключение из беседы: !кик @пользователь"""
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        if not await is_admin(message.peer_id, message.from_id):
            return await message.answer("⛔ Нужны права администратора беседы.")
        
        args = message.text.split()
        if len(args) < 2:
            return await message.answer("⚠ Использование: !кик @пользователь")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        if user_id == message.from_id:
            return await message.answer("❌ Нельзя кикнуть самого себя.")
        
        await bot.api.messages.remove_chat_user(
            chat_id=message.chat_id,
            member_id=user_id
        )
        await message.answer(f"🚫 Пользователь {mention(user_id)} исключён из беседы.")
    except Exception as e:
        logger.exception("Ошибка в команде !кик")
        await message.answer(f"❌ Произошла ошибка: {e}")

@bot.on.message(command="бан")
async def ban_user(message: Message):
    """Блокировка в беседе: !бан @пользователь [причина]"""
    try:
        if not message.chat_id:
            return await message.answer("❌ Команда работает только в беседах.")
        
        if not await is_admin(message.peer_id, message.from_id):
            return await message.answer("⛔ Нужны права администратора беседы.")
        
        args = message.text.split(maxsplit=2)
        if len(args) < 2:
            return await message.answer("⚠ Использование: !бан @пользователь [причина]")
        
        user_id = extract_mention_id(args[1])
        if not user_id:
            return await message.answer("❌ Укажите пользователя через @.")
        
        if user_id == message.from_id:
            return await message.answer("❌ Нельзя забанить самого себя.")
        
        reason = args[2] if len(args) > 2 else "Нарушение правил"
        reason = reason[:100]
        
        await bot.api.messages.ban_chat_member(
            chat_id=message.chat_id,
            member_id=user_id,
            reason=reason
        )
        await message.answer(f"🔨 Пользователь {mention(user_id)} заблокирован. Причина: {reason}")
    except Exception as e:
        logger.exception("Ошибка в команде !бан")
        await message.answer(f"❌ Произошла ошибка: {e}")

# ====== ОБРАБОТЧИК CALLBACK API ======
async def callback_handler(request):
    """Принимает POST-запросы от ВКонтакте."""
    try:
        data = await request.json()
        logger.debug(f"Получен callback: {data.get('type', 'unknown')}")
        
        if SECRET_KEY and request.headers.get("X-Secret") != SECRET_KEY:
            logger.warning("Неверный секретный ключ")
            return web.Response(status=403)
        
        if data.get("type") == "confirmation":
            logger.info("Отправка кода подтверждения")
            return web.Response(text=CONFIRMATION_CODE)
        
        await bot.emulate(data, confirmation_token=CONFIRMATION_CODE)
        return web.Response(text="ok")
    except Exception as e:
        logger.exception("Ошибка callback")
        return web.Response(status=500, text="Internal Server Error")

# ====== ЗАПУСК ======
app = web.Application()
app.router.add_post("/callback", callback_handler)

# Добавляем корневой маршрут для проверки
async def index(request):
    return web.Response(text="Бот работает! Используйте /callback для VK")

app.router.add_get("/", index)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🚀 Запуск бота на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)
