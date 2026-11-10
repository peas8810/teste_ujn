#!/usr/bin/env python3
"""Brain UJN: coleta IMAP somente leitura da caixa editorial institucional.

Python 3.11+; biblioteca padrão. Não altera, apaga nem marca mensagens como lidas.
Começa da posição atual (sem disparar histórico retroativo).
Não registra assunto, e-mail, corpo ou credenciais em logs.
Por padrão executa somente testes de classificação (UJN_DRY_RUN=1).
"""
import email
import email.policy
from email.header import decode_header, make_header
from email.utils import getaddresses
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
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

URL="https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-editorial-email-ingest"
ALLOWED_FROM={"ujn@journals.ojsbr.com"}
JOURNALS={
 "REMUNOM":("remunom.ojsbr.com",),
 "RJNM":("jrnm.ojsbr.com","jrnm.ojsbr.com"),
 "RSV":("rsv.ojsbr.com",),
 "JIRRS":("jirrs.org.uk",),
 "NEXUS":("nexussr.org.uk",),
}
ADMIN_TO={
 "contato@ujn.ojsbr.com","contato_01@ujn.ojsbr.com",
 "contact@jirrs.org.uk","notificacoes@ujn.ojsbr.com",
 "invite@jirrs.org.uk","ah-hoc@ujn.ojsbr.com",
}
EDITOR_ONLY=re.compile(
 r"needs an editor to be assigned|editor assignment|precisa que um editor seja designado|"
 r"new submission requires an editor|nova submissão precisa de um editor",re.I
)
JOURNAL_LABEL=re.compile(r"\b(REMUNOM|RJNM|JIRRS|RSV|NEXUS)\b",re.I)

def require(name):
 value=os.environ.get(name,"").strip()
 if not value:raise ValueError("Missing required configuration: "+name)
 return value

class TextFromHtml(HTMLParser):
 def __init__(self):
  super().__init__();self.tokens=[];self.hidden=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style"):self.hidden+=1
  if tag=="a":
   href=dict(attrs).get("href","")
   if href.startswith("https://"):self.tokens.append(href[:250])
 def handle_endtag(self,tag):
  if tag in ("script","style"):self.hidden=max(0,self.hidden-1)
 def handle_data(self,data):
  if not self.hidden:self.tokens.append(data)

def decode(value):
 try:return str(make_header(decode_header(value or "")))
 except Exception:return str(value or "")

def preview(message):
 texts=[]
 for p in message.walk():
  if p.get_filename() or p.get_content_disposition()=="attachment":continue
  fmt=p.get_content_type()
  if fmt not in ("text/html","text/plain"):continue
  try:
   part=p.get_content()
   if not isinstance(part,str):continue
   if fmt=="text/html":
    html=TextFromHtml();html.feed(part[:18000]);part=" ".join(html.tokens)
   texts.append((fmt!="text/plain",part))
  except Exception:continue
 if not texts:return ""
 text=sorted(texts,key=lambda x:x[0])[0][1]
 return re.sub(r"\s+"," ",text).strip()[:5500]

def classify_message(message):
 from_addresses=[a.lower().strip() for _,a in getaddresses(message.get_all("From",[]))]
 tos=[a.lower().strip() for _,a in getaddresses(message.get_all("To",[]))]
 if len(from_addresses)!=1 or from_addresses[0] not in ALLOWED_FROM:return None,"untrusted_sender"
 # Fail closed for editor/system notifications, non-author addressed messages,
 # multiple recipients and notifications where a BCC obscures original To.
 if len(tos)!=1 or tos[0] in ADMIN_TO:return None,"not_author_recipient"
 if not re.fullmatch(r"[^@\s<>]+@[a-z0-9.-]+\.[a-z]{2,}",tos[0]):return None,"bad_recipient"
 subj=decode(message.get("Subject"))
 if EDITOR_ONLY.search(subj):return None,"editor_only"
 mid=str(message.get("Message-ID") or "").strip()
 if not mid:return None,"no_message_id"
 body=preview(message)
 labels={m.upper() for m in JOURNAL_LABEL.findall(subj)}
 # Identify journal in subject or publication-specific URL, never from
 # sender alone because all journals may share the same address.
 for journal,hosts in JOURNALS.items():
  if any(re.search(r"https://"+re.escape(host)+r"(?=/|$)",body,re.I) for host in hosts):
   labels.add(journal)
 if len(labels)!=1:return None,"unknown_or_ambiguous_journal"
 return {
  "journal":next(iter(labels)),
  "sender":from_addresses[0],"recipient":tos[0],
  "subject":subj[:350],"message_id":mid[:250],
  "body_preview":body,
 },"ok"

