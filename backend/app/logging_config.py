"""Application logging setup.

The app logs through the ``kinesis.*`` logger family (``kinesis.timing`` for the
per-analysis stage breakdown, ``kinesis.pose``, ``kinesis.auth``, ``kinesis.email``).
Uvicorn only configures its own ``uvicorn.*`` loggers, and the root logger defaults
to WARNING — so without this, every ``logger.info(...)`` from the app (including the
timing breakdown we rely on to profile the deployed pipeline) is silently dropped.

``configure_logging`` attaches a single stdout handler to the ``kinesis`` parent
logger at INFO (Render/most PaaS capture stdout). It is idempotent and safe to call
from both module import and the app lifespan.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("KINESIS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")
    )

    app_logger = logging.getLogger("kinesis")
    app_logger.setLevel(level)
    app_logger.addHandler(handler)
    # Don't also bubble up to the (unconfigured) root logger — avoids duplicate
    # lines if the root ever gains a handler, and keeps our format intact.
    app_logger.propagate = False

    _CONFIGURED = True
