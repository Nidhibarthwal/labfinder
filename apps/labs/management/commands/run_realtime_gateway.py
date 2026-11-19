"""
Django management command to run the FastAPI real-time SSE gateway.

Usage:
    python manage.py run_realtime_gateway [--host 0.0.0.0] [--port 8001]
"""

import os
import sys
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand

BASE_DIR = Path(__file__).resolve().parents[4]
GATEWAY_DIR = BASE_DIR / "apps" / "fastapi_gateway"


class Command(BaseCommand):
    help = "Starts the FastAPI real-time SSE Gateway (Uvicorn)"

    def add_arguments(self, parser):
        parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
        parser.add_argument("--port", type=int, default=8001, help="Port to listen on (default: 8001)")
        parser.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload on code change")

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        reload_flag = options["reload"]

        self.stdout.write(self.style.SUCCESS(f"Starting LabFinder Real-Time Gateway on http://{host}:{port}..."))

        env = os.environ.copy()
        env["PYTHONPATH"] = str(GATEWAY_DIR)

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            host,
            "--port",
            str(port),
        ]
        if reload_flag:
            cmd.append("--reload")

        try:
            subprocess.run(cmd, cwd=str(GATEWAY_DIR), env=env)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Gateway stopped by user."))
