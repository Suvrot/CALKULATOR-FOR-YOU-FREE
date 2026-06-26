import sqlite3
import threading
from datetime import datetime, timedelta

DB_NAME = "bot.db"

# Блокировка для защиты от одновременной записи из разных потоков
_lock = threading.Lock()


def get_connection():
    """Возвращает соединение, безопасное для многопоточного использования."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")   # WAL позволяет одновременно читать и писать
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# ── Инициализация таблиц при импорте ──────────────────────────────────────────
with _lock, get_connection() as conn:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY,
            username   TEXT,
            first_seen TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            expression TEXT,
            result     TEXT,
            time       TEXT
        )
    """)
    conn.commit()


# ── CRUD-функции ───────────────────────────────────────────────────────────────

def add_user(uid: int, username: str) -> None:
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE id=?", (uid,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users VALUES (?, ?, ?)",
                (uid, username, str(datetime.now())),
            )
            conn.commit()


def add_history(uid: int, expr: str, result) -> None:
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO history (user_id, expression, result, time) VALUES (?, ?, ?, ?)",
            (uid, expr, str(result), str(datetime.now())),
        )
        conn.commit()


def count_users() -> int:
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]


def total_ops() -> int:
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM history")
        return cur.fetchone()[0]


def last_history(limit: int = 15):
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, expression, result, time "
            "FROM history ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()


def get_all_users():
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, first_seen FROM users ORDER BY first_seen DESC")
        return cur.fetchall()


def get_ops_chart_data():
    labels = []
    data = []
    with _lock, get_connection() as conn:
        cur = conn.cursor()
        for i in range(6, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            cur.execute(
                "SELECT COUNT(*) FROM history WHERE time LIKE ?", (f"{day}%",)
            )
            count = cur.fetchone()[0]
            labels.append((datetime.now() - timedelta(days=i)).strftime("%d.%m"))
            data.append(count)
    return labels, data


def backup(dest_path: str) -> None:
    """Создаёт резервную копию базы данных в dest_path."""
    with _lock, get_connection() as src:
        dest = sqlite3.connect(dest_path)
        src.backup(dest)
        dest.close()
