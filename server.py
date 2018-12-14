import asyncio

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)
import structlog

from commands import (
    DeleteCommand,
    DumpCommand,
    DumpCommitCommand,
    DumpLogCommand,
    SetCommand,
    GetCommand,
)


logger = structlog.get_logger(__name__)


REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration in seconds', ['command'])
REQUEST_ERRORS = Counter('request_errors', 'Exceptions thrown in request handlers', ['command'])
BYTES_IN = Counter('bytes_in', 'Network bytes in')
BYTES_OUT = Counter('bytes_out', 'Network bytes out')


class MemcacheServer(object):
    sep = b'\r\n'
    seplen = len(sep)

    def __init__(self, store):
        self.store = store

    async def cmd_set(self, reader, key, flags, exptime, datalen, noreply=None):
        datalen = int(datalen)
        data = await reader.readexactly(datalen + 2)
        BYTES_IN.inc(len(data))
        data = data.rstrip(self.sep)
        self.store.apply(SetCommand(key, flags, exptime, data))
        if noreply is None:
            return b'STORED'

    async def cmd_get(self, reader, *keys):
        resp = []
        for key in keys:
            try:
                item = self.store.apply(GetCommand(key))
            except KeyError:
                pass
            else:
                resp.append(b'VALUE %s %d %d' % (key, item.flags, len(item.data)))
                resp.append(item.data)
        resp.append(b'END')
        return b'\r\n'.join(resp)

    async def cmd_delete(self, reader, key, noreply=None):
        try:
            self.store.apply(DeleteCommand(key))
        except KeyError:
            resp = b'NOT_FOUND'
        else:
            resp = b'DELETED'
        finally:
            if noreply is None:
                return resp

    async def cmd_dump(self, reader):
        self.store.apply(DumpCommand())

    async def cmd_dumplog(self, reader):
        self.store.apply(DumpLogCommand())

    async def cmd_dumpcommit(self, reader):
        self.store.apply(DumpCommitCommand())

    async def handler(self, reader, writer):
        while True:
            if reader.at_eof():
                break
            try:
                buf = await reader.readuntil(self.sep)
                BYTES_IN.inc(len(buf))
            except asyncio.IncompleteReadError as e:
                if e.partial:
                    logger.warn('Incomplete read, ignoring partial: {}'.format(e.partial))
            except asyncio.LimitOverrunError as e:
                logger.warn('limit overrun, clearing buffer')
                if reader._buffer.startswith(self.sep, e.consumed):
                    del reader._buffer[:e.consumed + self.seplen]
                else:
                    reader._buffer.clear()
                reader._maybe_resume_transport()
            else:
                buf = buf.rstrip(self.sep)
                if buf:
                    resp = await self.dispatch(reader, buf)
                    if resp:
                        writer.write(resp + self.sep)
                        BYTES_OUT.inc(len(resp + self.sep))
                        await writer.drain()
        writer.close()

    async def dispatch(self, reader, buf):
        argv = buf.split(b' ')
        cmd, argv = argv[0], argv[1:]
        cmd = cmd.decode().lower()
        cmd_handler = getattr(self, 'cmd_%s' % cmd, None)
        if cmd_handler:
            with REQUEST_DURATION.labels(cmd).time():
                with REQUEST_ERRORS.labels(cmd).count_exceptions():
                    try:
                        return await cmd_handler(reader, *argv)
                    except Exception as e:
                        logger.exception('error processing command {}: {}'.format(cmd, e))
        else:
            logger.warn('received unknown command: %s', cmd)
            return b'ERROR'
