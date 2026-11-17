#!/usr/bin/env python3
"""Brain UJN: bounded recovery of missing attachments using existing IMAP infrastructure.
Python 3.6+; no SMTP, flag changes or destructive operations.
Run manually with --diagnose first, then --limit 8. No new permanent Cron.
"""
import argparse
import email
import fcntl
import imaplib
import json
import os
import socket
import ssl
import sys
import time

import ujn_imap_readonly_collector as base
import ujn_imap_incremental_collector as inc
import ujn_email_mime_adapter as mime
import ujn_imap_multipasta_repair as folders

LOCK = "/home/ujn/brain-ujn/state/maildesk_incremental.lock"

def run(diagnose=False, limit=8):
    result = {"attachment_batch": "DIAGNOSTIC" if diagnose else "COMPLETE",
              "candidates": 0, "stored": 0, "errors": 0, "not_found": 0,
              "unsupported": 0, "deferred": 0, "sent_email": False, "imap_changes": False}
    with open(LOCK, "a+") as locked:
        try:
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            result["attachment_batch"] = "ALREADY_RUNNING"
            print(json.dumps(result), flush=True)
            return
        pending = base.post({"action": "repair_missing_attachments", "limit": limit}).get("candidates") or []
        if not isinstance(pending, list):
            raise RuntimeError("BAD_REPAIR_CANDIDATES")
        result["candidates"] = len(pending)
        if not pending:
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return
        socket.setdefaulttimeout(25)
        started = time.monotonic()
        with imaplib.IMAP4_SSL(base.HOST, port=int(os.getenv("UJN_IMAP_PORT", "993")),
                               ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER, base.PASSWORD)
            available = folders.available_folders(conn)
            sent_folder = base.detect_sent_folder(conn)
            if sent_folder and sent_folder not in available:
                available.append(sent_folder)
            result["folders_available"] = len(available)
            if diagnose:
                result["no_changes"] = True
                result["filenames"] = [str(x.get("filename", ""))[:120] for x in pending]
                print(json.dumps(result, ensure_ascii=False), flush=True)
                return
            grouped = {}
            for att in pending:
                key = att.get("message_key")
                if isinstance(key, str) and key.startswith("<") and key.endswith(">"):
                    grouped.setdefault(key, []).append(att)
                else:
                    result["errors"] += 1
            for key, attachments in grouped.items():
                found = False
                is_outbound = all(x.get("direction") == "OUTBOUND" for x in attachments)
                for folder in available:
                    if is_outbound and folder != sent_folder:
                        continue
                    if not is_outbound and folder == sent_folder:
                        continue
                    if time.monotonic() - started > 80:
                        result["deferred"] += len(attachments)
                        break
                    try:
                        status, _ = conn.select('"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"',
                                                readonly=True)
                        if status != "OK":
                            continue
                        validity = str(inc.parse_uidvalidity(conn))
                        known = attachments[0]
                        if (known.get("imap_folder") == folder and
                                str(known.get("imap_uidvalidity")) == validity and
                                isinstance(known.get("imap_uid"), int) and known["imap_uid"] > 0):
                            matches = [known["imap_uid"]]
                        else:
                            matches = folders.exact_uid_matches(conn, key)
                        for uid in matches:
                            status, rows = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
                            if status != "OK":
                                raise RuntimeError("IMAP_FETCH_FAILED")
                            data = next((x[1] for x in rows or []
                                         if isinstance(x, tuple) and len(x) > 1
                                         and isinstance(x[1], bytes)), None)
                            if data is None:
                                continue
                            msg = email.message_from_bytes(data)
                            if str(msg.get("Message-ID") or "").strip() != key:
                                continue
                            from email.utils import parseaddr
                            sender = parseaddr(msg.get("From", ""))[1].lower()
                            if is_outbound != (sender == base.MAILBOX):
                                continue
                            if not is_outbound and base.MAILBOX not in base.addrs(msg.get("To", "")) and base.MAILBOX not in base.addrs(msg.get("Cc", "")):
                                continue
                            uploads = mime.extract(msg).get("upload_files", [])
                            for att in attachments:
                                candidates = [x for x in uploads if x["filename"] == att.get("filename")]
                                if len(candidates) != 1:
                                    result["unsupported"] += 1
                                    continue
                                if att.get("size_bytes") is not None and int(att["size_bytes"]) != len(candidates[0]["bytes"]):
                                    result["errors"] += 1
                                    continue
                                try:
                                    mime.upload(base, key, candidates[0])
                                    result["stored"] += 1
                                except Exception as exc:
                                    result["errors"] += 1
                                    result["last_upload_error_type"] = type(exc).__name__
                            found = True
                            break
                        if found:
                            break
                    except Exception as exc:
                        result["errors"] += 1
                        result["last_imap_error_type"] = type(exc).__name__
                if not found and time.monotonic() - started <= 80:
                    result["not_found"] += len(attachments)
        print(json.dumps(result, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 12:
        parser.error("--limit must be between 1 and 12")
    try:
        run(args.diagnose, args.limit)
    except Exception as exc:
        print(json.dumps({"attachment_batch": "ERROR", "error_type": type(exc).__name__,
                          "error_code": str(exc)[:80] if isinstance(exc, RuntimeError) else None,
                          "sent_email": False, "imap_changes": False}), flush=True)
        sys.exit(2)
