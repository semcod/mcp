from __future__ import annotations

from rq import Worker

import server


def main() -> None:
    redis_client = server._get_rq_redis_client()
    if redis_client is None:
        raise RuntimeError("Redis is unavailable. Check REDIS_URL and Redis service health.")

    worker = Worker([server.RQ_QUEUE_NAME], connection=redis_client)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
