import asyncio
import yaml

import click
import structlog

from dos import (
    do_configure_logging
)


logger = structlog.get_logger(__name__)


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

async def handle_memcache(reader, writer):
    while True:
        sep = b'\r\n'
        seplen = len(sep)

        if reader.at_eof():
            break

        try:
            data = await reader.readuntil(sep)
        except asyncio.IncompleteReadError as e:
            if e.partial:
                logger.warn('Incomplete read, ignoring partial: {}'.format(e.partial))
        except asyncio.LimitOverrunError as e:
            logger.warn('limit overrun, clearing buffer')
            if reader._buffer.startswith(sep, e.consumed):
                del reader._buffer[:e.consumed + seplen]
            else:
                reader._buffer.clear()
            reader._maybe_resume_transport()
        else:
            data = data.rstrip(sep)
            if data:
                writer.write(data + sep)
                await writer.drain()
    writer.close()


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
    do_configure_logging(ctx.default_map.get('logging'))

    loop = asyncio.get_event_loop()

    coro = asyncio.start_server(
        handle_memcache,
        bind,
        port,
        loop=loop)

    server = loop.run_until_complete(coro)

    logger.info('serving on {0[0]}:{0[1]}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info('stopping server')
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


if __name__ == '__main__':
    main(auto_envvar_prefix='KV')
