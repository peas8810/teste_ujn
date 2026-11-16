#!/usr/bin/env python3
"""Brain UJN: recover missing bodies across safe IMAP folders (Python 3.6+).

Searches the exact Message-ID in INBOX and readable non-system IMAP folders.
Never changes mail flags, copies, moves, deletes, expunges, or sends mail.
Only fills missing body fields of an already existing Supabase message.
"""
import argparse
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
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

import ujn_imap_readonly_collector as base
import ujn_imap_incremental_collector as incremental

ROOT = Path("/home/ujn/brain-ujn/state")
LOCK = ROOT / "maildesk_incremental.lock"
STATE = ROOT / "mime_multipasta_repair_state.json"
BATCH = max(1, min(12, int(os.getenv("UJN_MIME_MULTIPASTA_BATCH", "8"))))
FOLDER_LIMIT = max(1, min(20, int(os.getenv("UJN_MIME_MULTIPASTA_FOLDERS", "15"))))
TIME_LIMIT = max(20, min(110, int(os.getenv("UJN_MIME_MULTIPASTA_SECONDS", "65"))))
# Spam/Trash/Sent/Drafts are excluded. This is inbound author mail recovery.
FORBIDDEN = re.compile(r"(?:^|[./])(trash|deleted|junk|spam|sent|enviados|enviado|drafts|rascunhos|lixeira|spamassassin)(?:[./]|$)", re.I)


def state_load():
    if not STATE.exists():
        return {"version": 1, "done": {}}
    with STATE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("done"), dict):
        raise RuntimeError("INVALID_REPAIR_CHECKPOINT")
    return data


def state_save(value):
    tmp = STATE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, sort_keys=True)
        file.flush()
        os.fsync(file.fileno())
    os.replace(str(tmp), str(STATE))


def parse_folder(row):
    """Decode LIST response with quoted or atom mailbox names (no command interpolation)."""
    if not isinstance(row, bytes):
        return None
    line = row.decode("utf-8", "replace")
    match = re.match(r'^\(([^)]*)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(.+)$', line)
    if not match:
        return None
    flags, raw_name = match.groups()
    raw_name = raw_name.strip()
    if raw_name.startswith('"') and raw_name.endswith('"'):
        name = re.sub(r'\\(["\\])', r'\1', raw_name[1:-1])
    else:
        name = raw_name
    if not name or name.upper() == "NIL" or any(c in name for c in "\r\n\x00"):
        return None
    if re.search(r'\\(?:NoSelect|NonExistent|Trash|Junk|Sent|Drafts)\b', flags, re.I):
        return None
    if FORBIDDEN.search(name):
        return None
    if len(name) > 240:
        return None
    return name


def available_folders(conn):
    status, rows = conn.list()
    if status != "OK":
        raise RuntimeError("IMAP_LIST_FAILED")
    found = {"INBOX"}
    for row in rows or []:
        name = parse_folder(row)
        if name:
            found.add(name)
    ordered = ["INBOX"] + sorted((x for x in found if x.upper() != "INBOX"),
                                key=lambda x: (not bool(re.search("archiv|archive", x, re.I)), x.lower()))
    # Limit number of folders to control load on the mail server.
    return ordered[:FOLDER_LIMIT]


def exact_uid_matches(conn, message_key):
    status, rows = conn.uid("SEARCH", None, "HEADER", "Message-ID", message_key)
    if status != "OK":
        raise RuntimeError("IMAP_UID_SEARCH_FAILED")
    raw_uids = (rows[0] or b"").split() if rows else []
    if len(raw_uids) > 12:
        raise RuntimeError("TOO_MANY_MESSAGE_ID_MATCHES")
    matches = []
    for raw_uid in raw_uids:
        if not raw_uid.isdigit():
            continue
        uid = int(raw_uid)
        status, parts = conn.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if status != "OK":
            raise RuntimeError("IMAP_HEADER_FETCH_FAILED")
        payload = next((x[1] for x in parts or [] if isinstance(x, tuple) and len(x) >= 2
                        and isinstance(x[1], bytes)), None)
        if not payload:
            continue
        parsed = BytesParser().parsebytes(payload, headersonly=True)
        if str(parsed.get("Message-ID") or "").strip() == message_key:
            matches.append(uid)
    if len(matches) > 1:
        raise RuntimeError("MESSAGE_ID_AMBIGUOUS")
    return matches


