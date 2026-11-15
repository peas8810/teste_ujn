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
    parser.add_argument("--reindex", action="store_true", help="Re-read up to 300 recent MIME messages and refresh document text without resetting the regular checkpoint")
    parser.add_argument("--reply-to-reconcile", action="store_true", help="Refresh From/Reply-To metadata only, no attachments or MIME uploads")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 30:
        parser.error("--limit must be 1 to 30")
    if args.reindex and args.reply_to_reconcile:
        parser.error("Choose either --reindex or --reply-to-reconcile")
    if not args.reply_to_reconcile and not collector.MIME_ENABLED:
        parser.error("Set UJN_IMAP_MIME_ENABLED=1 (and UJN_IMAP_ATTACHMENTS_ENABLED=1 to store files)")
    if args.reply_to_reconcile and collector.MIME_ENABLED:
        parser.error("Run --reply-to-reconcile without UJN_IMAP_MIME_ENABLED for fast metadata-only reconciliation")
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
        stats = {"mode":"reply_to_reconcile" if args.reply_to_reconcile else ("mime_reindex" if args.reindex else "mime_recover"),"newly_processed":0,"errors":0,
                 "dry_run":bool(args.dry_run),"sent_email":False,"per_folder":{}}
        with imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT","993")),
                              ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER, base.PASSWORD)
            sent = None if args.reply_to_reconcile else base.detect_sent_folder(conn)
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
                checkpoint_group = "reply_to_reconcile" if args.reply_to_reconcile else ("reindex" if args.reindex else "folders")
                state.setdefault(checkpoint_group, {})
                done = set(state[checkpoint_group].get(key, []))
                candidates = [uid for uid in reversed(recent) if uid not in done]
                stats["per_folder"][folder] = {"remaining":len(candidates)}
                if args.dry_run:
                    continue
                for uid in candidates[:args.limit]:
                    try:
                        collector.submit_uid(conn, folder, uid)
                        done.add(uid)
                        state[checkpoint_group][key] = sorted(done.intersection(recent))
                        save(state)
                        stats["newly_processed"] += 1
                    except Exception as error:
                        stats["errors"] += 1
                        info = {"type": type(error).__name__, "uid": uid}
                        if hasattr(error, "code"):
                            info["http_status"] = int(error.code)
                        stats["per_folder"][folder]["last_error"] = info
                        # Keep failed UID out of checkpoint for safe retry,
                        # but do not block other recent messages in this batch.
                        continue
                stats["per_folder"][folder]["remaining"] = len([x for x in recent if x not in done])
        if args.reply_to_reconcile and not args.dry_run and stats["errors"] == 0 and stats["per_folder"] and all(v.get("remaining") == 0 for v in stats["per_folder"].values()):
            flag = STATE_FILE.with_name("reply_to_reconcile_done.flag")
            with flag.open("w", encoding="utf-8") as handle:
                handle.write("IMAP Reply-To reconciliation finished for the recent 300-message INBOX window.\\n")
            stats["completed"] = True
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