def call_service(data,secret,dry_run):
 payload={**data,"action":"dry_run" if dry_run else "ingest_mail"}
 raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode("utf-8")
 stamp=str(int(time.time()))
 signature=hmac.new(secret.encode(),stamp.encode()+b"."+raw,hashlib.sha256).hexdigest()
 req=Request(URL,data=raw,headers={
  "content-type":"application/json",
  "x-ujn-mail-timestamp":stamp,
  "x-ujn-mail-signature":"sha256="+signature,
 },method="POST")
 try:
  with urlopen(req,timeout=25) as res:
   return res.status,json.loads(res.read(4000))
 except HTTPError as exc:
  return exc.code,{"error":"HTTP_"+str(exc.code)}

def run():
 host=require("UJN_IMAP_HOST")
 if not re.fullmatch(r"[a-z0-9.-]+",host,re.I):raise ValueError("Invalid IMAP hostname")
 user=require("UJN_IMAP_USER")
 password=require("UJN_IMAP_PASSWORD")
 key=require("UJN_EMAIL_INGEST_HMAC")
 if not re.fullmatch(r"[0-9a-f]{64}",key,re.I):raise ValueError("Invalid signing key")
 folder=os.environ.get("UJN_IMAP_FOLDER","INBOX").strip()
 dry_run=os.environ.get("UJN_DRY_RUN","1")!="0"
 statefile=Path(os.environ.get("UJN_IMAP_STATE","./brain-ujn-imap.sqlite"))
 statefile.parent.mkdir(parents=True,exist_ok=True)
 database=sqlite3.connect(str(statefile))
 database.execute("CREATE TABLE IF NOT EXISTS mailbox_cursor (id TEXT PRIMARY KEY, uidvalidity TEXT NOT NULL, last_uid INTEGER NOT NULL)")
 database.execute("CREATE TABLE IF NOT EXISTS processed (id TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
 summary={"dry_run":dry_run,"checked":0,"eligible":0,"review":0,"skipped":0,"failed":0,"baseline":False}
 boxid=hashlib.sha256((host+"|"+user+"|"+folder).encode()).hexdigest()
 with imaplib.IMAP4_SSL(host,port=993,ssl_context=ssl.create_default_context(),timeout=30) as client:
  client.login(user,password)
  status,response=client.select(folder,readonly=True)
  if status!="OK":raise RuntimeError("IMAP folder unavailable")
  uidval=client.response("UIDVALIDITY")[1]
  uidvalidity=(uidval[0].decode() if uidval and uidval[0] else "0")
  status,result=client.uid("search",None,"ALL")
  if status!="OK":raise RuntimeError("IMAP search unavailable")
  uids=[int(x) for x in (result[0] or b"").split()]
  previous=database.execute("SELECT uidvalidity,last_uid FROM mailbox_cursor WHERE id=?",(boxid,)).fetchone()
  if previous is None or previous[0]!=uidvalidity:
   # The first connection captures a baseline only. Do not notify authors
   # about months of previous editorial correspondence.
   last=max(uids,default=0)
   if not dry_run:
    database.execute("INSERT OR REPLACE INTO mailbox_cursor(id,uidvalidity,last_uid) VALUES (?,?,?)",(boxid,uidvalidity,last))
    database.commit()
   summary["baseline"]=True
   print(json.dumps(summary))
   return
  last=previous[1]
  for uid in sorted(x for x in uids if x>last)[:40]:
   # Never process out of order; retry transient errors on next run.
   status,parts=client.uid("fetch",str(uid),"(BODY.PEEK[])")
   if status!="OK" or not parts or not isinstance(parts[0],tuple):
    summary["failed"]+=1;break
   raw=parts[0][1]
   if len(raw)>250000:
    summary["skipped"]+=1
   else:
    msg=email.message_from_bytes(raw,policy=email.policy.default)
    data,reason=classify_message(msg)
    summary["checked"]+=1
    if data is None:
     summary["skipped"]+=1
    else:
     status,answer=call_service(data,key,dry_run)
     if status==200:
      summary["eligible"]+=1
      if answer.get("state") in ("NEEDS_REVIEW","UNMATCHED"):summary["review"]+=1
     elif status in (403,409,422):
      summary["skipped"]+=1
     else:
      summary["failed"]+=1;break
   if not dry_run:
    database.execute("UPDATE mailbox_cursor SET last_uid=? WHERE id=?",(uid,boxid))
    database.commit()
 print(json.dumps(summary))
 database.close()

if __name__=="__main__":
 try:run()
 except Exception as err:
  print("IMAP collector failed: "+type(err).__name__,file=sys.stderr)
  sys.exit(1)
