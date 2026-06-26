import ast
import operator
import math
import asyncio
import signal
import sys
import os
import time
from collections import defaultdict

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

print("[INIT] Библиотеки загружены. Подключаем файлы проекта...")

try:
    import db
    from config import TOKEN, ADMIN_ID
    print("[INIT] db.py и config.py успешно подключены!")
except Exception as e:
    print(f"[CRITICAL ERROR] Ошибка импорта: {e}")
    sys.exit(1)


# ── Rate limiting: не более 30 сообщений в минуту на пользователя ─────────────
_rate_data: dict[int, list[float]] = defaultdict(list)
RATE_LIMIT = 30      # максимум сообщений
RATE_WINDOW = 60.0   # за этот период (секунды)

def is_rate_limited(uid: int) -> bool:
    now = time.monotonic()
    timestamps = _rate_data[uid]
    # Удаляем старые отметки за пределами окна
    _rate_data[uid] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_data[uid]) >= RATE_LIMIT:
        return True
    _rate_data[uid].append(now)
    return False


# ── Клавиатура ─────────────────────────────────────────────────────────────────
keyboard = ReplyKeyboardMarkup(
    [
        ["(", ")", "^", "⬅️"],
        ["sin", "cos", "tan", "sqrt"],
        ["log", "abs", "π", "="],
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "Очистить", "+"],
        ["История", "Помощь", "Админ"],
    ],
    resize_keyboard=True,
)


