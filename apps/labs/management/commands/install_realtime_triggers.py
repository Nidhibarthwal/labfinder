"""
Django management command to install the PostgreSQL LISTEN/NOTIFY triggers
for LabFinder real-time updates.

Usage:
    python manage.py install_realtime_triggers
"""

import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import connection

BASE_DIR = Path(__file__).resolve().parents[4]
CONFIG_PATH = BASE_DIR / "apps" / "fastapi_gateway" / "config" / "watched_tables.json"
NOTIFY_CHANNEL = "labfinder_realtime"

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


class Command(BaseCommand):
    help = "Installs PostgreSQL LISTEN/NOTIFY triggers for real-time updates."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.ERROR(f"Database vendor is {connection.vendor}, triggers require PostgreSQL."))
            return

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            watched_tables = json.load(f).get("watched_tables", [])

        self.stdout.write(f"Installing triggers for tables: {watched_tables}")

        with connection.cursor() as cursor:
            cursor.execute(TRIGGER_FUNCTION_SQL)
            self.stdout.write(self.style.SUCCESS(f"Created/updated trigger function notify_row_change() on channel '{NOTIFY_CHANNEL}'"))

            installed = 0
            for table_name in watched_tables:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = %s
                    )
                    """,
                    [table_name],
                )
                if not cursor.fetchone()[0]:
                    self.stdout.write(self.style.WARNING(f"Table 'public.{table_name}' does not exist, skipping."))
                    continue

                trigger_name = f"{table_name}_notify_trigger"
                cursor.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "public"."{table_name}"')
                cursor.execute(
                    f'''CREATE TRIGGER "{trigger_name}"
                        AFTER INSERT OR UPDATE OR DELETE ON "public"."{table_name}"
                        FOR EACH ROW EXECUTE FUNCTION notify_row_change()'''
                )
                installed += 1
                self.stdout.write(self.style.SUCCESS(f"Attached trigger to public.{table_name}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully installed {installed} real-time trigger(s)."))
