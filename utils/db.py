import sqlite3
from config.settings import DB_PATH
# Путь к базе данных
# DB_PATH = "auth_users.db"

# Создаем подключение и таблицу, если она не существует
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            is_authorized INTEGER NOT NULL,
            access_token TEXT,
            refresh_token TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_authorized_users():
    """Возвращает список Telegram ID всех авторизованных пользователей."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE is_authorized = 1")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


# Добавление пользователя
def add_user(telegram_id: int, access_token: str, refresh_token: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (telegram_id, is_authorized, access_token, refresh_token)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, 1, access_token, refresh_token))
    conn.commit()
    conn.close()

# Удаление пользователя
def remove_user(telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
    conn.commit()
    conn.close()

# Проверка авторизации пользователя
def is_user_authorized(telegram_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT is_authorized FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None and result[0] == 1

