#!/usr/bin/env python3
"""UJN Intelligence - IMAP read-only collector adapter, standard library only.

Install on cPanel after confirming account credentials and IMAP folders.
Never place this file or env variables under public_html.
NO SMTP; NO mail deletion or flag changes; NO attachment downloads.
"""
import os, json, ssl, imaplib, email, hmac, hashlib, time, urllib.request, urllib.error, sys, re
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timezone

HOST = os.environ["UJN_IMAP_HOST"]
USER = os.environ["UJN_IMAP_USER"]
PASSWORD = os.environ["UJN_IMAP_PASSWORD"]
ENDPOINT = os.environ["UJN_EMAIL_DESK_ENDPOINT"]
HMAC_KEY = os.environ["UJN_MAIL_INGEST_KEY"]
FOLDERS = [x.strip() for x in os.getenv("UJN_IMAP_FOLDERS", "INBOX,Sent").split(",") if x.strip()]
MAILBOX = os.environ["UJN_MAILBOX"].strip().lower()
LIMIT = max(5,min(500,int(os.getenv("UJN_IMAP_SCAN_LIMIT", "150"))))

if not ENDPOINT.startswith("https://") or not re.match(r"^[a-f0-9]{64}$", HMAC_KEY):
    raise RuntimeError("Invalid collector endpoint/key")
def text_header(value):
    try: return str(make_header(decode_header(value or "")))[:500]
    except Exception: return str(value or "")[:500]
def text_body(message):
    parts=[p for p in message.walk() if p.get_content_type()=="text/plain" and p.get_content_disposition()!="attachment"]
    if not parts and message.get_content_type()=="text/plain":parts=[message]
    if not parts:return ""
    part=parts[0]
    raw=part.get_payload(decode=True) or b""
    try:return raw.decode(part.get_content_charset() or "utf-8",errors="replace")[:19000]
    except Exception:return raw.decode("utf-8",errors="replace")[:19000]
def addrs(value):
    from email.utils import getaddresses
    return [a.lower() for _,a in getaddresses([value or ""]) if "@" in a]
def iso(value):
    try:return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except:return datetime.now(timezone.utc).isoformat()
def stable_thread(message, sender, recipient):
    refs=(message.get("References") or "").split()
    reply=(message.get("In-Reply-To") or "").strip()
    mid=(message.get("Message-ID") or "").strip()
    if refs:return refs[0][:240]
    if reply:return reply.split()[0][:240]
    if mid:return mid[:240]
    # Last resort: subject + correspondent, no same-subject cross-author sharing
    subj=re.sub(r"^(re|fw|fwd):\s*","",text_header(message.get("Subject")),flags=re.I).lower()
    correspondent=sender if sender!=MAILBOX else recipient
    return hashlib.sha256((subj+"|"+correspondent).encode()).hexdigest()
def post(item):
    raw=json.dumps(item,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    stamp=str(int(time.time()))
    digest=hmac.new(HMAC_KEY.encode("utf-8"),stamp.encode()+b"."+raw,hashlib.sha256).hexdigest()
    req=urllib.request.Request(ENDPOINT,raw,{"Content-Type":"application/json","x-ujn-mail-timestamp":stamp,"x-ujn-mail-signature":"sha256="+digest},method="POST")
    with urllib.request.urlopen(req,timeout=22) as result:
        data=json.loads(result.read().decode("utf-8"))
        if not (data.get("ok") or data.get("duplicate")):raise RuntimeError("collector rejected message")
        return data
def main():
    sent=0;errors=0
    with imaplib.IMAP4_SSL(HOST,port=int(os.getenv("UJN_IMAP_PORT","993")),ssl_context=ssl.create_default_context(),timeout=25) as conn:
        conn.login(USER,PASSWORD)
        for folder in FOLDERS:
            status,_=conn.select('"'+folder.replace('"','')+'"',readonly=True)
            if status!="OK":
                print("IMAP folder not available:",folder,file=sys.stderr);errors+=1;continue
            status,data=conn.uid("SEARCH",None,"ALL")
            if status!="OK" or not data:continue
            for uid in data[0].split()[-LIMIT:]:
                status,items=conn.uid("FETCH",uid,"(BODY.PEEK[])")
                if status!="OK" or not items or not isinstance(items[0],tuple):errors+=1;continue
                msg=email.message_from_bytes(items[0][1])
                sender=parseaddr(msg.get("From",""))[1].lower()
                recipients=addrs(msg.get("To",""))
                if not sender or not recipients:continue
                direction="OUTBOUND" if sender==MAILBOX else "INBOUND"
                correspondent=recipients[0] if direction=="OUTBOUND" else sender
                if direction=="INBOUND" and MAILBOX not in recipients and MAILBOX not in addrs(msg.get("Cc","")):continue
                mid=(msg.get("Message-ID") or "").strip()
                message_key=mid[:240] if mid else "uid:"+folder+":"+uid.decode()
                item={"action":"sync_message","mailbox":MAILBOX,"thread_key":stable_thread(msg,sender,correspondent),"message_key":message_key,
                    "sender":sender,"recipient":correspondent if direction=="OUTBOUND" else MAILBOX,"subject":text_header(msg.get("Subject")),
                    "body_text":text_body(msg),"direction":direction,"occurred_at":iso(msg.get("Date"))}
                try:post(item);sent+=1
                except (urllib.error.HTTPError,urllib.error.URLError,RuntimeError) as exc:
                    errors+=1;print("Sync failed for folder/UID:",folder,uid.decode(),type(exc).__name__,file=sys.stderr)
    print(json.dumps({"processed":sent,"errors":errors,"sent_email":False}))
if __name__=="__main__":main()
