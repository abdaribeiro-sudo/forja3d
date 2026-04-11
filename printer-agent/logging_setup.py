import logging
import os
import sys


def setup_logging() -> None:
    level = logging.DEBUG if os.getenv("AGENT_DEBUG") == "1" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
