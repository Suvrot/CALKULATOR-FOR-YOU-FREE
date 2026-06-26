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

Для проверки:


• Тест бота в TG: @testbotsava44_bot
