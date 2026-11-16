#!/usr/bin/env python3
"""Repair missing email MIME bodies already stored in Brain UJN.

Python 3.6+. Read-only INBOX, BODY.PEEK[], no outgoing emails, no flag
modifications, no IMAP deletes. Uses existing protected base collector config.
Uses original Message-ID, never subject/email matching.
"""
import fcntl
import imaplib
import json
import os
import socket
import ssl
import sys
import time
from email.parser import BytesParser
from pathlib import Path

import ujn_imap_readonly_collector as base
import ujn_imap_incremental_collector as incremental

ROOT=Path("/home/ujn/brain-ujn/state")
STATE=ROOT/"mime_body_repair_state.json"
LOCK=ROOT/"maildesk_incremental.lock"
LIMIT=max(1,min(15,int(os.getenv("UJN_MIME_REPAIR_BATCH","10"))))
TIME_BUDGET=max(20,min(90,int(os.getenv("UJN_MIME_REPAIR_SECONDS","48"))))

def load_state():
    if not STATE.exists():
        return {"version":1,"skipped":{}}
    with STATE.open("r",encoding="utf-8") as h:
        obj=json.load(h)
    return obj if obj.get("version")==1 else {"version":1,"skipped":{}}

def save_state(data):
    tmp=STATE.with_suffix(".tmp")
    with tmp.open("w",encoding="utf-8") as h:
        json.dump(data,h,ensure_ascii=False)
        h.flush()
        os.fsync(h.fileno())
    os.replace(str(tmp),str(STATE))

def verified_uids(conn,message_id):
    typ,rows=conn.uid("SEARCH",None,"HEADER","Message-ID",message_id)
    if typ!="OK":
        raise RuntimeError("IMAP_SEARCH_UNAVAILABLE")
    result=[]
    for raw_uid in (rows[0] or b"").split()[:12]:
        uid=int(raw_uid)
        status,parts=conn.uid("FETCH",str(uid),"(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if status!="OK":
            continue
        data=next((r[1] for r in parts or [] if isinstance(r,tuple) and len(r)>=2 and isinstance(r[1],bytes)),b"")
        if not data:
            continue
        parsed=BytesParser().parsebytes(data,headersonly=True)
        if str(parsed.get("Message-ID") or "").strip()==message_id:
            result.append(uid)
    return result

def run():
    ROOT.mkdir(parents=True,exist_ok=True)
    begin=time.monotonic()
    with LOCK.open("a+") as locked:
        try:
            fcntl.flock(locked,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (IOError,OSError):
            print(json.dumps({"mime_repair":"ALREADY_RUNNING","sent_email":False}),flush=True)
            return
        state=load_state()
        stats={"mime_repair":"COMPLETE","candidates":0,"reprocessed":0,"missing_in_inbox":0,
               "empty_original":0,"errors":0,"sent_email":False}
        candidates=base.post({"action":"repair_missing_bodies","limit":LIMIT,
                              "skip_keys":list(state["skipped"].keys())[-500:]}).get("candidates") or []
        stats["candidates"]=len(candidates)
        if not candidates:
            print(json.dumps(stats),flush=True)
            return
        socket.setdefaulttimeout(22)
        with imaplib.IMAP4_SSL(base.HOST,port=int(os.getenv("UJN_IMAP_PORT","993")),
                               ssl_context=ssl.create_default_context()) as conn:
            conn.login(base.USER,base.PASSWORD)
            status,_=conn.select('"INBOX"',readonly=True)
            if status!="OK":
                raise RuntimeError("IMAP_INBOX_READONLY_FAILED")
            valid=incremental.parse_uidvalidity(conn)
            for candidate in candidates:
                if time.monotonic()-begin>TIME_BUDGET:
                    break
                key=candidate["message_key"]
                try:
                    uids=verified_uids(conn,key)
                    if len(uids)!=1:
                        reason="MISSING_OR_AMBIGUOUS" if not uids else "AMBIGUOUS"
                        state["skipped"][key]=reason
                        stats["missing_in_inbox"]+=1
                        save_state(state)
                        continue
                    outcome=incremental.submit_uid(conn,"INBOX",uids[0],valid)
                    if outcome=="SKIPPED":
                        stats["empty_original"]+=1
                        state["skipped"][key]="SKIPPED"
                        save_state(state)
                    else:
                        stats["reprocessed"]+=1
                        # If MIME is truly blank, the endpoint continues returning
                        # this candidate; skip it after this single safe attempt.
                        state["skipped"][key]="REPROCESSED"
                        save_state(state)
                except Exception as error:
                    stats["errors"]+=1
                    stats["last_error_type"]=type(error).__name__
                    break
        print(json.dumps(stats,ensure_ascii=False),flush=True)

if __name__=="__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({"mime_repair":"ERROR","error_type":type(error).__name__,"sent_email":False}),flush=True)
        sys.exit(2)
