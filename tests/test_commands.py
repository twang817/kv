import commands
import store

import io


def test_pack_unpack():
    set_cmd = commands.SetCommand(b'some_key', 1, 2, b'some_value')
    f = io.BytesIO(set_cmd.pack())
    c = commands.SetCommand.unpack(f)
    assert set_cmd.key == c.key
    assert set_cmd.flags == c.flags
    assert set_cmd.exptime == c.exptime
    assert set_cmd.data == c.data

    delete_cmd = commands.DeleteCommand(b'some_key')
    f = io.BytesIO(delete_cmd.pack())
    c = commands.DeleteCommand.unpack(f)
    assert delete_cmd.key == c.key

def test_set_cmd():
    key = b'some_key'
    value = b'some_value'
    d = {}
    c = commands.SetCommand(key, 1, 2, value)
    c.visit(d)
    assert key in d
    assert d[key].flags == 1
    assert d[key].exptime == 2
    assert d[key].data == value

def test_get_cmd():
    key = b'some_key'
    value = b'some_value'
    d = {key: store.StorageItem(1, 2, value)}
    c = commands.GetCommand(key)
    c.visit(d)
    assert d[key].flags == 1
    assert d[key].exptime == 2
    assert d[key].data == value

def test_delete_cmd():
    key = b'some_key'
    value = b'some_value'
    d = {key: store.StorageItem(1, 2, value)}
    c = commands.DeleteCommand(key)
    c.visit(d)
    assert key not in d
