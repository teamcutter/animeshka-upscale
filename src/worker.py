"""Standalone job worker: takes queued jobs from the database and runs the upscaler.

    uv run python -m src.worker          # run until Ctrl+C
    uv run python -m src.worker --once   # drain the queue and exit

Several workers can run at once: each job is claimed atomically.
"""

import argparse
import logging
import signal
import sys
import threading

from src.container import Container
from src.core.config import Settings

logger = logging.getLogger("src.worker")


def run(settings: Settings | None = None, *, once: bool = False) -> int:
    """Process jobs until stopped (or, with once=True, until the queue is empty).

    Returns the number of processed jobs.
    """
    settings = settings or Settings()
    container = Container.build(settings)
    container.startup(load_models=True)
    stop = threading.Event()

    def request_stop(signum: int, _: object) -> None:
        logger.info("Got signal %s, finishing the current job", signum)
        stop.set()

    previous_handlers = {}
    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, request_stop)

    processed = 0
    logger.info("Worker started (backend=%s)", settings.upscale.backend)
    try:
        while not stop.is_set():
            try:
                took_job = container.upscale_service.process_next()
            except Exception:
                # e.g. the database restarted: log it and retry instead of dying.
                logger.exception("Failed to fetch the next job")
                took_job = False
            if took_job:
                processed += 1
            elif once:
                break
            else:
                stop.wait(settings.worker.poll_interval)
    finally:
        container.shutdown()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    logger.info("Worker stopped, processed %d job(s)", processed)
    return processed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="animeshka-worker", description=__doc__)
    parser.add_argument("--once", action="store_true", help="drain the queue and exit")
    args = parser.parse_args(argv)

    settings = Settings()
    logging.basicConfig(
        level=settings.log.level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run(settings, once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
