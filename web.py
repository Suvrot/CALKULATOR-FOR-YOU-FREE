import os
import threading
import asyncio
import logging
from datetime import datetime

from flask import Flask, request, redirect, url_for, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from markupsafe import escape   # ← FIX: экранирование HTML против XSS

import db
import bot
from config import WEB_LOGIN, WEB_PASSWORD, SECRET_KEY

# ── Логирование ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("web.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Flask ──────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class AdminUser(UserMixin):
    def __init__(self, uid):
        self.id = uid


@login_manager.user_loader
def load_user(user_id):
    if user_id == WEB_LOGIN:
        return AdminUser(WEB_LOGIN)
    return None


# ── Шаблоны ────────────────────────────────────────────────────────────────────
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Вход — Admin Panel</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a;
           display: flex; justify-content: center; align-items: center;
           height: 100vh; margin: 0; color: white; }
    .card { background: #1e293b; padding: 40px; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,.4); width: 100%; max-width: 360px; text-align: center; }
    h2 { margin-bottom: 20px; color: #38bdf8; }
    input { width: 100%; padding: 10px 14px; margin: 8px 0; border-radius: 6px;
            border: 1px solid #475569; background: #334155; color: white; font-size: 15px; }
    button { width: 100%; padding: 12px; background: #0284c7; border: none; color: white;
             font-weight: bold; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 12px; }
    button:hover { background: #0369a1; }
    .error { color: #f87171; margin-top: 10px; font-size: 14px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>🔑 Панель управления</h2>
    {% if error %}<p class="error">{{ error }}</p>{% endif %}
    <form method="POST" action="/login">
      <input type="text"     name="username" placeholder="Логин"   autocomplete="username"    required>
      <input type="password" name="password" placeholder="Пароль"  autocomplete="current-password" required>
      <button type="submit">Войти</button>
    </form>
  </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Calkulator — Admin Analytics</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #f8fafc; min-height: 100vh; padding: 16px; }
    .navbar { display: flex; justify-content: space-between; align-items: center;
              background: #1e293b; padding: 12px 24px; border-radius: 8px; margin-bottom: 20px; }
    .navbar h1 { font-size: 18px; color: #38bdf8; }
    .logout { background: #ef4444; color: white; padding: 7px 16px;
              text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 14px; }
    .logout:hover { background: #dc2626; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .grid-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .card { background: #1e293b; padding: 20px; border-radius: 10px; }
    .stat { text-align: center; display: flex; flex-direction: column; justify-content: center; }
    .stat h3 { color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
    .stat p  { font-size: 52px; font-weight: 700; color: #38bdf8; margin-top: 8px; }
    .card-title { color: #e2e8f0; font-size: 16px; border-bottom: 1px solid #334155;
                  padding-bottom: 10px; margin-bottom: 12px; }
    .table-wrap { max-height: 280px; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { background: #334155; color: #94a3b8; padding: 9px 10px;
         text-align: left; text-transform: uppercase; font-size: 11px; }
    td { padding: 9px 10px; border-bottom: 1px solid #334155; color: #cbd5e1; word-break: break-all; }
    tr:hover td { background: rgba(56,189,248,.05); }
    code { background: #334155; padding: 2px 5px; border-radius: 4px; color: #38bdf8; font-size: 12px; }
    @media (max-width: 700px) { .grid2, .grid-stats { grid-template-columns: 1fr; } }
    canvas { max-height: 200px; }
  </style>
</head>
<body>
  <nav class="navbar">
    <h1>📊 Calkulator — Аналитика</h1>
    <a class="logout" href="/logout">Выйти</a>
  </nav>

  <div class="grid2">
    <div class="grid-stats">
      <div class="card stat">
        <h3>Пользователей</h3>
        <p>{{ users_count }}</p>
      </div>
      <div class="card stat">
        <h3>Операций</h3>
        <p>{{ ops_count }}</p>
      </div>
    </div>

    <div class="card">
      <p class="card-title">📈 Активность за 7 дней</p>
      <canvas id="chart"></canvas>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <p class="card-title">👥 Пользователи</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Username</th><th>Дата</th></tr></thead>
          <tbody>
            {% for uid, uname, fseen in all_users %}
            <tr>
              <td><code>{{ uid }}</code></td>
              <td>@{{ uname }}</td>
              <td>{{ fseen[:19] }}</td>
            </tr>
            {% else %}
            <tr><td colspan="3" style="text-align:center;color:#64748b;">Пусто</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <p class="card-title">📋 Последние вычисления</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Выражение</th><th>Результат</th><th>Время</th></tr></thead>
          <tbody>
            {% for user_id, expr, res, ts in history_records %}
            <tr>
              <td><code>{{ user_id }}</code></td>
              <td>{{ expr }}</td>
              <td><strong>{{ res }}</strong></td>
              <td>{{ ts[:19] }}</td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align:center;color:#64748b;">Пусто</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    new Chart(document.getElementById('chart').getContext('2d'), {
      type: 'line',
      data: {
        labels: {{ chart_labels | tojson }},
        datasets: [{
          label: 'Расчёты',
          data: {{ chart_data | tojson }},
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56,189,248,.12)',
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: '#38bdf8'
        }]
      },
      options: {
        scales: {
          y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
          x: { grid: { display: false },          ticks: { color: '#94a3b8' } }
        },
        plugins: { legend: { display: false } }
      }
    });
  </script>
</body>
</html>
"""


# ── Маршруты ───────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == WEB_LOGIN and password == WEB_PASSWORD:
            login_user(AdminUser(WEB_LOGIN))
            logger.info("Успешный вход в панель администратора")
            return redirect(url_for("home"))
        error = "Неверный логин или пароль"
        logger.warning("Неудачная попытка входа (логин: %s)", escape(username))
    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/")
@login_required
def home():
    try:
        # ── FIX: вызываем функции БД напрямую (они синхронные), без asyncio.run ──
        users_count     = db.count_users()
        ops_count       = db.total_ops()
        history_records = db.last_history(15)
        all_users       = db.get_all_users()
        chart_labels, chart_data = db.get_ops_chart_data()

        # ── FIX: данные проходят через Jinja2 auto-escape → XSS невозможен ──────
        return render_template_string(
            DASHBOARD_TEMPLATE,
            users_count=users_count,
            ops_count=ops_count,
            history_records=history_records,
            all_users=all_users,
            chart_labels=chart_labels,
            chart_data=chart_data,
        )
    except Exception as e:
        logger.exception("Ошибка в /home")
        return f"<h2 style='color:red'>Ошибка: {escape(str(e))}</h2>", 500


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── Запуск бота в отдельном потоке ────────────────────────────────────────────

def run_bot():
    """Запускает Telegram-бота в собственном event loop в фоновом потоке."""
    logger.info("[BOT-THREAD] Запускаем event loop для бота...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.main())
    except Exception as e:
        logger.critical("[BOT-THREAD] Бот упал с ошибкой: %s", e)
    finally:
        loop.close()
        logger.warning("[BOT-THREAD] Event loop закрыт")


if __name__ == "__main__":
    # Запускаем бот в демон-потоке (завершится вместе с Flask)
    bot_thread = threading.Thread(target=run_bot, daemon=True, name="TelegramBot")
    bot_thread.start()
    logger.info("[WEB] Telegram-бот запущен в фоновом потоке")

    port = int(os.environ.get("PORT", 5000))
    logger.info("[WEB] Flask стартует на 0.0.0.0:%d", port)
    # debug=False обязателен в продакшене!
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
