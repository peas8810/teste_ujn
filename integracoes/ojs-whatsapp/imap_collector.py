#!/usr/bin/env python3
"""Coletor IMAP -> Brain UJN. Python 3.11+, somente biblioteca padrão.

Este serviço lê cópias de e-mails editoriais já enviadas pelo OJS.
Não altera o OJS. Nunca registra o corpo das mensagens em logs.
Uma mensagem é marcada como processada somente após resposta 200 do Supabase.
"""
import email
import email.policy
from email.header import decode_header, make_header
from email.utils import getaddresses
import hashlib
import hmac
import imaplib
import json
import os
import re
import sqlite3
import ssl
import sys
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path

JOURNALS={"REMUNOM","JIRRS","NEXUS","RSV","RJNM"}
API="https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-editorial-email-ingest"

class HtmlText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
        self.hide=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"): self.hide+=1
        if tag=="a":
            url=dict(attrs).get("href","")
            if url.startswith("https://"):self.parts.append(url[:250])
    def handle_endtag(self,tag):
        if tag in ("script","style"): self.hide=max(0,self.hide-1)
    def handle_data(self,data):
        if not self.hide:self.parts.append(data)

def required(k):
    value=os.environ.get(k,"").strip()
    if not value:raise RuntimeError("Variável ausente: "+k)
    return value

def decode(s):
    return str(make_header(decode_header(s or "")))

def body_preview(msg):
    candidates=[]
    for part in msg.walk():
        if part.get_content_disposition() in ("attachment","inline") and part.get_filename():
            continue
        kind=part.get_content_type()
        if kind not in ("text/plain","text/html"):continue
        try:
            data=part.get_content()
            if not isinstance(data,str):continue
            if kind=="text/html":
                p=HtmlText();p.feed(data[:20000]);data=" ".join(p.parts)
            candidates.append((0 if kind=="text/plain" else 1,data))
        except Exception:continue
    return re.sub(r"\s+"," ",sorted(candidates,key=lambda x:x[0])[0][1])[:6000] if candidates else ""

def send(payload,secret):
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    stamp=str(int(time.time()))
    signature="sha256="+hmac.new(secret.encode(),stamp.encode()+b"."+raw,hashlib.sha256).hexdigest()
    request=Request(API,raw,headers={
        "Content-Type":"application/json",
        "x-ujn-mail-timestamp":stamp,
        "x-ujn-mail-signature":signature,
    },method="POST")
    try:
        with urlopen(request,timeout=25) as response:
            return response.status,json.loads(response.read(10000))
    except HTTPError as err:
        return err.code,{"error":"HTTP_"+str(err.code)}

def process_mail(msg, journal, secret, dry_run=False):
    subject=decode(msg.get("Subject"))
    # Copies must preserve original To. Forwarding through normal clients may
    # replace To with the monitoring mailbox; that format is not supported.
    recipients=[x.strip().lower() for _,x in getaddresses(msg.get_all("To",[]))]
    senders=[x.strip().lower() for _,x in getaddresses(msg.get_all("From",[]))]
    if len(set(recipients))!=1 or len(set(senders))!=1:
        return 422,{"error":"ambiguous_to_or_from"}
    recipient, sender=recipients[0],senders[0]
    if not re.fullmatch(r"[^@\s<>]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",recipient):
        return 422,{"error":"invalid_recipient"}
    msgid=(msg.get("Message-ID") or "").strip()
    if not msgid:
        return 422,{"error":"missing_message_id"}
    payload={
        "action":"dry_run" if dry_run else "ingest_mail",
        "journal":journal,
        "sender":sender,
        "recipient":recipient,
        "message_id":msgid[:250],
        "subject":subject[:350],
        "body_preview":body_preview(msg),
    }
    return send(payload,secret)

def main():
    journal=required("UJN_JOURNAL").upper()
    if journal not in JOURNALS:raise RuntimeError("Revista inválida")
    host=required("UJN_IMAP_HOST")
    if not re.fullmatch(r"[A-Za-z0-9.-]+",host):raise RuntimeError("Host IMAP inválido")
    username=required("UJN_IMAP_USER")
    password=required("UJN_IMAP_PASSWORD")
    secret=required("UJN_EMAIL_INGEST_HMAC")
    if not re.fullmatch("[a-fA-F0-9]{64}",secret):raise RuntimeError("Chave HMAC inválida")
    folder=os.environ.get("UJN_IMAP_FOLDER","INBOX")
    dry_run=os.environ.get("UJN_DRY_RUN","1")!="0"
    dbpath=Path(os.environ.get("UJN_IMAP_STATE","./ujn-imap-state.sqlite"))
    connection=sqlite3.connect(dbpath)
    connection.execute("create table if not exists processed (message_key text primary key, seen_at text default current_timestamp)")
    context=ssl.create_default_context()
    with imaplib.IMAP4_SSL(host,port=993,ssl_context=context,timeout=30) as client:
        client.login(username,password)
        status,_=client.select(folder,readonly=True)
        if status!="OK":raise RuntimeError("Pasta IMAP indisponível")
        status,data=client.uid("search",None,"ALL")
        if status!="OK":raise RuntimeError("Falha ao localizar mensagens")
        uids=(data[0] or b"").split()[-100:]
        totals={"checked":0,"accepted":0,"skipped":0,"failed":0}
        for uid in uids:
            key=journal+":"+hashlib.sha256((host+":"+folder+":"+uid.decode()).encode()).hexdigest()
            if connection.execute("select 1 from processed where message_key=?",(key,)).fetchone():
                continue
            status,items=client.uid("fetch",uid,"(RFC822)")
            if status!="OK" or not items or not isinstance(items[0],tuple):
                totals["failed"]+=1;continue
            raw=items[0][1]
            if len(raw)>150000:
                totals["skipped"]+=1;continue
            msg=email.message_from_bytes(raw,policy=email.policy.default)
            status,result=process_mail(msg,journal,secret,dry_run)
            totals["checked"]+=1
            if status==200:
                totals["accepted"]+=1
                if not dry_run:
                    connection.execute("insert or ignore into processed(message_key) values (?)",(key,))
                    connection.commit()
            elif status in (403,409,422):
                totals["skipped"]+=1
            else:
                totals["failed"]+=1
        print(json.dumps({"journal":journal,"dry_run":dry_run,**totals}))
    connection.close()

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("Falha de configuração ou conexão IMAP: "+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
