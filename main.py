import asyncio
import logging
import logging.config
import sqlite3
import threading
import yaml

import click
import prometheus_client
import structlog

import commands
from server import MemcacheServer
from store import Store
from web import webapp


logger = structlog.get_logger(__name__)


def do_configure_logging(config):
    config = config or {}

    level = logging.getLevelName(config.get('level', 'INFO'))

    handlers = {
        'console': {
            'level': level,
            'class': 'logging.StreamHandler',
            'formatter': 'colored',
        }
    }

    filename = config.get('filename', None)
    if filename:
        handlers['file'] = {
            'level': level,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': filename,
            'mode': 'a',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'structured',
        }

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
                'processor': structlog.dev.ConsoleRenderer(colors=True),
                'foreign_pre_chain': shared_processors,
            },
            'structured': {
                '()': structlog.stdlib.ProcessorFormatter,
                'processor': structlog.processors.JSONRenderer(),
                'foreign_pre_chain': shared_processors,
            },
        },
        'handlers': handlers,
        'loggers': {
            '': {
                'handlers': [k for k in handlers],
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

def click_config_file(default_config_file):
    def parse_config_callback(ctx, param, value):
        try:
            with open(value or default_config_file) as f:
                config = yaml.load(f)
        except FileNotFoundError as e:
            if value is not None:
                raise click.BadParameter(str(e))
        else:
            if not ctx.default_map:
                ctx.default_map = {}
            ctx.default_map.update(config)

    return click.option('--config',
                        is_eager=True,
                        expose_value=False,
                        callback=parse_config_callback,
                        help='Read configuration from PATH')

@click.command()
@click.pass_context
@click_config_file(default_config_file='./kv.conf')
@click.option('--bind',
              default='127.0.0.1',
              help='ip for server to bind to')
@click.option('-p', '--port',
              default=11211,
              help='port for server to listen on')
@click.argument('db',
                type=click.Path(exists=True),
                envvar='KV_DATABASE')
def main(ctx, db, bind, port):
    do_configure_logging(ctx.default_map['logging'])

    logger.info('connecting to %s', db)
    conn = sqlite3.connect(db)

    logger.info('initializing store')
    commit_log = open(ctx.default_map['commit_log'], 'a+b')
    store = Store(conn, commit_log)
    store.load_db()
    store.sync_commit_log()

    loop = asyncio.get_event_loop()

    server = MemcacheServer(store)
    flush_task = loop.create_task(
        store.flush_loop(timeout=ctx.default_map['flush_timeout'])
    )

    metrics_conf = ctx.default_map['metrics']
    prometheus_client.start_http_server(
        metrics_conf['port'],
        metrics_conf['bind'])

    web_conf = ctx.default_map['web']
    coro = loop.create_server(
        webapp.make_handler(),
        host=web_conf['bind'],
        port=web_conf['port'])
    web_server = loop.run_until_complete(coro)
    logger.info('serving web application on {0[0]}:{0[1]}'.format(web_server.sockets[0].getsockname()))

    coro = asyncio.start_server(
        server.handler,
        bind,
        port,
        loop=loop)
    server = loop.run_until_complete(coro)
    logger.info('serving memcached server on {0[0]}:{0[1]}'.format(server.sockets[0].getsockname()))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info('stopping server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        flush_task.cancel()
        loop.run_until_complete(flush_task)
        loop.close()


if __name__ == '__main__':
    main(
        default_map={
            'bind': '0.0.0.0',
            'port': 11211,
            'flush_timeout': 5,
            'commit_log': 'commit.log',
            'web': {
                'bind': '0.0.0.0',
                'port': 8080,
            },
            'metrics': {
                'bind': '0.0.0.0',
                'port': 8090,
            },
            'logging': {
                'level': 'INFO',
                'filename': 'logs/kv.log',
            },
        },
        auto_envvar_prefix='KV'
    )