def recover_message(conn, folder, uid, expected_key):
    status, rows = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if status != "OK":
        raise RuntimeError("IMAP_BODY_FETCH_FAILED")
    raw = next((x[1] for x in rows or [] if isinstance(x, tuple) and len(x) >= 2
                and isinstance(x[1], bytes)), None)
    if raw is None:
        raise RuntimeError("IMAP_BODY_MISSING")
    message = email.message_from_bytes(raw)
    if str(message.get("Message-ID") or "").strip() != expected_key:
        raise RuntimeError("MESSAGE_ID_MISMATCH")
    sender = parseaddr(message.get("From", ""))[1].lower()
    recipients = base.addrs(message.get("To", ""))
    if not sender or not recipients:
        return "ENVELOPE_UNREADABLE"
    if sender == base.MAILBOX or (base.MAILBOX not in recipients and
                                  base.MAILBOX not in base.addrs(message.get("Cc", ""))):
        return "NOT_INBOUND"
    # MIME enrichment is strictly optional: a charset failure must never discard
    # decoded plain text, while malformed HTML should not break other records.
    plain = base.text_body(message)
    html = ""
    try:
        import ujn_email_mime_adapter as mime_adapter
        html = mime_adapter.extract(message).get("body_html") or ""
    except Exception as err:
        print("HTML_EXTRACTION_WARNING", type(err).__name__, file=sys.stderr)
    if not plain.strip() and not html.strip():
        return "ORIGINAL_EMPTY"
    item = {
        "action": "sync_message",
        "mailbox": base.MAILBOX,
        "thread_key": base.stable_thread(message, sender, sender),
        "message_key": expected_key,
        "sender": sender,
        "recipient": base.MAILBOX,
        "subject": base.text_header(message.get("Subject")),
        "body_text": plain,
        "direction": "INBOUND",
        "occurred_at": base.iso(message.get("Date")),
    }
    item.update(incremental.reply_routing(message, sender))
    if html:
        item["body_html"] = html
    result = base.post(item)
    if result.get("enriched"):
        return "RESTORED"
    if result.get("duplicate"):
        return "ALREADY_PRESENT"
    # A missing-body repair must not create an entirely new message.
    raise RuntimeError("UNEXPECTED_NEW_MESSAGE")


def run(diagnose=False):
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    stats = {"mime_multipasta": "DIAGNOSTIC" if diagnose else "COMPLETE",
             "folders_scanned": 0, "candidates": 0, "restored": 0,
             "already_present": 0, "not_found": 0, "original_empty": 0,
             "skipped": 0, "errors": 0, "deferred": 0,
             "sent_email": False, "imap_changes": False}
    with LOCK.open("a+") as locked:
        try:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            print(json.dumps({"mime_multipasta": "ALREADY_RUNNING",
                              "sent_email": False, "imap_changes": False}), flush=True)
            return
        state = state_load()
        skip = list(state["done"].keys())[-500:]
        candidates = base.post({"action": "repair_missing_bodies", "limit": BATCH,
                                "skip_keys": skip}).get("candidates") or []
        stats["candidates"] = len(candidates)
        if not candidates:
            print(json.dumps(stats), flush=True)
            return
        socket.setdefaulttimeout(22)
        started = time.monotonic()
        with imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT", "993")),
                               ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER, base.PASSWORD)
            folders = available_folders(conn)
            stats["folders_available"] = len(folders)
            stats["folder_names"] = folders[:20]
            if diagnose:
                stats["no_changes"] = True
                print(json.dumps(stats, ensure_ascii=False), flush=True)
                return
            # Search folder by folder to minimize mailbox SELECT calls.
            outstanding = {c["message_key"]: c for c in candidates}
            searched_all = True
            for folder in folders:
                if time.monotonic() - started >= TIME_LIMIT - 12:
                    searched_all = False
                    break
                selected, _ = conn.select('"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"', readonly=True)
                if selected != "OK":
                    stats["errors"] += 1
                    searched_all = False
                    continue
                stats["folders_scanned"] += 1
                for key in list(outstanding):
                    if time.monotonic() - started >= TIME_LIMIT - 10:
                        searched_all = False
                        break
                    try:
                        matches = exact_uid_matches(conn, key)
                        if not matches:
                            continue
                        outcome = recover_message(conn, folder, matches[0], key)
                        if outcome == "RESTORED":
                            stats["restored"] += 1
                        elif outcome == "ALREADY_PRESENT":
                            stats["already_present"] += 1
                        elif outcome == "ORIGINAL_EMPTY":
                            stats["original_empty"] += 1
                        else:
                            stats["skipped"] += 1
                        # Completed candidates are checkpointed. Incomplete scans
                        # stay eligible for a retry, even if their first folder failed.
                        state["done"][key] = outcome
                        state_save(state)
                        del outstanding[key]
                    except Exception as error:
                        stats["errors"] += 1
                        stats["last_error_type"] = type(error).__name__
                        # Keep candidate eligible for retry, never assume absence.
                if not outstanding:
                    break
            if searched_all and stats["errors"] == 0:
                for key in outstanding:
                    state["done"][key] = "NOT_FOUND_IN_ALLOWED_FOLDERS"
                    stats["not_found"] += 1
                if outstanding:
                    state_save(state)
            else:
                stats["deferred"] = len(outstanding)
        # Folder search does not mean ALL records are repaired: log what was found.
        print(json.dumps(stats, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--diagnose", action="store_true")
        args = parser.parse_args()
        run(diagnose=args.diagnose)
    except Exception as error:
        print(json.dumps({"mime_multipasta": "ERROR",
                          "error_type": type(error).__name__,
                          "sent_email": False, "imap_changes": False}), flush=True)
        sys.exit(2)
