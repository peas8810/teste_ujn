#!/usr/bin/env python3
"""Brain UJN: restore one attachment from an already-imported INBOX message.

Python 3.6+; requires the existing cPanel IMAP and ingest_config.json.
IMAP SELECT readonly and UID FETCH BODY.PEEK[] only; no SMTP/flags changes.
Checks UIDVALIDITY, exact RFC Message-ID and exact attachment filename before
uploading only that attachment through the existing secure HMAC endpoint.
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

import ujn_imap_readonly_collector as base
import ujn_imap_incremental_collector as inc
import ujn_email_mime_adapter as mime

LOCK = "/home/ujn/brain-ujn/state/maildesk_incremental.lock"

def execute(args):
    result={"attachment_repair":"NOT_STARTED","upload_attempted":False,
            "sent_email":False,"imap_changes":False}
    with open(LOCK,"a+") as file:
        try:
            fcntl.flock(file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (IOError,OSError):
            result["attachment_repair"]="ALREADY_RUNNING"
            print(json.dumps(result),flush=True)
            return
        socket.setdefaulttimeout(30)
        with imaplib.IMAP4_SSL(base.HOST,port=int(os.getenv("UJN_IMAP_PORT","993")),
                               ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER,base.PASSWORD)
            status,_=conn.select('"INBOX"',readonly=True)
            if status!="OK":
                raise RuntimeError("INBOX_UNAVAILABLE")
            actual_validity=int(inc.parse_uidvalidity(conn))
            if actual_validity!=args.uidvalidity:
                raise RuntimeError("UIDVALIDITY_MISMATCH")
            status,rows=conn.uid("FETCH",str(args.uid),"(BODY.PEEK[])")
            if status!="OK":
                raise RuntimeError("UID_FETCH_FAILED")
            raw=next((x[1] for x in rows or [] if isinstance(x,tuple) and len(x)>1
                      and isinstance(x[1],bytes)),None)
            if raw is None:
                raise RuntimeError("UID_NOT_FOUND")
            msg=email.message_from_bytes(raw)
            actual_key=str(msg.get("Message-ID") or "").strip()
            if actual_key!=args.message_id:
                raise RuntimeError("MESSAGE_ID_MISMATCH")
            original=mime.extract(msg)
            chosen=[x for x in original.get("upload_files",[]) if x["filename"]==args.filename]
            if len(chosen)!=1:
                raise RuntimeError("ATTACHMENT_NOT_FOUND_OR_NOT_ALLOWED")
            item=chosen[0]
            result.update({"filename":args.filename,"bytes":len(item["bytes"]),
                           "attachment_repair":"VERIFIED","eligible":True})
            if args.diagnose:
                result["attachment_repair"]="DIAGNOSTIC"
                result["no_changes"]=True
                print(json.dumps(result,ensure_ascii=False),flush=True)
                return
            result["upload_attempted"]=True
            mime.upload(base,args.message_id,item)
            result["attachment_repair"]="STORED"
            print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--uid",type=int,required=True)
    p.add_argument("--uidvalidity",type=int,required=True)
    p.add_argument("--message-id",required=True)
    p.add_argument("--filename",required=True)
    p.add_argument("--diagnose",action="store_true")
    try:
        args=p.parse_args()
        if args.uid<=0 or args.uidvalidity<=0 or len(args.message_id)>240 or not args.message_id.startswith("<") or not args.message_id.endswith(">"):
            raise RuntimeError("INVALID_MESSAGE_REFERENCE")
        execute(args)
    except Exception as exc:
        print(json.dumps({"attachment_repair":"ERROR","error_type":type(exc).__name__,
                          "error_code":str(exc)[:100] if isinstance(exc,RuntimeError) else None,
                          "sent_email":False,"imap_changes":False}),flush=True)
        sys.exit(2)
