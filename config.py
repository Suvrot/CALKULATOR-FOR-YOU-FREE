import os
import secrets

# ──────────────────────────────────────────────
#  Все значения берутся ТОЛЬКО из переменных окружения.
#  НЕ храните реальные токены в коде или в git!
# ──────────────────────────────────────────────

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", 0))

WEB_LOGIN = os.getenv("WEB_LOGIN", "admin")
WEB_PASSWORD = os.getenv("WEB_PASSWORD", "")

# Если SECRET_KEY не задан в env — генерируем случайный при каждом запуске.
# ВАЖНО: для сохранения сессий между перезапусками задайте SECRET_KEY в env!
_default_key = secrets.token_hex(32)
SECRET_KEY = os.getenv("SECRET_KEY", _default_key)

# Проверка при старте — предупреждаем об отсутствующих критичных переменных
if not TOKEN:
    raise RuntimeError(
        "[CONFIG] TELEGRAM_TOKEN не задан! "
        "Установите переменную окружения TELEGRAM_TOKEN перед запуском."
    )
if ADMIN_ID == 0:
    print("[CONFIG WARNING] TELEGRAM_ADMIN_ID не задан. Кнопка 'Админ' в боте не будет работать.")
if not WEB_PASSWORD:
    raise RuntimeError(
        "[CONFIG] WEB_PASSWORD не задан! "
        "Установите переменную окружения WEB_PASSWORD перед запуском."
    )
if SECRET_KEY == _default_key:
    print("[CONFIG WARNING] SECRET_KEY не задан в env. Сессии будут сбрасываться при перезапуске.")
