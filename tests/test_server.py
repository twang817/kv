import server


def test_dispatch_cmds(server, s1):
    resp = server.dispatch(b'SET foo 1 2 bar')
    assert s1[b'foo'].data == b'bar'
    assert resp == b'STORED'

    resp = server.dispatch(b'GET foo')
    assert resp == b'VALUE foo 1 3\r\nbar\r\nEND'

    resp = server.dispatch(b'GET bar')
    assert resp == b'END'

    resp = server.dispatch(b'DELETE foo')
    assert b'foo' not in s1
    assert resp == b'DELETED'

    resp = server.dispatch(b'DELETE foo')
    assert resp == b'NOT_FOUND'

    resp = server.dispatch(b'BADCMD')
    assert resp == b'ERROR'
