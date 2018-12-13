import asyncio
from collections import defaultdict, namedtuple
from collections.abc import MutableMapping
import os
import struct
import uuid

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)
import structlog

from base import Command
from utils import unpack


logger = structlog.get_logger(__name__)


StorageItem = namedtuple('StorageItem', 'flags exptime data')


TABLE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS items (
    key TEXT PRIMARY KEY,
    flags INTEGER,
    exptime INTEGER,
    data BLOB
);'''

STATUS_SCHEMA = '''
CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY,
    commit_id BLOB
);'''


NUM_KEYS = Gauge('storage_num_keys', 'number of keys')
NUM_BYTES = Gauge('storage_data_bytes', 'size of data')
NUM_COMMITS = Counter('storage_num_commits', 'number of commits')
COMMIT_DURATION = Histogram('storage_commit_seconds', 'Duration of commits')
COMMIT_ERRORS = Counter('storage_commit_errors', 'Number of errors during commit')
NUM_DB_UPSERTS = Counter('storage_db_upserts', 'number of db upserts')
NUM_DB_DELETES = Counter('storage_db_deletes', 'number of db deletes')
NUM_DB_FLUSH = Counter('storage_db_num_flush', 'number of db flushes')
FLUSH_DURATION = Histogram('storage_flush_seconds', 'Duration of flush')
FLUSH_ERRORS = Counter('storage_flush_errors', 'Number of errors during flush')


class Store(MutableMapping):
    def __init__(self, conn, commit_log):
        self.data = {}
        self.commit_id = None
        self.conn = conn
        self.commit_log = commit_log
        self.pending_insert = set()
        self.pending_delete = set()
        self.pending_update = set()

    @property
    def dirty(self):
        return self.pending_insert or self.pending_update or self.pending_delete

    @property
    def pending_upsert(self):
        return self.pending_insert.union(self.pending_update)

    def load_db(self, conn=None):
        conn = conn or self.conn
        with conn:
            c = conn.cursor()
            c.execute('BEGIN')

            c.execute(TABLE_SCHEMA)
            c.execute(STATUS_SCHEMA)

            c.execute('SELECT * FROM items')
            rows = c.fetchall()
            for row in rows:
                NUM_KEYS.inc()
                key, item = row[0], StorageItem(*row[1:])
                self.data[key] = item
                NUM_BYTES.inc(len(item.data))
            logger.info('loaded {} rows from db'.format(len(rows)))

            c.execute('SELECT commit_id FROM status WHERE id = 1')
            row = c.fetchone()
            if row:
                commit_id = uuid.UUID(bytes=row[0])
                self.commit_id = commit_id
            logger.info('commit_id: {}'.format(self.commit_id))
            c.execute('COMMIT')

    def sync_commit_log(self, commit_log=None):
        commit_log = commit_log or self.commit_log
        # replay the commits from the log
        for commit_id, command in self.load_commits(commit_log):
            logger.info('replaying commit %s - %s', commit_id, command)
            command.visit(self)
            self.commit_id = commit_id

    def load_commits(self, commit_log=None):
        commit_log = commit_log or self.commit_log
        commit_log.seek(0)
        while True:
            commit_id = commit_log.read(16)
            if not commit_id:
                break
            commit_id = uuid.UUID(bytes=commit_id)
            op = unpack(commit_log, '=H')[0]
            for command in Command.__subclasses__():
                if op == command.opcode:
                    yield commit_id, command.unpack(commit_log)

    def dump_commit_log(self):
        logger.debug('commits log: %s', ['%s - %s' % (commit_id, command) for commit_id, command in self.load_commits()])

    async def flush_loop(self, conn=None, timeout=10):
        try:
            while True:
                await asyncio.sleep(timeout)
                self.flush(conn)

        except asyncio.CancelledError as e:
            logger.info('--cleanup--')

    def flush(self, conn=None, commit_log=None):
        conn = conn or self.conn
        commit_log = commit_log or self.commit_log

        if not self.dirty:
            return

        NUM_DB_FLUSH.inc()
        with FLUSH_DURATION.time():
            with FLUSH_ERRORS.count_exceptions():
                self.save_db(conn)

                # truncate commit log
                commit_log.seek(0)
                commit_log.truncate()

    def save_db(self, conn=None):
        conn = conn or self.conn
        with conn:
            c = conn.cursor()
            c.execute('BEGIN')

            if self.pending_upsert:
                values = []
                for key in self.pending_upsert:
                    NUM_DB_UPSERTS.inc()
                    item = self.data[key]
                    values.append((key, item.flags, item.exptime, item.data))
                logger.debug('values to update: %s', values)
                c.executemany('INSERT OR REPLACE INTO items (key, flags, exptime, data) VALUES (?, ?, ?, ?)', values)
            else:
                logger.debug('no values to update')


            if self.pending_delete:
                values = []
                for key in self.pending_delete:
                    NUM_DB_DELETES.inc()
                    logger.debug(key.decode())
                    values.append((key,))
                logger.debug('keys to delete: %s', values)
                c.executemany('DELETE FROM items WHERE key = ?', values)
            else:
                logger.debug('no keys to delete')

            logger.debug('saving commit %s', self.commit_id)
            c.execute('INSERT OR REPLACE INTO status (id, commit_id) VALUES (1, ?)', (self.commit_id.bytes,))

            c.execute('COMMIT')

        self.pending_insert.clear()
        self.pending_update.clear()
        self.pending_delete.clear()

    def apply(self, command):
        ret = command.visit(self)
        if command.opcode:
            NUM_COMMITS.inc()
            self.commit(command.opcode, command.pack())
        return ret

    @COMMIT_DURATION.time()
    @COMMIT_ERRORS.count_exceptions()
    def commit(self, opcode, data):
        self.commit_id = uuid.uuid1()
        logger.info('commiting {}'.format(self.commit_id))
        self.commit_log.write(self.commit_id.bytes)
        self.commit_log.write(struct.pack('=H', opcode))
        self.commit_log.write(data)
        self.commit_log.flush()
        try:
            os.fsync(self.commit_log.fileno())
        except IOError as e:
            logger.exception('error syncing commit file')

    def __setitem__(self, key, value):
        assert isinstance(value, StorageItem)
        if key not in self.data:
            NUM_KEYS.inc()
            if key not in self.pending_delete:
                # this means that the key did not exist in the
                # database, so we want to put it in pending insert
                self.pending_insert.add(key)
            else:
                # this means that the key was in the database
                # but we have deleted it locally.  in thise case
                # we want to clear the delete and add it to pending
                # update
                self.pending_delete.remove(key)
                self.pending_update.add(key)
        else:
            if key not in self.pending_insert:
                # this means we are updating a key that was already
                # in the database (its not pending insert), so we
                # need to mark the key as pending update
                self.pending_update.add(key)
            NUM_BYTES.dec(len(self.data[key].data))
        NUM_BYTES.inc(len(value.data))
        self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __delitem__(self, key):
        value = self.data[key]
        if key not in self.pending_insert:
            # this key was from the database, so much
            # delete it from the db
            self.pending_delete.add(key)
        else:
            # this key was not in the database and was
            # pending insert, so we simply remove it from
            # pending insert
            self.pending_insert.remove(key)
        NUM_KEYS.dec()
        NUM_BYTES.dec(len(value.data))
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)
