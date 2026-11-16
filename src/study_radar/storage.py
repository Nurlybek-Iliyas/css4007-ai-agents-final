"""Local, account-scoped snapshots. Missing records never imply completion."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .core import AppError, display_records, parse_due


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical(record):
    if not isinstance(record, dict) or not isinstance(record.get('id'), str) or not record['id']:
        raise AppError('Запись без идентификатора не сохранена.')
    if not isinstance(record.get('title'), str) or not record['title'].strip():
        raise AppError('Запись без названия не сохранена.')
    parse_due(record.get('due_at'))
    # Derived values change with time and must not generate false updates.
    return {k: v for k, v in record.items() if k not in {
        'hours_until_due', 'due_local', 'assessment', 'reason', 'last_seen', 'available'}}


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS records (
          account TEXT, scope TEXT, id TEXT, payload TEXT NOT NULL,
          last_seen TEXT NOT NULL, available INTEGER NOT NULL,
          PRIMARY KEY(account, scope, id));
        CREATE TABLE IF NOT EXISTS sources (
          account TEXT, scope TEXT, last_attempt TEXT, last_success TEXT,
          error TEXT, PRIMARY KEY(account, scope));
        CREATE TABLE IF NOT EXISTS changes (
          seq INTEGER PRIMARY KEY, account TEXT, scope TEXT, id TEXT,
          kind TEXT, changed_at TEXT, before_json TEXT, after_json TEXT);
        ''')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def snapshot(self, account, scope, records, at=None):
        if not account or not scope:
            raise AppError('Не указан аккаунт или источник.')
        at = at or utc_now()
        parsed = [canonical(r) for r in records]
        ids = [r['id'] for r in parsed]
        if len(ids) != len(set(ids)):
            raise AppError('Источник вернул повторяющиеся идентификаторы.')
        counts = {'new': 0, 'updated': 0, 'not_seen': 0, 'restored': 0}
        with self.db:
            old = {r['id']: r for r in self.db.execute(
                'SELECT * FROM records WHERE account=? AND scope=?', (account, scope))}
            for record in parsed:
                payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
                prev = old.get(record['id'])
                kind = ('new' if prev is None else 'restored' if not prev['available'] else
                        'updated' if prev['payload'] != payload else None)
                if kind:
                    counts[kind] += 1
                    self.db.execute('INSERT INTO changes(account,scope,id,kind,changed_at,before_json,after_json) VALUES(?,?,?,?,?,?,?)',
                                    (account, scope, record['id'], kind, at, prev['payload'] if prev else None, payload))
                self.db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,1)',
                                (account, scope, record['id'], payload, at))
            for key, prev in old.items():
                if key not in ids and prev['available']:
                    counts['not_seen'] += 1
                    self.db.execute('UPDATE records SET available=0 WHERE account=? AND scope=? AND id=?', (account, scope, key))
                    self.db.execute('INSERT INTO changes(account,scope,id,kind,changed_at,before_json,after_json) VALUES(?,?,?,?,?,?,?)',
                                    (account, scope, key, 'not_seen', at, prev['payload'], None))
            self.db.execute('INSERT INTO sources VALUES(?,?,?,?,NULL) ON CONFLICT(account,scope) DO UPDATE SET last_attempt=excluded.last_attempt,last_success=excluded.last_success,error=NULL',
                            (account, scope, at, at))
        return counts

    def failure(self, account, scope, at=None):
        # No upstream exception body: it might contain private content/credentials.
        with self.db:
            self.db.execute('INSERT INTO sources VALUES(?,?,?,NULL,?) ON CONFLICT(account,scope) DO UPDATE SET last_attempt=excluded.last_attempt,error=excluded.error',
                            (account, scope, at or utc_now(), 'Проверка не завершена; сохранены предыдущие данные.'))

    def tasks(self, account, now=None):
        result = []
        for row in self.db.execute('SELECT * FROM records WHERE account=? ORDER BY scope,id', (account,)):
            record = display_records([json.loads(row['payload'])], now)[0]
            record.update(last_seen=row['last_seen'], available=bool(row['available']), scope=row['scope'])
            result.append(record)
        return result

    def health(self, account):
        return [dict(r) for r in self.db.execute('SELECT scope,last_attempt,last_success,error FROM sources WHERE account=? ORDER BY scope', (account,))]

    def history(self, account, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise AppError('Лимит истории должен быть от 1 до 100.')
        return [dict(r) for r in self.db.execute('SELECT scope,id,kind,changed_at,before_json,after_json FROM changes WHERE account=? ORDER BY seq DESC LIMIT ?', (account, limit))]

    def accounts(self):
        return [r[0] for r in self.db.execute('SELECT DISTINCT account FROM sources ORDER BY account')]
