# app/db.py
"""
Database pool + auto-install of NOTIFY triggers on startup.

Reads the table list from config/watched_tables.json (via app.config) and
attaches a generic trigger to that table on every tenant schema that has
it. Fully idempotent -- safe to run on every server restart.
"""

import logging

import asyncpg

from app.config import DATABASE_URL, NOTIFY_CHANNEL, load_watched_tables

logger = logging.getLogger("inventory-realtime")

TRIGGER_FUNCTION_SQL = f"""
CREATE OR REPLACE FUNCTION notify_row_change() RETURNS trigger AS $$
DECLARE
    payload json;
BEGIN
    IF TG_OP = 'DELETE' THEN
        payload := json_build_object(
            'action', 'DELETE',
            'table', TG_TABLE_NAME,
            'id', OLD.id,
            'tenant_id', TG_TABLE_SCHEMA,
            'data', NULL
        );
    ELSIF TG_OP = 'INSERT' THEN
        payload := json_build_object(
            'action', 'CREATE',
            'table', TG_TABLE_NAME,
            'id', NEW.id,
            'tenant_id', TG_TABLE_SCHEMA,
            'data', row_to_json(NEW)
        );
    ELSE
        payload := json_build_object(
            'action', 'UPDATE',
            'table', TG_TABLE_NAME,
            'id', NEW.id,
            'tenant_id', TG_TABLE_SCHEMA,
            'data', row_to_json(NEW)
        );
    END IF;

    PERFORM pg_notify('{NOTIFY_CHANNEL}', payload::text);

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    logger.info("DB connection pool created (min=2, max=10)")
    return pool


async def install_notify_triggers(pool: asyncpg.Pool):
    """Creates the notify function once, then attaches a trigger for each
    table in config/watched_tables.json to every tenant schema that has
    that table. Runs automatically on every app startup."""
    watched_tables = load_watched_tables()
    logger.info("Watched tables from config.json: %s", watched_tables)

    async with pool.acquire() as conn:
        await conn.execute(TRIGGER_FUNCTION_SQL)
        logger.info(
            "Trigger function notify_row_change() created/updated -> publishes to channel '%s'",
            NOTIFY_CHANNEL,
        )

        schemas = await conn.fetch(
            """
            SELECT nspname FROM pg_namespace
            WHERE nspname NOT IN ('public', 'pg_catalog', 'information_schema')
              AND nspname NOT LIKE 'pg_%'
            """
        )
        logger.info("Scanning %d tenant schema(s) for watched tables", len(schemas))

        installed = 0
        for record in schemas:
            schema_name = record["nspname"]
            for table_name in watched_tables:
                table_exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = $1 AND table_name = $2
                    )
                    """,
                    schema_name,
                    table_name,
                )
                if not table_exists:
                    logger.warning(
                        "Table '%s' does not exist in schema '%s' -> skipping trigger install",
                        table_name, schema_name
                    )
                    continue

                trigger_name = f"{table_name}_notify_trigger"
                await conn.execute(
                    f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{schema_name}"."{table_name}"'
                )
                await conn.execute(
                    f'''CREATE TRIGGER "{trigger_name}"
                        AFTER INSERT OR UPDATE OR DELETE ON "{schema_name}"."{table_name}"
                        FOR EACH ROW EXECUTE FUNCTION notify_row_change()'''
                )
                installed += 1
                logger.info(
                    "Trigger created: schema='%s' table='%s' -> will notify on channel '%s'",
                    schema_name, table_name, NOTIFY_CHANNEL,
                )

        logger.info(
            "Trigger install finished: %d trigger(s) active across %d schema(s), channel='%s'",
            installed, len(schemas), NOTIFY_CHANNEL,
        )