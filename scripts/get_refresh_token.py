#!/usr/bin/env python3
"""
Gera o refresh_token do Google OAuth para uso no GitHub Actions.
Execute UMA vez na sua máquina local e salve os valores como secrets.

Pré-requisitos:
  1. Acesse https://console.cloud.google.com/
  2. Crie (ou use) um projeto existente
  3. Ative as APIs: "Google Calendar API" e "Gmail API"
  4. Em "Credenciais" → "Criar credenciais" → "ID do cliente OAuth 2.0"
     Tipo: Aplicativo para computador (Desktop app)
  5. Baixe o JSON e cole os valores abaixo (ou passe como argumentos)

Uso:
  pip install google-auth-oauthlib
  python scripts/get_refresh_token.py
"""

import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Cole aqui os valores do JSON baixado do Google Cloud Console
CLIENT_ID = input("Cole o CLIENT_ID do OAuth: ").strip()
CLIENT_SECRET = input("Cole o CLIENT_SECRET do OAuth: ").strip()

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "=" * 60)
print("✅ Autenticação concluída! Adicione os 3 valores abaixo")
print("   como secrets no GitHub (Settings → Secrets → Actions):")
print("=" * 60)
print(f"\nGOOGLE_CLIENT_ID\n  {CLIENT_ID}")
print(f"\nGOOGLE_CLIENT_SECRET\n  {CLIENT_SECRET}")
print(f"\nGOOGLE_REFRESH_TOKEN\n  {creds.refresh_token}")
print("\n" + "=" * 60)
