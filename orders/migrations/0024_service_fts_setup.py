# orders/migrations/0024_service_fts_setup.py

from django.db import migrations

# SQL для создания виртуальной FTS-таблицы и триггеров для её обновления.
# Этот код будет работать и в SQLite, и в PostgreSQL (с небольшими отличиями).
CREATE_FTS_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS service_fts USING fts5(
    name,
    content='service',
    content_rowid='id'
);
"""

POPULATE_FTS_TABLE_SQL = """
INSERT INTO service_fts (rowid, name)
SELECT id, name FROM orders_service;
"""

# Триггеры для автоматической синхронизации
CREATE_TRIGGERS_SQL = [
    """
    CREATE TRIGGER IF NOT EXISTS service_after_insert
    AFTER INSERT ON orders_service
    BEGIN
        INSERT INTO service_fts (rowid, name)
        VALUES (new.id, new.name);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS service_after_delete
    AFTER DELETE ON orders_service
    BEGIN
        DELETE FROM service_fts WHERE rowid=old.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS service_after_update
    AFTER UPDATE ON orders_service
    BEGIN
        UPDATE service_fts SET name = new.name WHERE rowid=old.id;
    END;
    """
]

class Migration(migrations.Migration):

    dependencies = [
        # Укажи здесь свою последнюю миграцию для orders
        ('orders', '0023_alter_order_status_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_FTS_TABLE_SQL,
            reverse_sql="DROP TABLE IF EXISTS service_fts;"
        ),
        migrations.RunSQL(
            sql=POPULATE_FTS_TABLE_SQL,
            reverse_sql="DELETE FROM service_fts;"
        ),
        # Добавляем каждый триггер отдельно
        migrations.RunSQL(
            sql=CREATE_TRIGGERS_SQL[0],
            reverse_sql="DROP TRIGGER IF EXISTS service_after_insert;"
        ),
        migrations.RunSQL(
            sql=CREATE_TRIGGERS_SQL[1],
            reverse_sql="DROP TRIGGER IF EXISTS service_after_delete;"
        ),
        migrations.RunSQL(
            sql=CREATE_TRIGGERS_SQL[2],
            reverse_sql="DROP TRIGGER IF EXISTS service_after_update;"
        ),
    ]