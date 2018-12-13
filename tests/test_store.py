import pytest

import commands
import store

def assert_commit_log(s, num_keys, key, value):
    for i, (commit_id, command) in enumerate(s.load_commits()):
        assert type(command) == commands.SetCommand
        assert command.key == key % i
        assert command.flags == i
        assert command.exptime == i * i
        assert command.data == value % i
    assert i == num_keys

def assert_commit_log_empty(s):
    for _ in s.load_commits():
        pytest.fail('commit log should be empty after flush')

def assert_store_equal(s1, s2):
    assert len(s2) == len(s1)

    for key, value in s1.items():
        assert key in s2
        assert s2[key].flags == s1[key].flags
        assert s2[key].exptime == s1[key].exptime
        assert s2[key].data == s1[key].data

INSERT = 1
UPDATE = 2
DELETE = 4

def assert_pending(s, key, status=0):
    attr = {
        INSERT: 'pending_insert',
        UPDATE: 'pending_update',
        DELETE: 'pending_delete',
    }
    for op in (INSERT, UPDATE, DELETE):
        if status & op:
            assert key in getattr(s, attr[op])
        else:
            assert key not in getattr(s, attr[op])

def test_store_set_get_delete(s1):
    key = b'some_key'
    value = b'some_value'

    s1[key] = store.StorageItem(1, 2, value)
    assert s1[key].flags == 1
    assert s1[key].exptime == 2
    assert s1[key].data == value
    del s1[key]
    assert key not in s1

def test_store_get_non_existant(s1):
    key = b'some_key'
    try:
        s1[key]
    except KeyError:
        assert key not in s1
    else:
        pytest.fail('get did not raise KeyError for non-existant key')

def test_store_delete_non_existant(s1):
    key = b'some_key'
    try:
        del s1[key]
    except KeyError:
        assert key not in s1
    else:
        pytest.fail('delete did not raise KeyError for non-existant key')

def test_store_db_save_load(s1, conn, commit_log):
    key = b'some_key_%d'
    value = b'some_value_%d'
    num_keys = 10

    for i in range(0, num_keys + 1):
        s1.apply(commands.SetCommand(key % i, i, i*i, value % i))

    s1.save_db()

    s2 = store.Store(conn, commit_log)
    s2.load_db()

    assert len(s2) == len(s1)

    for key, value in s1.items():
        assert key in s2
        assert s2[key].flags == s1[key].flags
        assert s2[key].exptime == s1[key].exptime
        assert s2[key].data == s1[key].data

def test_store_db_replay_commits(s1, conn, commit_log):
    key = b'some_key_%d'
    value = b'some_value_%d'
    num_keys = 10

    for i in range(0, num_keys + 1):
        s1.apply(commands.SetCommand(key % i, i, i*i, value % i))

    s2 = store.Store(conn, commit_log)

    s2.load_db()
    assert len(s2) == 0

    s2.sync_commit_log()
    assert len(s2) == len(s1)

    for key, value in s1.items():
        assert key in s2
        assert s2[key].flags == s1[key].flags
        assert s2[key].exptime == s1[key].exptime
        assert s2[key].data == s1[key].data

def test_store_db_the_big_one(s1, conn, commit_log):
    key1 = b'some_saved_key_%d'
    value1 = b'some_saved_value_%d'
    key2 = b'some_replay_key_%d'
    value2 = b'some_replay_value_%d'
    num_keys = 10

    for i in range(0, num_keys + 1):
        s1.apply(commands.SetCommand(key1 % i, i, i*i, value1 % i))
    assert_commit_log(s1, num_keys, key1, value1)

    s1.flush()
    assert_commit_log_empty(s1)

    for i in range(0, num_keys + 1):
        s1.apply(commands.SetCommand(key2 % i, i, i*i, value2 % i))
    assert_commit_log(s1, num_keys, key2, value2)

    s2 = store.Store(conn, commit_log)
    s2.load_db()
    s2.sync_commit_log()
    assert_store_equal(s1, s2)

def test_store_db_set_set(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))
    # assure insert is pending
    assert_pending(s1, key, INSERT)

    # set again without flushing
    s1.apply(commands.SetCommand(key, 1, 2, value % 2))
    # assert insert is still pending
    assert_pending(s1, key, INSERT)

def test_store_db_set_flush_set(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # assure insert is pending
    assert_pending(s1, key, INSERT)

    # flush key to database
    s1.flush()

    # set the key again
    s1.apply(commands.SetCommand(key, 1, 2, value % 2))

    # assert update is now pending
    assert_pending(s1, key, UPDATE)

def test_store_db_set_delete(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # assure insert is pending
    assert_pending(s1, key, INSERT)

    # delete the key without flushing
    s1.apply(commands.DeleteCommand(key))

    # assert it isn't in pending delete (it never existed)
    assert_pending(s1, key)

def test_store_db_set_flush_delete(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # assure insert is pending
    assert_pending(s1, key, INSERT)

    # flush key to database
    s1.flush()

    # delete the key
    s1.apply(commands.DeleteCommand(key))

    # assert delete is now pending
    assert_pending(s1, key, DELETE)

def test_store_db_delete_set(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # flush key to database
    s1.flush()

    # delete the key
    s1.apply(commands.DeleteCommand(key))

    # assert delete is pending
    assert_pending(s1, key, DELETE)

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # assert it is now pending update (cancel the delete, now needs updating)
    assert_pending(s1, key, UPDATE)

def test_store_db_delete_flush_set(s1):
    key = b'some_key'
    value = b'some_value_%d'

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # flush key to database
    s1.flush()

    # delete the key
    s1.apply(commands.DeleteCommand(key))

    # assert delete is pending
    assert_pending(s1, key, DELETE)

    # flush key to database
    s1.flush()

    # set a key
    s1.apply(commands.SetCommand(key, 1, 2, value % 1))

    # assert it is now pending insert
    assert_pending(s1, key, INSERT)
