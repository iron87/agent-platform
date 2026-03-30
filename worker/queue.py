"""rq Queue factory and job enqueue helpers for async batch processing.

Provides:
- Queue initialization with retry and timeout policies
- Job enqueue helpers that bridge API -> rq -> PostgreSQL updates
- Task callback integration for status synchronization
- Graceful handling of rq unavailability
"""

from dataclasses import dataclass
from typing import Any, Mapping
import structlog

logger = structlog.get_logger(__name__)

DEFAULT_RETRY_INTERVALS = (30, 120, 300)
DEFAULT_RESULT_TTL_SECONDS = 86400
DEFAULT_FAILURE_TTL_SECONDS = 7 * 86400


class QueueUnavailableError(Exception):
    """Raised when rq Queue or Redis is unavailable."""

    pass


@dataclass(frozen=True)
class AgentJobEnqueueRequest:
    job_id: str
    client_id: str
    agent_id: str
    input: str
    session_id: str | None = None
    metadata: Mapping[str, Any] | None = None
    mode: str = "async"
    queue_name: str = "agent_jobs"
    task_path: str = "worker.tasks.run_agent_job"
    timeout_seconds: int | None = None
    max_retries: int = 3
    retry_intervals: tuple[int, ...] = DEFAULT_RETRY_INTERVALS
    result_ttl_seconds: int = DEFAULT_RESULT_TTL_SECONDS
    failure_ttl_seconds: int = DEFAULT_FAILURE_TTL_SECONDS

    def to_payload(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "client_id": self.client_id,
            "agent_id": self.agent_id,
            "input": self.input,
            "session_id": self.session_id,
            "metadata": dict(self.metadata or {}),
            "mode": self.mode,
        }


def create_queue(
    redis_url: str,
    queue_name: str = "agent_jobs",
    job_timeout_seconds: int = 300,
) -> Any:
    """Create an rq Queue with retry and timeout policies.

    Args:
        redis_url: Redis connection URL (e.g., "redis://localhost:6379")
        queue_name: Queue name (default "agent_jobs")
        job_timeout_seconds: Default job timeout (can be overridden per-job)

    Returns:
        rq.Queue instance

    Raises:
        QueueUnavailableError: If Redis is unreachable
    """
    try:
        from redis import Redis
        from rq import Queue

        redis_conn = Redis.from_url(redis_url)

        # Test connectivity
        redis_conn.ping()

        queue = Queue(
            queue_name,
            connection=redis_conn,
            default_timeout=job_timeout_seconds,
        )

        logger.info(
            "rq_queue_created",
            queue_name=queue_name,
            redis_url=redis_url.split("@")[1] if "@" in redis_url else redis_url,
            timeout_seconds=job_timeout_seconds,
        )

        return queue

    except ImportError as e:
        raise QueueUnavailableError(f"rq or redis not installed: {e}")
    except Exception as e:
        raise QueueUnavailableError(f"Failed to connect to Redis: {e}")


