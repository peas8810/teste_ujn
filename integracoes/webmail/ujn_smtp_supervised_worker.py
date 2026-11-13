#!/usr/bin/env python3
"""Brain UJN outbound SMTP worker. PRIVATE cPanel directory only.

Default mode: SMTP authentication/connection test; sends NO message.
--send-one: fetch ONE expressly operator-approved QUEUED job, deliver once, report status.
Never run --send-one on Cron until verified and enabled in Supabase.
"""
import sys, os, json, re, ssl, socket, smtplib, urllib.request, urllib.error, time, hmac, hashlib, uuid
from email.message import EmailMessage
from email.utils import formatdate

ROOT="/home/ujn/brain-ujn"
MAILBOX="contato@ujn.ojsbr.com"
SMTP_HOST="mail.ujn.ojsbr.com"
SMTP_PORT=465
ENDPOINT="https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-email-desk-v1"

def read_json(path):
    with open(path,"r",encoding="utf-8") as fh:
        v=json.load(fh)
    if not isinstance(v,dict):
        raise ValueError("JSON configuration must be an object")
    return v

def config_path(env,fallback):
    return os.environ.get(env,fallback)

def read_key():
    v=read_json(config_path("UJN_INGEST_CONFIG_PATH",ROOT+"/ingest_config.json")).get("hmac_key")
    if not isinstance(v,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",v):
        raise RuntimeError("Missing/invalid private HMAC key")
    return v.lower()

def nested(d,path):
    for segment in path.split("."):
        if not isinstance(d,dict): return None
        d=d.get(segment)
    return d

def read_password():
    d=read_json(config_path("UJN_IMAP_CONFIG_PATH",ROOT+"/imap_config.json"))
    selected=os.environ.get("UJN_IMAP_PASSWORD_FIELD","").strip()
    paths=[selected] if selected else ["password","senha","imap_password","mail_password","imap.password","imap.senha","email.password","account.password","credentials.password"]
    found=[nested(d,path) for path in paths if isinstance(nested(d,path),str) and nested(d,path)]
    if len(found)!=1:raise RuntimeError("Could not locate exactly one private password field")
    return found[0]

def signed_request(body,key):
    raw=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    ts=str(int(time.time()))
    sig=hmac.new(key.encode("utf-8"),ts.encode("ascii")+b"."+raw,hashlib.sha256).hexdigest()
    request=urllib.request.Request(ENDPOINT,raw,{"Content-Type":"application/json","x-ujn-mail-timestamp":ts,"x-ujn-mail-signature":"sha256="+sig},method="POST")
    with urllib.request.urlopen(request,timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

def open_smtp(password):
    socket.setdefaulttimeout(25)
    smtp=smtplib.SMTP_SSL(SMTP_HOST,SMTP_PORT,context=ssl.create_default_context(),timeout=25)
    try:
        smtp.login(MAILBOX,password)
        return smtp
    except:
        smtp.close()
        raise

def safe_header(value):
    if not isinstance(value,str) or "\r" in value or "\n" in value:
        raise ValueError("Invalid mail header")
    return value

def send_one(password,key):
    # A job is atomically claimed only after SMTP has been explicitly enabled in Supabase.
    # No automatic retry of a claimed job: prevents accidental duplicate delivery.
    response=signed_request({"action":"worker_claim"},key)
    job=response.get("item")
    if not response.get("ready") or not job:
        print(json.dumps({"ready":bool(response.get("ready")),"dispatched":0}))
        return
    reqid=job["id"]
    status="UNKNOWN"
    reason="UNKNOWN"
    message_id=None
    try:
        recipient=safe_header(job["recipient"])
        if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[A-Za-z]{2,}",recipient) or recipient.lower()==MAILBOX:
            raise ValueError("Recipient not allowed")
        subject=safe_header(job["subject"])
        msg=EmailMessage()
        msg["From"]=MAILBOX
        msg["To"]=recipient
        msg["Subject"]=subject
        msg["Date"]=formatdate(localtime=False)
        message_id="<"+uuid.uuid4().hex+"@ujn.ojsbr.com>"
        msg["Message-ID"]=message_id
        msg["X-UJN-Desk-Request-ID"]=reqid
        msg.set_content(job["body_text"],subtype="plain",charset="utf-8")
        with open_smtp(password) as smtp:
            refused=smtp.send_message(msg,from_addr=MAILBOX,to_addrs=[recipient])
        status="SENT" if not refused else "UNKNOWN"
        reason="" if not refused else "SMTP_RECIPIENT_REFUSED"
    except (smtplib.SMTPAuthenticationError,ValueError,KeyError):
        status="FAILED"
        reason="AUTH_OR_DATA_ERROR"
    except Exception:
        # A network failure after DATA may mean SMTP accepted the email.
        # Do NOT retry automatically. Operator must reconcile with the Sent folder/log.
        status="UNKNOWN"
        reason="SMTP_DELIVERY_UNCERTAIN"
    try:
        answer=signed_request({"action":"worker_report","request_id":reqid,"status":status,"message_id":message_id if status=="SENT" else None,"error_code":reason or None},key)
        if not answer.get("ok"):raise RuntimeError("Status not recorded")
    except Exception:
        print(json.dumps({"status":"REPORT_FAILED","manual_reconciliation_required":True,"request_id":reqid}))
        raise SystemExit(2)
    print(json.dumps({"request_id":reqid,"status":status,"dispatched":1 if status=="SENT" else 0}))

def main():
    password=read_password()
    if len(sys.argv)==1 or sys.argv[1]=="--test-auth":
        with open_smtp(password) as smtp:
            print(json.dumps({"smtp_authenticated":True,"sent_email":False,"host":SMTP_HOST,"port":SMTP_PORT}))
        return
    if sys.argv[1]=="--send-one":
        key=read_key()
        send_one(password,key)
        return
    raise SystemExit("Usage: python3 ujn_smtp_supervised_worker.py [--test-auth | --send-one]")

if __name__=="__main__":
    main()
