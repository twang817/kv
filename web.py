from aiohttp import web


class HttpServer(object):
    def __init__(self, store):
        self.store = store
        self.app = web.Application()
        self.app.router.add_routes([
            web.get('/api/health', self.health_check),
            web.get('/api/keys', self.handle_keys),
        ])

    def make_handler(self):
        return self.app.make_handler()

    def health_check(self, request):
        return web.json_response({'statis': 'ok'})

    def handle_keys(self, request):
        return web.json_response({
            'keys': [k.decode() for k in self.store.keys()],
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
