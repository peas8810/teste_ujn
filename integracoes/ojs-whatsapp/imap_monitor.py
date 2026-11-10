#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Brain UJN - monitor local sem envio (Python 3.6.8+).
Primeira execucao estabelece cursor; as proximas verificam mensagens novas.
Sem acesso ao Supabase/WhatsApp. IMAP read-only / BODY.PEEK[].
"""
import email
import email.policy
import hashlib
import imaplib
import json
import os
import sqlite3
import ssl
import sys
from pathlib import Path

from direct_inbox_collector import classify_message

BASE = Path('/home/ujn/brain-ujn')
CONF = BASE / 'imap_config.json'
STATE = BASE / 'state'
DB = STATE / 'brain-ujn-imap.sqlite'
REPORT = STATE / 'monitor-status.json'


def output(status, counters, error=None):
    result = {'status': status, 'dry_run': True, 'whatsapp_sent': 0,
              'messages_marked_read': 0, 'mailbox_changes': 0}
    result.update(counters)
    if error:
        result['error_code'] = error
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = REPORT.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as fp:
        json.dump(result, fp, ensure_ascii=False)
    os.replace(str(temporary), str(REPORT))
    print(json.dumps(result, ensure_ascii=False))


def main():
    counters = {'examined': 0, 'author_candidates': 0, 'ignored': 0,
                'new_messages': 0, 'baseline_initialized': False}
    try:
        if CONF.stat().st_mode & 0o077:
            output('ERROR', counters, 'UNSAFE_PERMISSIONS')
            return 1
        with CONF.open(encoding='utf-8') as fp:
            config = json.load(fp)
        host = config.get('host')
        username = config.get('user')
        password = config.get('password')
        if host != 'mail.ujn.ojsbr.com' or username != 'contato@ujn.ojsbr.com' or not password:
            output('ERROR', counters, 'CONFIG_INVALID')
            return 1
        STATE.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(DB), timeout=10)
        db.execute('CREATE TABLE IF NOT EXISTS mailbox_cursor '
                   '(id TEXT PRIMARY KEY, uidvalidity TEXT NOT NULL, last_uid INTEGER NOT NULL)')
        key = hashlib.sha256((host + '|' + username + '|INBOX').encode('utf-8')).hexdigest()
        con = imaplib.IMAP4_SSL(host, 993, ssl_context=ssl.create_default_context())
        try:
            con.login(username, password)
            typ, _ = con.select('INBOX', readonly=True)
            if typ != 'OK':
                output('ERROR', counters, 'INBOX_UNAVAILABLE')
                return 1
            _, val = con.response('UIDVALIDITY')
            validity = (val[0] or b'0').decode('ascii') if val else '0'
            typ, res = con.uid('search', None, 'ALL')
            if typ != 'OK':
                output('ERROR', counters, 'IMAP_SEARCH_FAILED')
                return 1
            uids = [int(v) for v in (res[0] or b'').split()]
            last_available = max(uids) if uids else 0
            current = db.execute('SELECT uidvalidity,last_uid FROM mailbox_cursor WHERE id=?',
                                 (key,)).fetchone()
            if current is None or current[0] != validity:
                db.execute('INSERT OR REPLACE INTO mailbox_cursor(id,uidvalidity,last_uid) '
                           'VALUES (?,?,?)', (key, validity, last_available))
                db.commit()
                counters['baseline_initialized'] = True
                output('BASELINE_OK', counters)
                return 0
            pending = sorted(u for u in uids if u > current[1])
            counters['new_messages'] = len(pending)
            for uid in pending[:40]:
                typ, fetch = con.uid('fetch', str(uid), '(BODY.PEEK[])')
                if typ != 'OK' or not fetch or not isinstance(fetch[0], tuple):
                    output('ERROR', counters, 'IMAP_FETCH_FAILED')
                    return 1
                data = fetch[0][1]
                if data and len(data) <= 250000:
                    message = email.message_from_bytes(data, policy=email.policy.default)
                    record, reason = classify_message(message)
                    counters['examined'] += 1
                    if record:
                        counters['author_candidates'] += 1
                    else:
                        counters['ignored'] += 1
                else:
                    counters['ignored'] += 1
                db.execute('UPDATE mailbox_cursor SET last_uid=? WHERE id=?', (uid, key))
                db.commit()
            output('OK', counters)
            return 0
        finally:
            try:
                con.logout()
            except Exception:
                pass
            db.close()
    except (OSError, ssl.SSLError, imaplib.IMAP4.error, ValueError, TypeError,
            UnicodeError, sqlite3.Error):
        output('ERROR', counters, 'IMAP_OR_CONFIGURATION_ERROR')
        return 1


if __name__ == '__main__':
    sys.exit(main())
