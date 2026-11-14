#!/usr/bin/env python3
"""Manually enrich up to 300 recent IMAP UIDs per folder (no new Cron).

Python 3.6+. Uses the exact same private IMAP/HMAC credentials and state lock.
Does NOT move incremental mail cursor, delete mail, change read flags or send.
"""
import argparse
import fcntl
import imaplib
import json
import os
import socket
import ssl
import time
from pathlib import Path

import ujn_imap_incremental_collector as collector
import ujn_imap_readonly_collector as base

STATE_FILE = Path("/home/ujn/brain-ujn/state/mime_recover_recent.json")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 30:
        parser.error("--limit must be 1 to 30")
    if not collector.MIME_ENABLED:
        parser.error("Set UJN_IMAP_MIME_ENABLED=1 (and UJN_IMAP_ATTACHMENTS_ENABLED=1 to store files)")
    with collector.LOCK_PATH.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            print(json.dumps({"mode":"mime_recover","status":"ALREADY_RUNNING"}))
            return
        state = {"version":1,"folders":{}}
        if STATE_FILE.is_file():
            with STATE_FILE.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
            if state.get("version") != 1:
                raise RuntimeError("MIME recovery state version invalid")
        socket.setdefaulttimeout(20)
        stats = {"mode":"mime_recover","newly_processed":0,"errors":0,
                 "dry_run":bool(args.dry_run),"sent_email":False,"per_folder":{}}
        with imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT","993")),
                              ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER, base.PASSWORD)
            sent = base.detect_sent_folder(conn)
            for folder in ["INBOX"] + ([sent] if sent and sent != "INBOX" else []):
                status, _ = conn.select('"' + folder.replace('"','') + '"',readonly=True)
                if status != "OK":
                    stats["errors"] += 1
                    continue
                valid = collector.parse_uidvalidity(conn)
                status, rows = conn.uid("SEARCH", None, "ALL")
                if status != "OK" or not rows:
                    stats["errors"] += 1
                    continue
                recent = [int(x) for x in rows[0].split()][-300:]
                key = folder + ":" + valid
                done = set(state["folders"].get(key, []))
                candidates = [uid for uid in reversed(recent) if uid not in done]
                stats["per_folder"][folder] = {"remaining":len(candidates)}
                if args.dry_run:
                    continue
                for uid in candidates[:args.limit]:
                    try:
                        collector.submit_uid(conn, folder, uid)
                        done.add(uid)
                        state["folders"][key] = sorted(done.intersection(recent))
                        save(state)
                        stats["newly_processed"] += 1
                    except Exception as error:
                        stats["errors"] += 1
                        stats["per_folder"][folder]["last_error_type"] = type(error).__name__
                        break
                stats["per_folder"][folder]["remaining"] = len([x for x in recent if x not in done])
        print(json.dumps(stats,ensure_ascii=False))

def save(state):
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    with tmp.open("w",encoding="utf-8") as handle:
        json.dump(state,handle,ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp),str(STATE_FILE))

if __name__ == "__main__":
    main()
