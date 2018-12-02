import logging
import logging.config

import structlog


def do_configure_logging(config):
    config = config or {}

    level = logging.getLevelName(config.get('level', 'INFO'))
    json = config.get('json', False)

    renderer = structlog.dev.ConsoleRenderer(colors=True)
    if json:
        renderer = structlog.processors.JSONRenderer()

    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
    ]

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'colored': {
                '()': structlog.stdlib.ProcessorFormatter,
                'processor': renderer,
                'foreign_pre_chain': shared_processors,
            },
        },
        'handlers': {
            'default': {
                'level': level,
                'class': 'logging.StreamHandler',
                'formatter': 'colored',
            }
        },
        'loggers': {
            '': {
                'handlers': ['default'],
                'level': level,
                'propagate': True,
            },
        }
    })

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
