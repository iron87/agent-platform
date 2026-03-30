from __future__ import annotations

import worker.queue as queue_module


class _DummyQueue:
    def __init__(self, name: str) -> None:
        self.name = name


class _DummyJob:
    def __init__(self, job_id: str) -> None:
        self.id = job_id


def test_agent_job_enqueue_request_builds_payload() -> None:
    request = queue_module.AgentJobEnqueueRequest(
        job_id="job-1",
        client_id="client-1",
        agent_id="agent-1",
        input="summarize this",
        session_id="session-1",
        metadata={"source": "test"},
    )

    assert request.to_payload() == {
        "job_id": "job-1",
        "client_id": "client-1",
        "agent_id": "agent-1",
        "input": "summarize this",
        "session_id": "session-1",
        "metadata": {"source": "test"},
        "mode": "async",
    }


def test_enqueue_agent_job_uses_queue_and_retry_policy(monkeypatch) -> None:
    created: dict[str, object] = {}

    def fake_create_queue(redis_url: str, queue_name: str, job_timeout_seconds: int) -> _DummyQueue:
        created["redis_url"] = redis_url
        created["queue_name"] = queue_name
        created["job_timeout_seconds"] = job_timeout_seconds
        return _DummyQueue(queue_name)

    def fake_enqueue_job(queue, task_path, job_payload, **kwargs):
        created["queue"] = queue
        created["task_path"] = task_path
        created["job_payload"] = job_payload
        created["enqueue_kwargs"] = kwargs
        return _DummyJob("rq-job-1")

    monkeypatch.setattr(queue_module, "create_queue", fake_create_queue)
    monkeypatch.setattr(queue_module, "enqueue_job", fake_enqueue_job)

    request = queue_module.AgentJobEnqueueRequest(
        job_id="job-1",
        client_id="client-1",
        agent_id="agent-1",
        input="summarize this",
        metadata={"ticket_id": "SUP-1"},
        queue_name="agent_jobs",
        timeout_seconds=45,
    )

    job = queue_module.enqueue_agent_job(redis_url="redis://example", request=request)

    assert job.id == "rq-job-1"
    assert created["redis_url"] == "redis://example"
    assert created["queue_name"] == "agent_jobs"
    assert created["job_timeout_seconds"] == 45
    assert created["task_path"] == "worker.tasks.run_agent_job"
    assert created["job_payload"] == request.to_payload()
    assert created["enqueue_kwargs"]["max_retries"] == 3
    assert created["enqueue_kwargs"]["timeout_seconds"] == 45
    assert created["enqueue_kwargs"]["result_ttl_seconds"] == queue_module.DEFAULT_RESULT_TTL_SECONDS
    assert created["enqueue_kwargs"]["failure_ttl_seconds"] == queue_module.DEFAULT_FAILURE_TTL_SECONDS