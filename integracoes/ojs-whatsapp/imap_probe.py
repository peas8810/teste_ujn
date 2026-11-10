#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostico IMAP somente leitura do Brain UJN. Compativel com Python 3.6.8.
Nao envia WhatsApp, nao le corpos e nao altera mensagens ou flags.
"""
import imaplib
import json
import ssl
import sys
from pathlib import Path

BASE = Path('/home/ujn/brain-ujn')
CONFIG = BASE / 'imap_config.json'
REPORT = BASE / 'state' / 'imap-diagnostico.json'

def report(code, detail):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open('w', encoding='utf-8') as f:
        json.dump({'status': code, 'detail': detail, 'whatsapp_sent': 0,
                   'read_only': True}, f, ensure_ascii=False)
    print('IMAP_DIAGNOSTIC_' + code)

def main():
    try:
        st = CONFIG.stat()
    except FileNotFoundError:
        report('CONFIG_MISSING', 'Crie imap_config.json fora de public_html.')
        return 1
    if st.st_mode & 0o077:
        report('UNSAFE_PERMISSIONS', 'Defina permissao 600 no arquivo imap_config.json.')
        return 1
    try:
        with CONFIG.open(encoding='utf-8') as f:
            cfg = json.load(f)
        host, user, password = cfg.get('host', ''), cfg.get('user', ''), cfg.get('password', '')
        if host != 'mail.ujn.ojsbr.com' or user != 'contato@ujn.ojsbr.com' or not password:
            report('CONFIG_INVALID', 'Verifique host, user e password no arquivo privado.')
            return 1
        client = imaplib.IMAP4_SSL(host, 993, ssl_context=ssl.create_default_context())
        try:
            client.login(user, password)
            typ, data = client.select('INBOX', readonly=True)
            if typ != 'OK':
                report('SELECT_FAILED', 'Nao foi possivel abrir INBOX.')
                return 1
            typ, data = client.uid('search', None, 'ALL')
            if typ != 'OK':
                report('SEARCH_FAILED', 'Nao foi possivel contar mensagens.')
                return 1
            count = len((data[0] or b'').split())
            report('OK', 'Conexao IMAP somente leitura confirmada. Total na caixa: %d.' % count)
            return 0
        finally:
            try:
                client.logout()
            except Exception:
                pass
    except imaplib.IMAP4.error:
        report('AUTH_OR_IMAP_ERROR', 'Falha IMAP ou autenticacao. Verifique senha localmente.')
        return 1
    except (OSError, ssl.SSLError):
        report('NETWORK_OR_TLS_ERROR', 'Rede ou TLS indisponivel; nao desative verificacao.')
        return 1
    except (ValueError, TypeError, UnicodeError):
        report('CONFIG_FORMAT_ERROR', 'JSON invalido.')
        return 1

if __name__ == '__main__':
    sys.exit(main())
