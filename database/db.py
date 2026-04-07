from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "healthcare.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_definition: str) -> None:
    column_name = column_definition.split()[0]
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _users_table_definition(table_name: str = "users") -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            age INTEGER,
            gender TEXT DEFAULT '',
            city TEXT DEFAULT 'Delhi',
            phone TEXT DEFAULT '',
            medical_conditions TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """


def _build_users_migration_select(source_columns: set[str]) -> str:
    full_name_parts: list[str] = []
    if "full_name" in source_columns:
        full_name_parts.append("NULLIF(TRIM(full_name), '')")
    if "name" in source_columns:
        full_name_parts.append("NULLIF(TRIM(name), '')")
    full_name_options = ", ".join(full_name_parts + ["'HealthCare User'"])
    full_name_expr = f"COALESCE({full_name_options})"

    if "email" in source_columns:
        email_expr = (
            "CASE "
            "WHEN email IS NULL OR TRIM(email) = '' THEN 'legacy-user-' || id || '@local.health' "
            "ELSE LOWER(TRIM(email)) "
            "END"
        )
    else:
        email_expr = "'legacy-user-' || id || '@local.health'"

    password_hash_expr = "COALESCE(password_hash, '')" if "password_hash" in source_columns else "''"
    age_expr = "age" if "age" in source_columns else "NULL"
    gender_expr = "COALESCE(gender, '')" if "gender" in source_columns else "''"

    if "city" in source_columns:
        city_expr = "COALESCE(NULLIF(TRIM(city), ''), 'Delhi')"
    else:
        city_expr = "'Delhi'"

    phone_expr = "COALESCE(phone, '')" if "phone" in source_columns else "''"

    if "medical_conditions" in source_columns:
        medical_conditions_expr = "COALESCE(medical_conditions, '')"
    else:
        medical_conditions_expr = "''"

    bio_expr = "COALESCE(bio, '')" if "bio" in source_columns else "''"

    if "created_at" in source_columns:
        created_at_expr = "COALESCE(NULLIF(created_at, ''), CURRENT_TIMESTAMP)"
    else:
        created_at_expr = "CURRENT_TIMESTAMP"

    if "updated_at" in source_columns:
        updated_at_expr = "COALESCE(NULLIF(updated_at, ''), CURRENT_TIMESTAMP)"
    elif "created_at" in source_columns:
        updated_at_expr = "COALESCE(NULLIF(created_at, ''), CURRENT_TIMESTAMP)"
    else:
        updated_at_expr = "CURRENT_TIMESTAMP"

    return f"""
        SELECT
            id,
            {full_name_expr} AS full_name,
            {email_expr} AS email,
            {password_hash_expr} AS password_hash,
            {age_expr} AS age,
            {gender_expr} AS gender,
            {city_expr} AS city,
            {phone_expr} AS phone,
            {medical_conditions_expr} AS medical_conditions,
            {bio_expr} AS bio,
            {created_at_expr} AS created_at,
            {updated_at_expr} AS updated_at
        FROM users_legacy
        ORDER BY id
    """


def _migrate_users_table(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "users"):
        connection.execute(_users_table_definition())
        return

    source_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    required_columns = {
        "full_name",
        "email",
        "password_hash",
        "age",
        "gender",
        "city",
        "phone",
        "medical_conditions",
        "bio",
        "created_at",
        "updated_at",
    }

    if required_columns.issubset(source_columns) and "name" not in source_columns:
        return

    connection.execute("DROP TABLE IF EXISTS users_legacy")
    connection.execute("ALTER TABLE users RENAME TO users_legacy")
    connection.execute(_users_table_definition())
    migration_select = _build_users_migration_select(source_columns)
    connection.execute(
        f"""
        INSERT INTO users (
            id,
            full_name,
            email,
            password_hash,
            age,
            gender,
            city,
            phone,
            medical_conditions,
            bio,
            created_at,
            updated_at
        )
        {migration_select}
        """
    )
    connection.execute("DROP TABLE users_legacy")


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(_users_table_definition())
        _migrate_users_table(connection)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                notes TEXT DEFAULT '',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        _ensure_column(connection, "chat_history", "user_id INTEGER")
        _ensure_column(connection, "reminders", "user_id INTEGER")
        connection.commit()


def _row_to_user(row: sqlite3.Row | None) -> dict[str, object] | None:
    if row is None:
        return None

    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "age": row["age"],
        "gender": row["gender"] or "",
        "city": row["city"] or "Delhi",
        "phone": row["phone"] or "",
        "medical_conditions": row["medical_conditions"] or "",
        "bio": row["bio"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_user(
    *,
    full_name: str,
    email: str,
    password_hash: str,
    city: str = "Delhi",
) -> dict[str, object]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash, city)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email.lower().strip(), password_hash, city.strip() or "Delhi"),
        )
        user_id = int(cursor.lastrowid)
        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        connection.commit()

    return _row_to_user(row) or {}


def get_user_by_email(email: str) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email.lower().strip(),),
        ).fetchone()

    return _row_to_user(row)


def get_user_auth_record(email: str) -> sqlite3.Row | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email.lower().strip(),),
        ).fetchone()

    return row


def get_user_by_id(user_id: int) -> dict[str, object] | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return _row_to_user(row)


def update_user_profile(
    user_id: int,
    *,
    full_name: str,
    age: int | None,
    gender: str,
    city: str,
    phone: str,
    medical_conditions: str,
    bio: str,
) -> dict[str, object] | None:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET full_name = ?,
                age = ?,
                gender = ?,
                city = ?,
                phone = ?,
                medical_conditions = ?,
                bio = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                full_name.strip(),
                age,
                gender.strip(),
                city.strip() or "Delhi",
                phone.strip(),
                medical_conditions.strip(),
                bio.strip(),
                user_id,
            ),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return None

        row = connection.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        connection.commit()

    return _row_to_user(row)


def save_chat_message(user_id: int | None, session_id: str, role: str, message: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_history (user_id, session_id, role, message)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, session_id, role, message),
        )
        connection.commit()


def get_chat_history(
    *,
    user_id: int | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    if user_id is None and session_id is None:
        return []

    if user_id is not None:
        query = """
            SELECT id, user_id, session_id, role, message, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """
        params: tuple[object, ...] = (user_id, limit)
    else:
        query = """
            SELECT id, user_id, session_id, role, message, created_at
            FROM chat_history
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
        """
        params = (session_id, limit)

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    history = [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "message": row["message"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    history.reverse()
    return history


def add_reminder(user_id: int, title: str, reminder_time: str, notes: str = "") -> int:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO reminders (user_id, title, reminder_time, notes)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, title, reminder_time, notes),
        )
        connection.commit()
        return int(cursor.lastrowid)


def fetch_reminders(user_id: int) -> list[dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, title, reminder_time, notes, is_completed, created_at, updated_at
            FROM reminders
            WHERE user_id = ?
            ORDER BY is_completed ASC, reminder_time ASC, id DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "medicine_name": row["title"],
            "reminder_time": row["reminder_time"],
            "time": row["reminder_time"],
            "notes": row["notes"] or "",
            "is_completed": bool(row["is_completed"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def update_reminder_status(user_id: int, reminder_id: int, is_completed: bool) -> dict[str, object] | None:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE reminders
            SET is_completed = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (int(is_completed), reminder_id, user_id),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return None

        row = connection.execute(
            """
            SELECT id, user_id, title, reminder_time, notes, is_completed, created_at, updated_at
            FROM reminders
            WHERE id = ? AND user_id = ?
            """,
            (reminder_id, user_id),
        ).fetchone()
        connection.commit()

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "medicine_name": row["title"],
        "reminder_time": row["reminder_time"],
        "time": row["reminder_time"],
        "notes": row["notes"] or "",
        "is_completed": bool(row["is_completed"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM reminders
            WHERE id = ? AND user_id = ?
            """,
            (reminder_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def get_user_dashboard_stats(user_id: int) -> dict[str, object]:
    with get_connection() as connection:
        reminder_row = connection.execute(
            """
            SELECT
                COUNT(*) AS total_reminders,
                SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END) AS pending_reminders,
                SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed_reminders
            FROM reminders
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        chat_row = connection.execute(
            """
            SELECT COUNT(*) AS total_messages
            FROM chat_history
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return {
        "total_reminders": int(reminder_row["total_reminders"] or 0),
        "pending_reminders": int(reminder_row["pending_reminders"] or 0),
        "completed_reminders": int(reminder_row["completed_reminders"] or 0),
        "total_messages": int(chat_row["total_messages"] or 0),
    }
