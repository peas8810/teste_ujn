#!/usr/bin/env python3
"""Brain UJN IMAP incremental sync: read-only, resumable and lock-protected.

Uses the EXISTING private IMAP credentials and HMAC signer from the proven
ujn_imap_readonly_collector.py in this same private cPanel directory.
No SMTP operations or read-flag changes. New mail is processed before
a rolling window of the newest 300 UIDs per folder; checkpoints persist atomically.
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
from email.utils import parseaddr, getaddresses
from pathlib import Path
import ujn_imap_readonly_collector as base

# Optional additive MIME enrichment; default OFF until installed and tested.
MIME_ENABLED = os.getenv("UJN_IMAP_MIME_ENABLED", "0") == "1"
ATTACHMENTS_ENABLED = os.getenv("UJN_IMAP_ATTACHMENTS_ENABLED", "0") == "1"
if MIME_ENABLED:
    import ujn_email_mime_adapter as mime_adapter

ROOT = Path("/home/ujn/brain-ujn/state")
LOCK_PATH = ROOT / "maildesk_incremental.lock"
STATE_PATH = ROOT / "maildesk_incremental_state.json"
BATCH_NEW = max(5, min(100, int(os.getenv("UJN_IMAP_NEW_LIMIT", "30"))))
BATCH_OLD = 0  # Explicit operating policy: no historical backfill
INITIAL_RECENT = 300  # Keep a rolling recent-mail window per folder
MAX_SECONDS = max(20, min(150, int(os.getenv("UJN_IMAP_MAX_SECONDS", "95"))))
LOCK_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


def read_state():
    if not STATE_PATH.exists():
        return {"version": 1, "folders": {}}
    with STATE_PATH.open("r", encoding="utf-8") as file:
        result = json.load(file)
    if not isinstance(result, dict) or result.get("version") != 1:
        raise RuntimeError("Incremental state version mismatch; do not reset automatically")
    return result


def save_state(state):
    tmp = STATE_PATH.with_name(STATE_PATH.name + ".tmp")
    fd = os.open(str(tmp), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp), str(STATE_PATH))


def iso_uid(raw):
    return int(raw.decode("ascii") if isinstance(raw, bytes) else raw)


def parse_uidvalidity(conn):
    status, values = conn.response("UIDVALIDITY")
    if status == "UIDVALIDITY" and values and values[0]:
        return str(iso_uid(values[0]))
    # Do not silently trust stale UIDs without identifying mailbox UIDVALIDITY
    raise RuntimeError("UIDVALIDITY not available")


def reply_routing(message, sender):
    """Parse RFC 5322 Reply-To conservatively; fail closed on ambiguity."""
    fields = message.get_all("Reply-To", [])
    if not fields:
        authors = getaddresses(message.get_all("From", []))
        if len(authors) != 1 or authors[0][1].strip().lower() != sender:
            return {"reply_to_source": "ambiguous_from_header"}
        return {"reply_to_source": "from_header"}
    recipients = getaddresses(fields)
    parsed = [(name, addr.strip().lower()) for name, addr in recipients]
    valid = [(name, address) for name, address in parsed
             if re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[a-zA-Z]{2,}", address or "")]
    if len(fields) > 1 or len(parsed) != 1 or len(valid) != 1:
        return {"reply_to_source": "ambiguous_reply_to_header"}
    name, address = valid[0]
    if address in (base.MAILBOX, "ujn@journals.ojsbr.com"):
        return {"reply_to_source": "unsafe_reply_to_header"}
    return {"reply_to": address,
            "reply_to_name": base.text_header(name)[:160] if name else "",
            "reply_to_source": "mime_reply_to_header"}


def submit_uid(conn, folder, uid, uidvalidity=None):
    status, items = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if status != "OK" or not items:
        raise RuntimeError("IMAP FETCH failed")
    result = next((i[1] for i in items if isinstance(i, tuple) and len(i) >= 2), None)
    if not isinstance(result, bytes):
        raise RuntimeError("IMAP FETCH missing message body")
    msg = email.message_from_bytes(result)
    sender = parseaddr(msg.get("From", ""))[1].lower()
    recipients = base.addrs(msg.get("To", ""))
    if not sender or not recipients:
        return "SKIPPED"
    direction = "OUTBOUND" if sender == base.MAILBOX else "INBOUND"
    correspondent = recipients[0] if direction == "OUTBOUND" else sender
    if direction == "INBOUND" and base.MAILBOX not in recipients and base.MAILBOX not in base.addrs(msg.get("Cc", "")):
        return "SKIPPED"
    mid = (msg.get("Message-ID") or "").strip()
    message_key = mid[:240] if mid else "uid:" + folder + ":" + str(uid)
    item = {
        "action": "sync_message", "mailbox": base.MAILBOX,
        "thread_key": base.stable_thread(msg, sender, correspondent),
        "message_key": message_key,
        "sender": sender,
        "recipient": correspondent if direction == "OUTBOUND" else base.MAILBOX,
        "subject": base.text_header(msg.get("Subject")),
        "body_text": base.text_body(msg), "direction": direction,
        "occurred_at": base.iso(msg.get("Date")),
    }
    if direction == "INBOUND":
        item.update(reply_routing(msg, sender))
        if folder=="INBOX" and uidvalidity and str(uidvalidity).isdigit():
            item.update({"imap_folder":"INBOX","imap_uid":int(uid),"imap_uidvalidity":int(uidvalidity)})
    if MIME_ENABLED:
        extracted = mime_adapter.extract(msg)
        if extracted["body_html"]:
            item["body_html"] = extracted["body_html"]
        if extracted["attachments"]:
            item["attachments"] = extracted["attachments"]
    result = base.post(item)
    if MIME_ENABLED and ATTACHMENTS_ENABLED:
        for file in extracted["upload_files"]:
            try:
                mime_adapter.upload(base, message_key, file)
            except Exception as err:
                status = getattr(err, "code", None)
                # The message was synced successfully; leave attachment
                # remediation to the independent resumable recovery task.
                print("MIME_ATTACHMENT_UPLOAD_FAILED", folder, uid,
                      type(err).__name__, "http_status", status, file=sys.stderr)
    return "DUPLICATE" if result.get("duplicate") else "NEW"


def collect_remote_flags(conn, uids, deadline):
    """Mirror Roundcube \Seen / \Answered to Brain without modifying IMAP flags.

    Scan one fifth of the 300-message rolling window each minute. Read the
    Message-ID header (never assume a UID belongs to a prior database row).
    """
    available = uids[-300:]
    slot = (int(time.time()) // 60) % 5
    selected = available[slot * 60:(slot + 1) * 60]
    report = {"observed": 0, "updated": 0, "errors": 0}
    for start in range(0, len(selected), 20):
        if time.monotonic() >= deadline - 8:
            break
        group = selected[start:start + 20]
        status, rows = conn.uid("FETCH", ",".join(str(uid) for uid in group),
                                "(UID FLAGS BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if status != "OK":
            report["errors"] += 1
            continue
        records = []
        for row in rows or []:
            if not isinstance(row, tuple) or len(row) < 2 or not isinstance(row[1], bytes):
                continue
            description = row[0]
            if not isinstance(description, bytes):
                continue
            match = re.search(rb"\bFLAGS\s+\(([^)]*)\)", description, re.I)
            if not match:
                continue
            parsed = email.message_from_bytes(row[1])
            mid = str(parsed.get("Message-ID") or "").strip()
            if not (mid.startswith("<") and mid.endswith(">") and len(mid) <= 240):
                continue
            flags = set(word.lower() for word in match.group(1).split())
            records.append({"message_key": mid, "seen": b"\\seen" in flags,
                            "answered": b"\\answered" in flags})
        if records:
            report["observed"] += len(records)
            try:
                outcome = base.post({"action": "imap_flags_observe", "flags": records})
                if not outcome.get("ok"):
                    raise RuntimeError("IMAP_OBSERVATION_NOT_RECORDED")
                report["updated"] += int(outcome.get("updated") or 0)
            except Exception as error:
                report["errors"] += 1
                print("IMAP_FLAG_OBSERVATION_FAILED", type(error).__name__, file=sys.stderr)
    return report


def synchronize(conn, state, deadline):
    stats = {"new": 0, "historical": 0, "duplicates": 0, "skipped": 0, "errors": 0}
    healthy = set()
    sent_folder = base.detect_sent_folder(conn)
    folders = ["INBOX"] + ([sent_folder] if sent_folder and sent_folder != "INBOX" else [])
    history_remaining = False  # Archived mail beyond the window is not imported
    remote_flags = {"observed": 0, "updated": 0, "errors": 0}
    for folder in folders:
        if time.monotonic() > deadline - 8:
            stats["errors"] += 1
            break
        status, _ = conn.select('"' + folder.replace('"', "") + '"', readonly=True)
        if status != "OK":
            stats["errors"] += 1
            continue
        valid = parse_uidvalidity(conn)
        status, values = conn.uid("SEARCH", None, "ALL")
        if status != "OK" or not values:
            stats["errors"] += 1
            continue
        all_uids = [iso_uid(x) for x in values[0].split()]
        uids = all_uids[-INITIAL_RECENT:]  # newest 300 INBOX/Sent UIDs only
        cursor = state["folders"].get(folder)
        if cursor is None or cursor.get("uidvalidity") != valid:
            seed = uids[0] - 1 if uids else 0
            cursor = {"uidvalidity": valid, "last_uid": seed,
                      "history_before": seed, "history_done": seed == 0}
            state["folders"][folder] = cursor
            save_state(state)
        # If the stored checkpoint is older than the rolling window, skip the
        # expired historical range. Messages are not deleted from Supabase.
        floor_uid = uids[0] - 1 if uids else cursor["last_uid"]
        if cursor["last_uid"] < floor_uid:
            cursor["last_uid"] = floor_uid
            cursor["history_before"] = floor_uid
            cursor["history_done"] = True
            save_state(state)
        # Forward cursor catches new messages without re-reading old ones.
        forward = [uid for uid in uids if uid > cursor["last_uid"]]
        for uid in forward[:BATCH_NEW]:
            if time.monotonic() >= deadline - 8:
                break
            try:
                outcome = submit_uid(conn, folder, uid, valid)
                cursor["last_uid"] = uid
                save_state(state)
                stats["new"] += outcome == "NEW"
                stats["duplicates"] += outcome == "DUPLICATE"
                stats["skipped"] += outcome == "SKIPPED"
            except Exception as error:
                stats["errors"] += 1
                print("forward error", folder, uid, type(error).__name__, file=sys.stderr)
                break  # retry same UID on next run
        # Read Roundcube flags only from the INBOX, using the same IMAP
        # connection and existing Cron; never add a second polling process.
        if folder == "INBOX" and time.monotonic() < deadline - 10:
            try:
                remote_flags = collect_remote_flags(conn, uids, deadline)
            except Exception as exc:
                remote_flags["errors"] += 1
                print("IMAP_FLAGS_READ_FAILED", type(exc).__name__, file=sys.stderr)
        history_remaining = False  # Rolling window, no older backfill
        # A successful initial selection is not enough; ensure all new UIDs
        # up to the snapshot are consumed before declaring healthy.
        if (not forward or cursor["last_uid"] >= forward[-1]) and stats["errors"] == 0:
            healthy.add(folder)
    # The worker must not be released after an incomplete or errored run.
    is_healthy = bool(sent_folder and "INBOX" in healthy and sent_folder in healthy and stats["errors"] == 0)
    try:
        health = base.post({
            "action": "collector_status", "mailbox": base.MAILBOX,
            "inbox_ok": is_healthy,
            "sent_ok": is_healthy,
            "sent_folder": sent_folder,
            "errors": stats["errors"],
        })
        enabled = bool(health.get("sync_enabled"))
    except Exception as err:
        enabled = False
        stats["errors"] += 1
        print("health report error:", type(err).__name__, file=sys.stderr)
    print(json.dumps({"mode": "incremental", "mime_enabled": MIME_ENABLED,
                      "attachment_capture_enabled": ATTACHMENTS_ENABLED, "new": stats["new"],
                      "historical": stats["historical"],
                      "duplicates": stats["duplicates"],
                      "skipped": stats["skipped"], "errors": stats["errors"],
                      "sync_enabled": enabled, "backfill_remaining": False, "window": INITIAL_RECENT,
                      "sent_folder_detected": bool(sent_folder), "sent_email": False,
                      "webmail_flags": remote_flags}))


def main():
    start = time.monotonic()
    with open(str(LOCK_PATH), "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"mode": "incremental", "status": "ALREADY_RUNNING", "sent_email": False}))
            return
        socket.setdefaulttimeout(20)
        state = read_state()
        with imaplib.IMAP4_SSL(
            base.HOST, port=int(os.getenv("UJN_IMAP_PORT", "993")),
            ssl_context=ssl.create_default_context()
        ) as conn:
            conn.login(base.USER, base.PASSWORD)
            synchronize(conn, state, start + MAX_SECONDS)


if __name__ == "__main__":
    main()
