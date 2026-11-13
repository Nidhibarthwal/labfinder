import logging
from typing import Optional, Dict, Any
from django.utils import timezone
from datetime import timedelta
from apps.analysis.models import Website, AnalysisJob, WorkflowState
from apps.crawler.normalizer import normalize_url, extract_domain
from apps.crawler.security import validate_url_security
from .tasks import execute_analysis_workflow_task
from .engine import WorkflowEngine

logger = logging.getLogger(__name__)

class JobManager:
    """
    Coordinates job creation, idempotency / cache checking, and worker dispatch.
    """

    @classmethod
    def create_and_dispatch_job(
        cls,
        url: str,
        objective: str = 'company_intelligence',
        options: Optional[Dict[str, Any]] = None,
        run_async: bool = True
    ) -> AnalysisJob:
        options = options or {}
        
        # 1. Normalize and validate basic URL
        normalized_url = normalize_url(url)
        if not normalized_url:
            raise ValueError(f"Invalid URL format: '{url}'")

        domain = extract_domain(normalized_url)
        if not domain:
            raise ValueError(f"Cannot extract domain from URL: '{url}'")

        # 2. Check Idempotency / Cache (if not forced refresh)
        force_refresh = options.get('force_refresh', False)
        if not force_refresh:
            recent_completed = AnalysisJob.objects.filter(
                website__domain=domain,
                objective=objective,
                status=WorkflowState.COMPLETED,
                created_at__gte=timezone.now() - timedelta(hours=2)
            ).order_by('-created_at').first()

            if recent_completed:
                logger.info(f"Returning cached/idempotent recent job {recent_completed.id} for domain {domain}")
                return recent_completed

        # 3. Create or retrieve Website
        website, _ = Website.objects.get_or_create(
            domain=domain,
            defaults={'root_url': normalized_url}
        )

        # 4. Create AnalysisJob
        job = AnalysisJob.objects.create(
            website=website,
            objective=objective,
            status=WorkflowState.PENDING,
            options=options,
        )

        # 5. Dispatch execution
        if run_async and not options.get('sync', False):
            # Fast check if Redis/Celery broker is reachable (timeout 0.2s)
            broker_available = False
            try:
                import redis
                from django.conf import settings
                broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
                r = redis.from_url(broker_url, socket_timeout=0.2)
                r.ping()
                broker_available = True
            except Exception:
                broker_available = False

            if broker_available:
                try:
                    execute_analysis_workflow_task.delay(str(job.id))
                    logger.info(f"Dispatched Job {job.id} to Celery worker queue.")
                except Exception as e:
                    broker_available = False

            if not broker_available:
                logger.info(f"Celery broker unavailable, running in background worker thread for job {job.id}")
                import threading
                def _run_worker():
                    try:
                        eng = WorkflowEngine(job_id=str(job.id))
                        eng.execute()
                    except Exception as err:
                        logger.error(f"Worker thread execution failed for job {job.id}: {err}")
                threading.Thread(target=_run_worker, daemon=True).start()
        else:
            logger.info(f"Executing Job {job.id} synchronously.")
            engine = WorkflowEngine(job_id=str(job.id))
            job = engine.execute()

        return job