def enqueue_job(
    queue: Any,
    task_path: str,
    job_payload: dict[str, Any],
    *,
    job_id: str,
    client_id: str,
    timeout_seconds: int | None = None,
    max_retries: int = 3,
    retry_intervals: list[int] | None = None,
    meta: dict[str, Any] | None = None,
    result_ttl_seconds: int = DEFAULT_RESULT_TTL_SECONDS,
    failure_ttl_seconds: int = DEFAULT_FAILURE_TTL_SECONDS,
) -> Any:
    """Enqueue a job to the rq queue with retry and callback configuration.

    Args:
        queue: rq.Queue instance from create_queue()
        task_path: Path to task function (e.g., "worker.tasks.run_agent_job")
        job_payload: Dictionary of arguments to pass to the task
        job_id: Unique job identifier (UUID string, used for idempotency)
        client_id: Tenant identifier (attached as metadata)
        timeout_seconds: Job timeout (None = use queue default)
        max_retries: Number of retries on failure
        retry_intervals: List of retry delay seconds; defaults to [30, 120, 300]

    Returns:
        rq.Job instance

    Raises:
        QueueUnavailableError: If enqueue fails
    """
    if retry_intervals is None:
        retry_intervals = [30, 120, 300]

    try:
        from rq import Retry

        retry_policy = Retry(
            max=max_retries,
            interval=retry_intervals[:max_retries],
        )

        job = queue.enqueue(
            task_path,
            job_payload,
            job_id=str(job_id),
            retry=retry_policy,
            timeout=timeout_seconds,
            result_ttl=result_ttl_seconds,
            failure_ttl=failure_ttl_seconds,
            meta=meta or {"client_id": client_id},
        )

        logger.info(
            "job_enqueued",
            job_id=job_id,
            client_id=client_id,
            task=task_path,
            queue=queue.name,
            retries=max_retries,
            timeout_seconds=timeout_seconds,
            result_ttl_seconds=result_ttl_seconds,
            failure_ttl_seconds=failure_ttl_seconds,
        )

        return job

    except Exception as e:
        logger.error(
            "job_enqueue_failed",
            job_id=job_id,
            client_id=client_id,
            task=task_path,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise QueueUnavailableError(f"Failed to enqueue job: {e}")


def enqueue_agent_job(*, redis_url: str, request: AgentJobEnqueueRequest) -> Any:
    """Enqueue an async agent job using the request envelope used by the API layer."""
    queue = create_queue(
        redis_url,
        queue_name=request.queue_name,
        job_timeout_seconds=request.timeout_seconds or 300,
    )
    return enqueue_job(
        queue,
        request.task_path,
        request.to_payload(),
        job_id=request.job_id,
        client_id=request.client_id,
        timeout_seconds=request.timeout_seconds,
        max_retries=request.max_retries,
        retry_intervals=list(request.retry_intervals),
        meta={
            "client_id": request.client_id,
            "agent_id": request.agent_id,
            "mode": request.mode,
        },
        result_ttl_seconds=request.result_ttl_seconds,
        failure_ttl_seconds=request.failure_ttl_seconds,
    )


def get_job_status(queue: Any, job_id: str) -> dict[str, Any] | None:
    """Retrieve job status from rq.

    Args:
        queue: rq.Queue instance
        job_id: Job identifier

    Returns:
        Dictionary with 'status', 'result', 'exc_info', etc.; None if job not found
    """
    try:
        job = queue.fetch_job(job_id)
        if job is None:
            return None

        return {
            "job_id": job.id,
            "status": job.get_status(),
            "result": job.result,
            "exc_info": job.exc_info,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "ended_at": job.ended_at,
        }

    except Exception as e:
        logger.warning(
            "job_status_fetch_failed",
            job_id=job_id,
            error=str(e),
        )
        return None


def cancel_job(queue: Any, job_id: str) -> bool:
    """Cancel a queued or running job.

    Args:
        queue: rq.Queue instance
        job_id: Job identifier

    Returns:
        True if job was cancelled, False if not found or already completed
    """
    try:
        job = queue.fetch_job(job_id)
        if job is None:
            return False

        if job.get_status() in ["queued", "started"]:
            job.cancel()
            logger.info("job_cancelled", job_id=job_id)
            return True

        return False

    except Exception as e:
        logger.warning(
            "job_cancel_failed",
            job_id=job_id,
            error=str(e),
        )
        return False


class JobCallbackBridge:
    """Bridge between rq job callbacks and PostgreSQL status updates.

    rq callbacks (on_success, on_failure) notify this class, which then
    updates the PostgreSQL jobs table.

    Usage:
        bridge = JobCallbackBridge(db_engine, jobs_repo)
        job = queue.enqueue(
            task_path,
            payload,
            on_success=bridge.on_job_success,
            on_failure=bridge.on_job_failure,
        )
    """

    def __init__(self, job_repository: Any) -> None:
        """Initialize callback bridge.

        Args:
            job_repository: JobsRepository instance for updating job status
        """
        self.job_repo = job_repository
        logger.info("job_callback_bridge_initialized")

    def on_job_success(self, job: Any, connection: Any, result: Any) -> None:
        """Called by rq on successful job completion.

        Args:
            job: rq.Job instance
            connection: Redis connection
            result: Job result (return value from task)
        """
        # This would run in rq worker context; async update deferred to reconciliation
        logger.info(
            "job_success_callback",
            job_id=job.id,
            rq_status=job.get_status(),
        )

    def on_job_failure(self, job: Any, connection: Any, type_: Any, value: Any, traceback: Any) -> None:
        """Called by rq on job failure.

        Args:
            job: rq.Job instance
            connection: Redis connection
            type_: Exception type
            value: Exception instance
            traceback: Traceback object
        """
        logger.error(
            "job_failure_callback",
            job_id=job.id,
            rq_status=job.get_status(),
            exc_type=type_.__name__ if type_ else None,
            exc_message=str(value) if value else None,
        )


__all__ = [
    "AgentJobEnqueueRequest",
    "DEFAULT_FAILURE_TTL_SECONDS",
    "DEFAULT_RESULT_TTL_SECONDS",
    "DEFAULT_RETRY_INTERVALS",
    "create_queue",
    "enqueue_job",
    "enqueue_agent_job",
    "get_job_status",
    "cancel_job",
    "JobCallbackBridge",
    "QueueUnavailableError",
]
