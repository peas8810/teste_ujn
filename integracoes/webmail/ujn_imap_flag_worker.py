#!/usr/bin/env python3
"""Synchronize Brain UJN \Seen and \Answered flags with the real Roundcube IMAP inbox.

Python 3.6+, stdlib only. Uses existing private IMAP/HMAC settings in
ujn_imap_readonly_collector.py. NEVER sends email or modifies message bodies.
Never deletes, expunges, moves or alters arbitrary server folders.
"""
import email
import fcntl
import imaplib
import json
import os
import re
import socket
import ssl
import sys
import time
from pathlib import Path
import ujn_imap_readonly_collector as base

ROOT = Path("/home/ujn/brain-ujn/state")
LOCK = ROOT / "imap_flags_worker.lock"
MAX_JOBS = max(1, min(15, int(os.getenv("UJN_IMAP_FLAGS_LIMIT", "8"))))
DEADLINE = 75

def uid_validity(conn):
    code, values = conn.response("UIDVALIDITY")
    if code != "UIDVALIDITY" or not values or not values[0]:
        raise RuntimeError("UIDVALIDITY_MISSING")
    return int(values[0])

def message_id_for_uid(conn, uid):
    typ, rows = conn.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
    if typ != "OK":
        raise RuntimeError("UID_HEADER_FETCH_FAILED")
    chunks = [i[1] for i in rows or [] if isinstance(i, tuple) and len(i) >= 2 and isinstance(i[1], bytes)]
    if len(chunks) != 1:
        raise RuntimeError("UID_HEADER_UNAVAILABLE")
    parsed = email.message_from_bytes(chunks[0])
    return str(parsed.get("Message-ID") or "").strip()

def resolve_uid(conn, validity, job):
    key = str(job.get("message_key") or "").strip()
    if not key:
        raise RuntimeError("MESSAGE_KEY_MISSING")
    stored_uid = job.get("imap_uid")
    stored_validity = job.get("imap_uidvalidity")
    if job.get("imap_folder") == "INBOX" and stored_uid and stored_validity:
        if int(stored_validity) == validity and int(stored_uid) > 0:
            uid = int(stored_uid)
            if key.startswith("uid:INBOX:"):
                # UIDVALIDITY prevents reusing a UID from an altered mailbox.
                return uid
            if message_id_for_uid(conn, uid) == key:
                return uid
        # Even with stale UID mapping, a real Message-ID can be located safely.
    if not (key.startswith("<") and key.endswith(">") and len(key) <= 240 and
            re.fullmatch(r"<[^\s<>]{3,238}>", key)):
        raise RuntimeError("NO_SAFE_MESSAGE_ID")
    typ, rows = conn.uid("SEARCH", None, "HEADER", "Message-ID", key)
    if typ != "OK" or not rows or not rows[0]:
        raise RuntimeError("MESSAGE_NOT_IN_INBOX")
    uids = [int(x) for x in rows[0].split()]
    if len(uids) > 12:
        raise RuntimeError("MESSAGE_ID_AMBIGUOUS")
    matches = [uid for uid in uids if message_id_for_uid(conn, uid) == key]
    if len(matches) != 1:
        raise RuntimeError("MESSAGE_ID_NOT_UNIQUE")
    return matches[0]

def run():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    start = time.monotonic()
    with LOCK.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            print(json.dumps({"imap_flags": "ALREADY_RUNNING", "sent_email": False}), flush=True)
            return
        claim = base.post({"action": "imap_flags_claim", "limit": MAX_JOBS})
        jobs = claim.get("jobs") or []
        outcome = {"imap_flags": "COMPLETE", "jobs": len(jobs), "done": 0,
                   "failed": 0, "unreported": 0, "sent_email": False}
        if not jobs:
            print(json.dumps(outcome), flush=True)
            return
        socket.setdefaulttimeout(22)
        conn = imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT", "993")),
                                 ssl_context=ssl.create_default_context())
        try:
            conn.login(base.USER, base.PASSWORD)
            typ, _ = conn.select('"INBOX"', readonly=False)
            if typ != "OK":
                raise RuntimeError("INBOX_NOT_SELECTABLE")
            validity = uid_validity(conn)
            for job in jobs:
                status = "FAILED"
                reason = "UNRESOLVED"
                try:
                    if time.monotonic() - start > DEADLINE:
                        raise RuntimeError("TIME_BUDGET_EXCEEDED")
                    flag = job.get("flag")
                    if flag not in ("SEEN", "ANSWERED"):
                        raise RuntimeError("FLAG_NOT_ALLOWED")
                    uid = resolve_uid(conn, validity, job)
                    imap_flag = r"\Seen" if flag == "SEEN" else r"\Answered"
                    command = "+FLAGS.SILENT" if job.get("desired") is True else "-FLAGS.SILENT"
                    typ, _ = conn.uid("STORE", str(uid), command, "(" + imap_flag + ")")
                    if typ != "OK":
                        raise RuntimeError("UID_STORE_REJECTED")
                    status, reason = "DONE", None
                except Exception as ex:
                    reason = str(ex) if str(ex) in (
                        "TIME_BUDGET_EXCEEDED", "FLAG_NOT_ALLOWED", "INBOX_NOT_SELECTABLE",
                        "UIDVALIDITY_MISSING", "UID_HEADER_FETCH_FAILED", "UID_HEADER_UNAVAILABLE",
                        "MESSAGE_KEY_MISSING", "NO_SAFE_MESSAGE_ID", "MESSAGE_NOT_IN_INBOX",
                        "MESSAGE_ID_AMBIGUOUS", "MESSAGE_ID_NOT_UNIQUE", "UID_STORE_REJECTED"
                    ) else type(ex).__name__[:70]
                try:
                    report = base.post({"action": "imap_flags_report",
                                        "job_id": job["id"], "status": status,
                                        "error_code": reason})
                    if not report.get("ok"):
                        raise RuntimeError("REPORT_NOT_CONFIRMED")
                    outcome["done" if status == "DONE" else "failed"] += 1
                except Exception:
                    outcome["unreported"] += 1
        finally:
            try:
                conn.close()
            except Exception:
                pass
            conn.logout()
        print(json.dumps(outcome), flush=True)

def diagnose():
    """No database jobs claimed, no flags changed, no SMTP."""
    socket.setdefaulttimeout(15)
    conn = imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT", "993")),
                             ssl_context=ssl.create_default_context())
    try:
        conn.login(base.USER, base.PASSWORD)
        typ, _ = conn.select('"INBOX"', readonly=True)
        if typ != "OK":
            raise RuntimeError("INBOX_READONLY_FAILED")
        validity = uid_validity(conn)
        print(json.dumps({"imap_flags": "DIAGNOSTIC", "connection": "VERIFIED",
                          "inbox_readonly": True, "uidvalidity_available": validity > 0,
                          "flags_changed": False, "sent_email": False}), flush=True)
    finally:
        conn.logout()

if __name__ == "__main__":
    try:
        if "--diagnose" in sys.argv[1:]:
            diagnose()
        else:
            run()
    except Exception as exc:
        print(json.dumps({"imap_flags": "ERROR", "error_type": type(exc).__name__,
                          "sent_email": False}), flush=True)
        sys.exit(2)
