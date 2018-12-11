import struct

import structlog

from base import Command
from store import StorageItem
from utils import unpack, unpack_vls


logger = structlog.get_logger(__name__)


class DumpCommand(Command):
    def visit(self, store):
        logger.debug(str(store.data))

class DumpCommitCommand(Command):
    def visit(self, store):
        logger.debug(str(store.commit_id))

class DumpLogCommand(Command):
    def visit(self, store):
        store.dump_commit_log()

class SetCommand(Command):
    opcode = 1
    def __init__(self, key, flags, exptime, data):
        self.key = key
        self.flags = int(flags)
        self.exptime = int(exptime)
        self.data = data

    def visit(self, store):
        logger.debug('SET %s %d %d %s', self.key, self.flags, self.exptime, self.data)
        store[self.key] = StorageItem(self.flags, self.exptime, self.data)

    def pack(self):
        return struct.pack(
            '=I%dsHII%ds' % (len(self.key), len(self.data)),
            len(self.key),
            self.key,
            self.flags,
            self.exptime,
            len(self.data),
            self.data)

    @classmethod
    def unpack(cls, f):
        key = unpack_vls(f)
        flags, exptime = unpack(f, '=HI')
        data = unpack_vls(f)
        return cls(key, flags, exptime, data)

    def __str__(self):
        return 'SET %s' % self.key

class GetCommand(Command):
    def __init__(self, key):
        self.key = key

    def visit(self, store):
        data = store[self.key]
        logger.debug('GET %s -> %s', self.key, data)
        return data

    def __str__(self):
        return 'GET %s' % self.key

class DeleteCommand(Command):
    opcode = 2
    def __init__(self, key):
        self.key = key

    def visit(self, store):
        logger.debug('DELETE %s', self.key)
        del store[self.key]

    def pack(self):
        return struct.pack(
            '=I%ds' % len(self.key),
            len(self.key),
            self.key)

    @classmethod
    def unpack(cls, f):
        key = unpack_vls(f)
        return cls(key)

    def __str__(self):
        return 'DELETE %s' % self.key

