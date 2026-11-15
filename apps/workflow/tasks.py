from celery import shared_task
import logging
from .engine import WorkflowEngine
from apps.analysis.models import AnalysisJob

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1, default_retry_delay=10)
def execute_analysis_workflow_task(self, job_id: str):
    """
    Celery background worker task to run the website analysis workflow.
    """
    logger.info(f"Starting Celery background execution for Job {job_id}")
    try:
        engine = WorkflowEngine(job_id=job_id)
        job = engine.execute()
        return {"job_id": str(job.id), "status": job.status}
    except Exception as exc:
        logger.exception(f"Exception during celery task execution for Job {job_id}: {exc}")
        try:
            job = AnalysisJob.objects.get(id=job_id)
            job.status = 'FAILED'
            job.error_code = 'WORKER_TASK_ERROR'
            job.error_detail = str(exc)
            job.save(update_fields=['status', 'error_code', 'error_detail', 'updated_at'])
        except Exception:
            pass
        raise exc
