# 🤖 Calkulator-FREE — Telegram Бот-Калькулятор

Telegram-бот-калькулятор с Flask веб-панелью администратора.
Поддерживает арифметику, тригонометрию, логарифмы, константы и историю вычислений.

---

## 📁 Структура файлов

```
.
├── bot.py          # Telegram-бот (логика, калькулятор, обработчики)
├── web.py          # Flask веб-панель + запуск бота в потоке
├── db.py           # Работа с SQLite (потокобезопасная)
├── config.py       # Конфигурация из переменных окружения
├── requirements.txt
├── Procfile        # Для Railway / Heroku
├── ecosystem.config.js  # Для PM2 (VPS)
├── .env.example    # Шаблон переменных окружения
└── .gitignore
```

---

## ⚙️ Установка и запуск

### 1. Клонируй репозиторий

```bash
git clone https://github.com/Suvrot/Calkulator-FREE.git
cd Calkulator-FREE
```

### 2. Создай виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Установи зависимости

```bash
pip install -r requirements.txt
```

### 4. Настрой переменные окружения

```bash
cp .env.example .env
nano .env   # заполни своими значениями
```

Обязательные переменные:
- `TELEGRAM_TOKEN` — токен бота от @BotFather
- `TELEGRAM_ADMIN_ID` — твой Telegram ID (узнать у @userinfobot)
- `WEB_PASSWORD` — пароль для веб-панели
- `SECRET_KEY` — случайная строка (сгенерируй командой ниже)

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Запуск локально (для тестирования)

```bash
# Загружаем .env и запускаем
export $(cat .env | xargs)
python3 web.py
```

Бот запустится + веб-панель будет доступна на http://localhost:5000

---

## 🚀 Деплой 24/7

### Вариант A: Railway (рекомендуется, бесплатно)

1. Зайди на [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Выбери этот репозиторий
3. В разделе **Variables** добавь все переменные из `.env.example`
4. Railway автоматически использует `Procfile` и запустит `gunicorn`

### Вариант B: VPS (Ubuntu) с PM2

```bash
# Установи PM2
npm install -g pm2

# Создай папку для логов
mkdir -p logs

# Загрузи переменные окружения
export $(cat .env | xargs)

# Запусти через PM2
pm2 start ecosystem.config.js

# Автозапуск при перезагрузке сервера
pm2 startup
pm2 save
```

Полезные команды PM2:
```bash
pm2 status          # статус процессов
pm2 logs calkulator # просмотр логов
pm2 restart calkulator
pm2 stop calkulator
```

### Вариант C: systemd (Ubuntu/Debian)

```bash
sudo nano /etc/systemd/system/calkulator.service
```

```ini
[Unit]
Description=Calkulator Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Calkulator-FREE
EnvironmentFile=/home/ubuntu/Calkulator-FREE/.env
ExecStart=/home/ubuntu/Calkulator-FREE/venv/bin/gunicorn web:app --workers 1 --threads 4 --bind 0.0.0.0:5000 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable calkulator
sudo systemctl start calkulator
sudo systemctl status calkulator
```

---

## 🔒 Безопасность (что было исправлено)

| # | Проблема | Исправление |
|---|----------|-------------|
| 1 | XSS в веб-панели | Данные экранируются через Jinja2 auto-escape |
| 2 | `asyncio.run()` внутри Flask | Синхронные вызовы DB без asyncio |
| 3 | Слабый `SECRET_KEY` по умолчанию | Генерируется случайно, предупреждение в логах |
| 4 | SQLite deadlock при конкурентности | `WAL mode` + `threading.Lock()` |
| 5 | `.db` файлы в репозитории | Добавлены в `.gitignore` |
| 6 | Нет rate limiting | 30 запросов / 60 сек на пользователя |
| 7 | Нет `/help` команды | Добавлена подробная справка |
| 8 | Мало функций калькулятора | Добавлены: tan, log, ln, abs, ceil, floor, π, % |
| 9 | Нет логирования | Логи в `web.log` и консоль |
| 10 | `backup_*.db` в публичном git | `.gitignore` исключает все `.db` файлы |

---

## ⚠️ Важно после деплоя

1. **Удали** файлы `backup_*.db` из репозитория:
   ```bash
   git rm --cached backup_*.db
   git commit -m "remove db backups from repo"
   git push
   ```

2. **Никогда** не коммить `.env` в git

3. Веб-панель доступна по адресу `http://твой-сервер:5000`
   (для продакшена настрой nginx + SSL)
