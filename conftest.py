import pytest

from server import MemcacheServer
from store import Store

import io
import sqlite3

import structlog


shared_processors = [
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt='iso'),
]

structlog_processors = [
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

structlog.configure(
    processors=shared_processors + structlog_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

@pytest.fixture()
def conn():
    return sqlite3.connect(':memory:')

@pytest.fixture()
def commit_log():
    return io.BytesIO()

@pytest.fixture()
def s1(conn, commit_log):
    s1 = Store(conn, commit_log)
    s1.load_db() # to load tables
    s1.sync_commit_log() # should no-op
    assert len(s1) == 0
    return s1

@pytest.fixture()
def server(s1):
    return MemcacheServer(s1)
