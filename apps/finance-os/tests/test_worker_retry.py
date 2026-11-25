"""Worker retry/dead-letter unit tests with no live Postgres or Stripe calls."""
import os
import sys
from contextlib import nullcontext
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import worker


class FakeConnection:
    def __init__(self, rows, failures=()):
        self.rows = rows
        self.failures = set(failures)
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def transaction(self):
        return nullcontext()

    def execute(self, sql, args):
        self.commands.append((sql, args))
        if 'INSERT INTO finance_activity' in sql and args[0] in self.failures:
            raise ValueError('sensitive detail is not stored')
        return self

    def fetchall(self):
        return self.rows


class FakePsycopg:
    def __init__(self, connection):
        self.connection = connection

    def connect(self, dsn, connect_timeout):
        assert dsn.startswith('postgresql://')
        assert connect_timeout == 5
        return self.connection


class WorkerRetryTests(TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'APP_ENV': 'test', 'ENABLE_STRIPE_WRITES': 'false',
                                         'DATABASE_URL': 'postgresql://localhost/mock'})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def run_with(self, connection):
        with patch.dict(sys.modules, {'psycopg': FakePsycopg(connection)}):
            return worker.process_batch()

    def test_processed_event_marks_done(self):
        conn = FakeConnection([('evt_ok', 'core8', 'invoice.paid', 'in_1')])
        self.assertEqual(self.run_with(conn), 1)
        self.assertTrue(any("status='processed'" in sql for sql, _ in conn.commands))
        self.assertFalse(any('SET attempts=attempts+1' in sql for sql, _ in conn.commands))

    def test_single_event_failure_does_not_block_next(self):
        rows = [('evt_bad', 'core8', 'invoice.paid', 'in_1'),
                ('evt_ok', 'core8', 'invoice.paid', 'in_2')]
        conn = FakeConnection(rows, failures={'evt_bad'})
        self.assertEqual(self.run_with(conn), 1)
        self.assertTrue(any('SET attempts=attempts+1' in sql and args[-1] == 'evt_bad'
                            for sql, args in conn.commands))
        self.assertTrue(any("status='processed'" in sql and args[-1] == 'evt_ok'
                            for sql, args in conn.commands))

    def test_dead_letter_at_five_with_capped_backoff(self):
        conn = FakeConnection([('evt_bad', 'core8', 'invoice.paid', 'in_1')], failures={'evt_bad'})
        self.run_with(conn)
        retry = [(sql, args) for sql, args in conn.commands if 'SET attempts=attempts+1' in sql]
        self.assertEqual(len(retry), 1)
        self.assertIn("THEN 'dead' ELSE 'failed'", retry[0][0])
        self.assertIn('LEAST(POWER(2, attempts), 60)', retry[0][0])
        self.assertEqual(retry[0][1], (5, 5, 'evt_bad'))

    def test_no_stripe_write_or_non_sandbox(self):
        with patch.dict(os.environ, {'ENABLE_STRIPE_WRITES': 'true'}):
            with self.assertRaises(RuntimeError):
                worker.process_batch()
        with patch.dict(os.environ, {'APP_ENV': 'production'}):
            with self.assertRaises(RuntimeError):
                worker.process_batch()

    def test_fail_closed_without_dsn_or_invalid_limit(self):
        with patch.dict(os.environ, {'DATABASE_URL': ''}):
            with self.assertRaises(RuntimeError):
                worker.process_batch()
        for limit in (0, 101, True, 1.5):
            with self.assertRaises(ValueError):
                worker.process_batch(limit)
