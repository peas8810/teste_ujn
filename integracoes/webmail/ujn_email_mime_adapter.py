#!/usr/bin/env python3
"""MIME enrichment for Brain UJN, Python 3.6+ standard library only.

Extracts safe metadata/HTML; uploads approved attachments to the EXISTING
Supabase private storage ingest function using the EXISTING HMAC key.
Import does not execute any network operation.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.request
from email.header import decode_header, make_header

ENDPOINT = "https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-email-attachment-ingest"
MAX_HTML_CHARS = 85000
MAX_ATTACHMENTS = 15
MAX_ATTACHMENT_BYTES = 7 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_BYTES = 14 * 1024 * 1024
ALLOWED_MIME = frozenset((
    "application/pdf", "image/jpeg", "image/png", "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip", "text/plain"
))

def decoded_name(value):
    if not value:
        return ""
    try:
        value = str(make_header(decode_header(value)))
    except (ValueError, TypeError, UnicodeError):
        value = str(value)
    # Reject paths and control chars; allow Unicode names without path traversal.
    value = re.sub(r"[/\\\x00-\x1f\x7f]", "_", value).strip(" .")
    return value[:180]

def decode_text(part, cap):
    raw = part.get_payload(decode=True) or b""
    if len(raw) > 256000:
        raw = raw[:256000]
    return raw.decode(part.get_content_charset() or "utf-8", errors="replace")[:cap]

def extract(message):
    """No external access; contents are sanitized again by Supabase."""
    html = None
    metadata = []
    uploads = []
    total_bytes = 0
    for part in message.walk():
        if part.is_multipart():
            continue
        mime = part.get_content_type().lower()
        disposition = (part.get_content_disposition() or "").lower()
        filename = decoded_name(part.get_filename())
        inline_image = mime.startswith("image/") and bool(part.get("Content-ID"))
        is_attachment = disposition == "attachment" or bool(filename) or inline_image
        if not is_attachment and mime == "text/html" and html is None:
            html = decode_text(part, MAX_HTML_CHARS)
            continue
        if not is_attachment:
            continue
        if len(metadata) >= MAX_ATTACHMENTS:
            break
        raw = part.get_payload(decode=True) or b""
        name = filename or ("inline-image-" + str(len(metadata) + 1) + ".bin")
        size = len(raw)
        metadata.append({"filename": name, "mime_type": mime, "size_bytes": size})
        if mime not in ALLOWED_MIME or not size or size > MAX_ATTACHMENT_BYTES:
            continue
        if total_bytes + size > MAX_TOTAL_ATTACHMENT_BYTES:
            continue
        if len(name) > 180:
            continue
        uploads.append({"filename": name, "mime_type": mime, "bytes": raw})
        total_bytes += size
    return {"body_html": html, "attachments": metadata, "upload_files": uploads}

def upload(base, message_key, item):
    """HMAC-shared with normal ingest; idempotent by SHA-256 on the backend."""
    payload = {
        "action": "sync_attachment",
        "mailbox": base.MAILBOX,
        "message_key": message_key,
        "filename": item["filename"],
        "mime_type": item["mime_type"],
        "base64": base64.b64encode(item["bytes"]).decode("ascii")
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stamp = str(int(time.time()))
    signature = hmac.new(base.HMAC_KEY.encode("ascii"),
                         stamp.encode("ascii") + b"." + raw, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        ENDPOINT, raw,
        {"Content-Type": "application/json",
         "x-ujn-mail-timestamp": stamp,
         "x-ujn-mail-signature": "sha256=" + signature},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        result = json.loads(response.read().decode("utf-8"))
        if not result.get("ok") or not result.get("stored"):
            raise RuntimeError("attachment_not_confirmed")
    return True
