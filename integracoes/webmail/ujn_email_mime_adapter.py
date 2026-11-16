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
import zipfile
import io
import xml.etree.ElementTree as ET
import subprocess
import shutil
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
    try:
        return raw.decode(part.get_content_charset() or "utf-8", errors="replace")[:cap]
    except (LookupError, UnicodeError, TypeError):
        return raw.decode("utf-8", errors="replace")[:cap]

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

def extract_document_text(item):
    """Best-effort OCR-free reading of DOCX, TXT and text-based PDF."""
    filename = item["filename"].lower()
    mime = item["mime_type"]
    raw = item["bytes"]
    if mime == "text/plain" or filename.endswith(".txt"):
        return raw[:36000].decode("utf-8", errors="replace")[:16000]
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" and filename.endswith(".docx"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
                names = z.namelist()
                if "word/document.xml" not in names:
                    return ""
                info = z.getinfo("word/document.xml")
                if info.file_size > 1500000:
                    return ""
                data = z.read("word/document.xml")
                relations = b""
                if "word/_rels/document.xml.rels" in names:
                    rel_info = z.getinfo("word/_rels/document.xml.rels")
                    if rel_info.file_size < 200000:
                        relations = z.read("word/_rels/document.xml.rels")
            root = ET.fromstring(data)
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs = []
            for p in root.iter(ns + "p"):
                line = "".join(t.text or "" for t in p.iter(ns + "t"))
                if line.strip():
                    paragraphs.append(line.strip())
                if sum(len(v) for v in paragraphs) > 16500:
                    break
            if relations:
                rel_root = ET.fromstring(relations)
                for relation in rel_root.iter():
                    address = relation.attrib.get("Target", "")
                    if (relation.attrib.get("TargetMode") == "External"
                            and address.startswith("https://") and len(address) < 350):
                        paragraphs.append(address)
            return "\n".join(paragraphs)[:16000]
        except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError, RuntimeError, OSError):
            return ""
    if mime == "application/pdf" and filename.endswith(".pdf"):
        tool = shutil.which("pdftotext")
        if not tool:
            return ""
        try:
            result = subprocess.run([tool, "-f", "1", "-l", "8", "-layout", "-", "-"],
                                    input=raw, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=12)
            if result.returncode == 0:
                return result.stdout[:36000].decode("utf-8", errors="replace")[:16000]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return ""


def upload(base, message_key, item):
    """HMAC-shared with normal ingest; idempotent by SHA-256 on the backend."""
    payload = {
        "action": "sync_attachment",
        "mailbox": base.MAILBOX,
        "message_key": message_key,
        "filename": item["filename"],
        "mime_type": item["mime_type"],
        "base64": base64.b64encode(item["bytes"]).decode("ascii"),
        "extracted_text": extract_document_text(item)
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
