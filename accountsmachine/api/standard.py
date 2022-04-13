
# A load of boiler-plate web handlers

from aiohttp import web

def get_all(self, scope, cls):
    async def handler(self, request):
        request["auth"].verify_scope(scope)
        user = request["auth"].user

        try:
            i = await cls.get_all(request["state"])
            return web.json_response(i)
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
    return handler

def get(self, scope, cls):
    async def handler(self, request):
        request["auth"].verify_scope(scope)
        user = request["auth"].user
        id = request.match_info['id']
        o = cls(request["state"], id)
        try:
            info = await o.get()
        except KeyError:
            return web.HTTPNotFound()

        return web.json_response(info)
    return handler

def put(self, scope, cls):
    async def handler(self, request):
        request["auth"].verify_scope(scope)
        user = request["auth"].user
        id = request.match_info['id']
        info = await request.json()

        f = cls(request["state"], id)

        try:
            await f.put(info)
            return web.json_response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
    return handler

def delete(self, scope, cls):
    async def handler(self, request):
        request["auth"].verify_scope(scope)
        user = request["auth"].user
        id = request.match_info['id']

        f = cls(request["state"], id)

        try:
            await f.delete()
            return web.json_response()
        except Exception as e:
            return web.HTTPInternalServerError(
                body=str(e), content_type="text/plain"
            )
    return handler
