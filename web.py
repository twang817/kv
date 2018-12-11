from aiohttp import web


routes = web.RouteTableDef()

@routes.get('/')
async def handle(request):
    return web.json_response({'status': 'ok'})

webapp = web.Application()
webapp.add_routes(routes)
