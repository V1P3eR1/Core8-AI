"""Standalone worker process:  python -m social.worker

Runs the scheduler tick loop (research / planning / report jobs + due
publications) against the same SQLite file as the API. Several workers may
run at once — claims are transactional. Stop with Ctrl+C.
"""

import asyncio
import logging
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    from database import init_db
    from social.jobs import worker_loop
    from social.schema import init_social_schema

    await init_db()
    await init_social_schema()
    stop = {"flag": False}

    def _stop(*_):
        stop["flag"] = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _stop)
        except (NotImplementedError, RuntimeError):  # Windows
            signal.signal(sig, _stop)
    await worker_loop(is_stopped=lambda: stop["flag"])


if __name__ == "__main__":
    asyncio.run(main())
