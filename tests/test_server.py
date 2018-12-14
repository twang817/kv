import pytest

import server

import asyncio

import asynctest


@pytest.mark.asyncio
async def test_dispatch_cmds(server, s1):
    reader = asynctest.mock.Mock(asyncio.StreamReader)
    reader.readexactly.return_value = b'bar\r\n'

    resp = await server.dispatch(reader, b'SET foo 1 2 3')
    assert s1[b'foo'].data == b'bar'
    assert resp == b'STORED'

    resp = await server.dispatch(reader, b'GET foo')
    assert resp == b'VALUE foo 1 3\r\nbar\r\nEND'

    resp = await server.dispatch(reader, b'GET bar')
    assert resp == b'END'

    resp = await server.dispatch(reader, b'DELETE foo')
    assert b'foo' not in s1
    assert resp == b'DELETED'

    resp = await server.dispatch(reader, b'DELETE foo')
    assert resp == b'NOT_FOUND'

    resp = await server.dispatch(reader, b'BADCMD')
    assert resp == b'ERROR'
