# app/db.py
"""
Database pool + auto-install of NOTIFY triggers on startup.

Reads the table list from config/watched_tables.json (via app.config) and
attaches a generic trigger to that table on the public schema.
Extracts branch_id / lab_id dynamically and protects against Postgres 8KB pg_notify limits.
Fully idempotent -- safe to run on every server restart.
"""

import logging
import asyncpg

from app.config import DATABASE_URL, NOTIFY_CHANNEL, load_watched_tables

logger = logging.getLogger("labfinder-realtime")

TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION notify_row_change() RETURNS trigger AS $$
DECLARE
    payload jsonb;
    payload_text text;
    target_branch_id text := '';
    row_data jsonb;
    u_name text := '';
BEGIN
    IF TG_OP = 'DELETE' THEN
        row_data := to_jsonb(OLD);
    ELSE
        row_data := to_jsonb(NEW);
    END IF;

    -- Build clean payload tailored per table
    IF TG_TABLE_NAME = 'labs_branch' THEN
        target_branch_id := COALESCE(row_data->>'id', '');
        row_data := jsonb_build_object(
            'id', row_data->'id',
            'lab_name', row_data->'lab_name',
            'description', row_data->'description',
            'about_us', row_data->'about_us',
            'min_order_value', row_data->'min_order_value',
            'contact_mobile', row_data->'contact_mobile',
            'contact_email', row_data->'contact_email',
            'lab_address', row_data->'lab_address',
            'lab_city', row_data->'lab_city',
            'lab_pincode', row_data->'lab_pincode',
            'approval_status', row_data->'approval_status',
            'status', row_data->'status',
            'updated_at', row_data->'updated_at'
        );
    ELSIF TG_TABLE_NAME = 'enquiries_labreview' THEN
        target_branch_id := COALESCE(row_data->>'lab_id', '');
        BEGIN
            IF (row_data ? 'user_id') AND (row_data->>'user_id') IS NOT NULL THEN
                SELECT COALESCE(NULLIF(TRIM(first_name || ' ' || last_name), ''), username, email)
                INTO u_name
                FROM auth_user
                WHERE id = (row_data->>'user_id')::int;

                row_data := jsonb_set(row_data, '{user_name}', to_jsonb(COALESCE(u_name, 'Client')));
            END IF;
        EXCEPTION WHEN OTHERS THEN
            NULL;
        END;
    ELSIF row_data ? 'lab_id' THEN
        target_branch_id := COALESCE(row_data->>'lab_id', '');
    ELSIF row_data ? 'branch_id' THEN
        target_branch_id := COALESCE(row_data->>'branch_id', '');
    END IF;

    payload := jsonb_build_object(
        'action', TG_OP,
        'table', TG_TABLE_NAME,
        'id', CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
        'branch_id', target_branch_id,
        'data', row_data
    );

    payload_text := payload::text;

    -- PostgreSQL pg_notify has a hard 8000-byte limit.
    -- If the payload exceeds 7500 bytes, send a lightweight signal with overflow: true
    IF octet_length(payload_text) > 7500 THEN
        payload := jsonb_build_object(
            'action', TG_OP,
            'table', TG_TABLE_NAME,
            'id', CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
            'branch_id', target_branch_id,
            'overflow', true
        );
        payload_text := payload::text;
    END IF;

    PERFORM pg_notify('__NOTIFY_CHANNEL__', payload_text);

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""".replace("__NOTIFY_CHANNEL__", NOTIFY_CHANNEL)


async def create_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    logger.info("DB connection pool created (min=2, max=10)")
    return pool


async def install_notify_triggers(pool: asyncpg.Pool):
    """Creates the notify function once, then attaches a trigger for each
    table in config/watched_tables.json in the public schema.
    Runs automatically on every app startup."""
    watched_tables = load_watched_tables()
    logger.info("Watched tables from config.json: %s", watched_tables)

    async with pool.acquire() as conn:
        await conn.execute(TRIGGER_FUNCTION_SQL)
        logger.info(
            "Trigger function notify_row_change() created/updated -> publishes to channel '%s'",
            NOTIFY_CHANNEL,
        )

        installed = 0
        for table_name in watched_tables:
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                )
                """,
                table_name,
            )
            if not table_exists:
                logger.warning(
                    "Table '%s' does not exist in 'public' schema -> skipping trigger install",
                    table_name
                )
                continue

            trigger_name = f"{table_name}_notify_trigger"
            await conn.execute(
                f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "public"."{table_name}"'
            )
            await conn.execute(
                f'''CREATE TRIGGER "{trigger_name}"
                    AFTER INSERT OR UPDATE OR DELETE ON "public"."{table_name}"
                    FOR EACH ROW EXECUTE FUNCTION notify_row_change()'''
            )
            installed += 1
            logger.info(
                "Trigger active: public.%s -> channel '%s'",
                table_name, NOTIFY_CHANNEL,
            )

        logger.info(
            "Trigger install finished: %d trigger(s) active on channel '%s'",
            installed, NOTIFY_CHANNEL,
        )