# ── Безопасный AST-калькулятор ─────────────────────────────────────────────────
def safe_calc(expr: str) -> str | int | float:
    expr = expr.replace("=", "").strip()
    expr = expr.replace("^", "**")
    expr = expr.replace("π", str(math.pi))

    if not expr:
        return "error"

    # Лимит длины выражения
    if len(expr) > 200:
        return "Ошибка: выражение слишком длинное!"

    # Авто-закрытие скобок
    open_count = expr.count("(")
    close_count = expr.count(")")
    if open_count > close_count:
        expr += ")" * (open_count - close_count)

    _operators = {
        ast.Add:  operator.add,
        ast.Sub:  operator.sub,
        ast.Mult: operator.mul,
        ast.Div:  operator.truediv,
        ast.USub: operator.neg,
        ast.Pow:  operator.pow,
        ast.Mod:  operator.mod,
    }

    _functions = {
        "sin":  lambda x: math.sin(math.radians(x)),
        "cos":  lambda x: math.cos(math.radians(x)),
        "tan":  lambda x: math.tan(math.radians(x)),
        "sqrt": math.sqrt,
        "log":  math.log10,          # log10
        "ln":   math.log,            # натуральный логарифм
        "abs":  abs,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return "Ошибка: неверный синтаксис выражения"

    def eval_node(node):
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise TypeError("Недопустимый тип")
            return node.value

        elif isinstance(node, ast.BinOp):
            left_val  = eval_node(node.left)
            right_val = eval_node(node.right)

            if isinstance(node.op, ast.Div) and right_val == 0:
                raise ZeroDivisionError()

            if isinstance(node.op, ast.Pow):
                if abs(left_val) > 1e6 or abs(right_val) > 300:
                    raise ValueError("Числа слишком большие для возведения в степень!")
                if left_val < 0 and not isinstance(right_val, int):
                    raise ValueError("Отрицательное число в нецелой степени недопустимо")

            return _operators[type(node.op)](left_val, right_val)

        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _operators:
                raise TypeError("Недопустимая операция")
            return _operators[type(node.op)](eval_node(node.operand))

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise NameError("Недопустимый вызов")
            func_name = node.func.id
            if func_name not in _functions:
                raise NameError(f"Неизвестная функция: {func_name}")
            if len(node.args) != 1:
                raise ValueError(f"{func_name}() принимает ровно 1 аргумент")
            arg_val = eval_node(node.args[0])
            if abs(arg_val) > 1_000_000:
                raise ValueError("Аргумент функции слишком большой!")
            if func_name == "sqrt" and arg_val < 0:
                raise ValueError("sqrt() не определён для отрицательных чисел")
            if func_name in ("log", "ln") and arg_val <= 0:
                raise ValueError("log() не определён для нуля и отрицательных чисел")
            return _functions[func_name](arg_val)

        else:
            raise TypeError("Недопустимая конструкция в выражении")

    try:
        result = eval_node(tree.body)
        if isinstance(result, float):
            if math.isnan(result) or math.isinf(result):
                return "Ошибка: результат не определён (nan/inf)"
            if result.is_integer() and abs(result) < 1e15:
                return int(result)
        return round(result, 8)

    except ZeroDivisionError:
        return "Ошибка: деление на ноль!"
    except ValueError as ve:
        return f"Ошибка: {ve}"
    except (NameError, TypeError, KeyError) as e:
        return f"Ошибка: {e}"
    except Exception as e:
        print(f"[CALC ERROR] '{expr}': {e}")
        return "Ошибка вычисления"


# ── Обработчики команд ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await asyncio.to_thread(db.add_user, user.id, user.username or "none")
    context.user_data["expr"] = ""

    robot_photo_url = (
        "https://img.freepik.com/free-vector/cute-robot-operating-laptop-cartoon-vector-"
        "icon-illustration-science-technology-icon-concept_138676-2244.jpg"
    )
    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "🤖 Я — умный калькулятор прямо в Telegram!\n\n"
        "📈 Что умею:\n"
        "• Арифметика: + − * / ^ %\n"
        "• Тригонометрия: sin, cos, tan (градусы)\n"
        "• sqrt, log (log10), ln, abs, ceil, floor\n"
        "• Константа π (кнопка π)\n\n"
        "Нажимай кнопки или пиши выражение текстом.\n"
        "Команда /help — подробная справка."
    )
    try:
        await update.message.reply_photo(
            photo=robot_photo_url, caption=welcome_text, reply_markup=keyboard
        )
    except Exception:
        await update.message.reply_text(welcome_text, reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Справка по Calkulator*\n\n"
        "*Арифметика:*\n"
        "`2 + 3`, `10 - 4`, `6 * 7`, `15 / 3`\n"
        "`2 ^ 10` — степень\n"
        "`17 % 5` — остаток от деления\n\n"
        "*Функции:*\n"
        "`sin(90)` → 1\n"
        "`cos(60)` → 0.5\n"
        "`tan(45)` → 1\n"
        "`sqrt(16)` → 4\n"
        "`log(1000)` → 3 (log10)\n"
        "`ln(2.718)` → ≈1\n"
        "`abs(-5)` → 5\n\n"
        "*Константы:*\n"
        "Кнопка `π` вставляет 3.14159...\n\n"
        "*Команды:*\n"
        "/start — приветствие\n"
        "/help — эта справка\n"
        "/clear — очистить выражение"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["expr"] = ""
    await update.message.reply_text("Очищено ✅", reply_markup=keyboard)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text

    # Rate limiting
    if is_rate_limited(uid):
        await update.message.reply_text(
            "⏳ Слишком много запросов. Подождите немного.", reply_markup=keyboard
        )
        return

    if "expr" not in context.user_data:
        context.user_data["expr"] = ""

    # ── Кнопки управления ─────────────────────────────────────────────────────
    if text == "Очистить":
        context.user_data["expr"] = ""
        await update.message.reply_text("0", reply_markup=keyboard)
        return

    if text == "⬅️":
        context.user_data["expr"] = context.user_data["expr"][:-1]
        msg = context.user_data["expr"] if context.user_data["expr"] else "0"
        await update.message.reply_text(msg, reply_markup=keyboard)
        return

    if text == "Помощь":
        await cmd_help(update, context)
        return

    if text == "История":
        hist = await asyncio.to_thread(db.last_history, 10)
        if not hist:
            await update.message.reply_text("История пуста")
            return
        lines = [f"`{h[1]}` = *{h[2]}*" for h in hist]
        msg = "📋 *Последние вычисления:*\n" + "\n".join(lines)
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if text == "Админ":
        if uid != ADMIN_ID:
            await update.message.reply_text("⛔ У вас нет доступа.")
            return
        users_count = await asyncio.to_thread(db.count_users)
        ops_count   = await asyncio.to_thread(db.total_ops)
        await update.message.reply_text(
            f"📊 *Статистика:*\n"
            f"Пользователей: {users_count}\n"
            f"Операций в БД: {ops_count}",
            parse_mode="Markdown",
        )
        return

    if text == "=":
        current_expr = context.user_data["expr"]
        if not current_expr:
            await update.message.reply_text("Сначала введите выражение")
            return
        result = safe_calc(current_expr)
        if "Ошибка" not in str(result) and result != "error":
            await asyncio.to_thread(db.add_history, uid, current_expr, result)
            context.user_data["expr"] = str(result)
        else:
            context.user_data["expr"] = ""
        await update.message.reply_text(str(result), reply_markup=keyboard)
        return

    # ── Функции (добавляют открывающую скобку) ─────────────────────────────────
    if text in ("sin", "cos", "tan", "sqrt", "log", "ln", "abs", "ceil", "floor"):
        context.user_data["expr"] += f"{text}("
        await update.message.reply_text(context.user_data["expr"], reply_markup=keyboard)
        return

    if text == "π":
        context.user_data["expr"] += "π"
        await update.message.reply_text(context.user_data["expr"], reply_markup=keyboard)
        return

    # ── Ввод символов ──────────────────────────────────────────────────────────
    allowed_chars = set("0123456789+-*/.^()%πe sincostaqrlbf")
    filtered = "".join(c for c in text if c in allowed_chars)

    if filtered:
        current = context.user_data["expr"]
        # Если предыдущее состояние было ошибкой — сброс
        if "Ошибка" in current or current == "error":
            context.user_data["expr"] = ""
        context.user_data["expr"] += filtered

        # Лимит длины выражения на экране
        if len(context.user_data["expr"]) > 200:
            context.user_data["expr"] = context.user_data["expr"][:200]
            await update.message.reply_text(
                "⚠️ Достигнут лимит длины выражения (200 символов)", reply_markup=keyboard
            )
            return

        await update.message.reply_text(context.user_data["expr"], reply_markup=keyboard)


# ── Точка входа ────────────────────────────────────────────────────────────────

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    print("[BOT] Telegram-бот успешно запущен!")

    stop_event = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                pass
    except Exception:
        pass

    await stop_event.wait()

    print("[BOT] Получен сигнал остановки, завершаем...")
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
