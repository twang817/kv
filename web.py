from aiohttp import web
import structlog


logger = structlog.get_logger(__name__)


class HttpServer(object):
    def __init__(self, store):
        self.store = store
        self.app = web.Application()
        self.app.router.add_routes([
            web.get('/api/health', self.health_check),
            web.get('/api/keys', self.handle_keys),
            web.get('/api/values/{key}', self.handle_values),
        ])

    def make_handler(self):
        return self.app.make_handler()

    def health_check(self, request):
        return web.json_response({'statis': 'ok'})

    def handle_keys(self, request):
        return web.json_response({
            'keys': [k.decode() for k in self.store.keys()],
        })

    def handle_values(self, request):
        key = request.match_info.get('key', None)
        if not key:
            raise web.HTTPNotFound
        try:
            logger.debug('getting value for key {}'.format(key))
            value = self.store[key.encode()]
        except KeyError:
            raise web.HTTPNotFound
        return web.json_response({
            'value': value.data.decode(),
        })

    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                else:
                    await ws.send_str(msg.data + '/answer')
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.exception('ws connection closed with exception {}'.format(ws.exception()))

        logger.info('webscoket connection closed')
        return ws
