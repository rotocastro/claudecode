#!/usr/bin/env python3
"""
Briefing diário do Rodolfo.
Busca clima, agenda e gera rascunho HTML no Gmail.
"""

import os
import json
import base64
import requests
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict

import pytz
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─── Config ────────────────────────────────────────────────────────────────────

TZ = pytz.timezone("America/Sao_Paulo")
RECIPIENT = "rodolfo.tocastro@gmail.com"
CITY = "Campinas"
CITY_WEATHER = "Campinas,BR"

CALENDAR_IDS = [
    "rodolfo.tocastro@gmail.com",
    "pt-br.brazilian#holiday@group.v.calendar.google.com",
    "dg93sv9kfu3h6spuqgdo887932qo44eh@import.calendar.google.com",
    "family13773359058415049452@group.calendar.google.com",
]

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

WEEKDAY_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MONTH_PT = [
    "", "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]

# ─── Auth ──────────────────────────────────────────────────────────────────────

def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


# ─── Weather ───────────────────────────────────────────────────────────────────

WEATHER_ICONS = {
    "thundery": "⛈️",
    "blizzard": "🌨️",
    "heavy rain": "🌧️",
    "rain": "🌦️",
    "drizzle": "🌦️",
    "shower": "🌦️",
    "overcast": "☁️",
    "cloudy": "⛅",
    "partly": "⛅",
    "mist": "🌫️",
    "fog": "🌫️",
    "clear": "☀️",
    "sunny": "☀️",
}

DESC_PT = {
    "Sunny": "Ensolarado",
    "Clear": "Céu limpo",
    "Partly cloudy": "Parcialmente nublado",
    "Cloudy": "Nublado",
    "Overcast": "Nublado/fechado",
    "Mist": "Névoa",
    "Patchy rain possible": "Chuva isolada possível",
    "Patchy snow possible": "Neve isolada possível",
    "Blowing snow": "Neve com vento",
    "Blizzard": "Nevasca",
    "Fog": "Nevoeiro",
    "Freezing fog": "Nevoeiro congelante",
    "Patchy light drizzle": "Garoa fraca isolada",
    "Light drizzle": "Garoa fraca",
    "Freezing drizzle": "Garoa congelante",
    "Heavy freezing drizzle": "Garoa congelante intensa",
    "Patchy light rain": "Chuva fraca isolada",
    "Light rain": "Chuva fraca",
    "Moderate rain at times": "Chuva moderada a intervalos",
    "Moderate rain": "Chuva moderada",
    "Heavy rain at times": "Chuva forte a intervalos",
    "Heavy rain": "Chuva forte",
    "Light freezing rain": "Chuva congelante fraca",
    "Moderate or heavy freezing rain": "Chuva congelante moderada/forte",
    "Light sleet": "Granizo fraco",
    "Moderate or heavy sleet": "Granizo moderado/forte",
    "Patchy light snow": "Neve fraca isolada",
    "Light snow": "Neve fraca",
    "Patchy moderate snow": "Neve moderada isolada",
    "Moderate snow": "Neve moderada",
    "Patchy heavy snow": "Neve forte isolada",
    "Heavy snow": "Neve forte",
    "Ice pellets": "Pelotas de gelo",
    "Light rain shower": "Pancada de chuva fraca",
    "Moderate or heavy rain shower": "Pancada de chuva moderada/forte",
    "Torrential rain shower": "Pancada torrencial",
    "Light sleet showers": "Pancadas de granizo fraco",
    "Moderate or heavy sleet showers": "Pancadas de granizo",
    "Light snow showers": "Pancadas de neve fraca",
    "Moderate or heavy snow showers": "Pancadas de neve",
    "Light showers of ice pellets": "Pelotas de gelo fracas",
    "Moderate or heavy showers of ice pellets": "Pelotas de gelo moderadas",
    "Patchy light rain with thunder": "Chuva fraca isolada com trovoadas",
    "Moderate or heavy rain with thunder": "Chuva com trovoadas",
    "Patchy light snow with thunder": "Neve fraca com trovoadas",
    "Moderate or heavy snow with thunder": "Neve com trovoadas",
    "Thunder outbreaks possible": "Trovoadas possíveis",
}


def weather_icon(desc: str) -> str:
    dl = desc.lower()
    for key, icon in WEATHER_ICONS.items():
        if key in dl:
            return icon
    return "🌤️"


def translate_desc(desc: str) -> str:
    return DESC_PT.get(desc, desc)


def get_weather():
    try:
        url = f"https://wttr.in/{CITY_WEATHER}?format=j1"
        r = requests.get(url, timeout=12, headers={"User-Agent": "curl/7.68.0"})
        data = r.json()

        def parse_day(day):
            # Use midday forecast (index 4 = ~14h)
            hourly = day["hourly"]
            mid = hourly[min(4, len(hourly) - 1)]
            desc = mid["weatherDesc"][0]["value"]
            return {
                "desc": translate_desc(desc),
                "desc_en": desc,
                "min": day["mintempC"],
                "max": day["maxtempC"],
                "rain": mid.get("chanceofrain", "?"),
            }

        return {
            "today": parse_day(data["weather"][0]),
            "tomorrow": parse_day(data["weather"][1]),
        }
    except Exception as e:
        print(f"[WARN] Weather fetch failed: {e}")
        fallback = {"desc": "Dados indisponíveis", "desc_en": "", "min": "–", "max": "–", "rain": "–"}
        return {"today": fallback, "tomorrow": fallback}


# ─── Calendar ──────────────────────────────────────────────────────────────────

def rfc3339(dt: datetime) -> str:
    return dt.isoformat()


def get_all_events(cal_service, time_min: datetime, time_max: datetime):
    events = []
    for cal_id in CALENDAR_IDS:
        try:
            result = cal_service.events().list(
                calendarId=cal_id,
                timeMin=rfc3339(time_min),
                timeMax=rfc3339(time_max),
                singleEvents=True,
                orderBy="startTime",
                timeZone="America/Sao_Paulo",
                maxResults=250,
            ).execute()
            for ev in result.get("items", []):
                ev["_calendarId"] = cal_id
            events.extend(result.get("items", []))
        except Exception as e:
            print(f"[WARN] Calendar {cal_id}: {e}")
    return events


def event_start_dt(ev) -> datetime:
    s = ev.get("start", {})
    dt_str = s.get("dateTime") or s.get("date")
    if not dt_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt


def event_end_dt(ev) -> datetime:
    s = ev.get("end", {})
    dt_str = s.get("dateTime") or s.get("date")
    if not dt_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def is_all_day(ev) -> bool:
    return "date" in ev.get("start", {}) and "dateTime" not in ev.get("start", {})


def is_teams(ev) -> bool:
    loc = (ev.get("location") or "").lower()
    desc = (ev.get("description") or "").lower()
    return "teams" in loc or "microsoft teams" in loc or "teams" in desc[:200]


def is_presencial(ev) -> bool:
    loc = ev.get("location") or ""
    loc_lower = loc.lower()
    # Has a real address (not only Teams/Meet)
    has_address = len(loc.strip()) > 5 and (
        "rua " in loc_lower
        or "av." in loc_lower
        or "avenida" in loc_lower
        or "sala" in loc_lower
        or "andar" in loc_lower
        or "uva" in loc_lower.split("teams")[0] if "teams" in loc_lower else True
    )
    not_only_virtual = not (
        loc_lower.strip().startswith("reunião do microsoft teams")
        or loc_lower.strip() == "teams"
    )
    return has_address and not_only_virtual


def is_birthday(ev) -> bool:
    summary = (ev.get("summary") or "").lower()
    return "aniversário" in summary or "aniversario" in summary or "birthday" in summary


def is_holiday(ev) -> bool:
    return "holiday" in (ev.get("_calendarId") or "")


def is_routine_short(ev) -> bool:
    """15-min routine events like Aplicação/Resgate."""
    if is_all_day(ev):
        return False
    summary = (ev.get("summary") or "").lower()
    start = event_start_dt(ev)
    end = event_end_dt(ev)
    duration = (end - start).total_seconds() / 60
    return duration <= 15 and ("aplicação" in summary or "resgate" in summary)


def duration_min(ev) -> float:
    if is_all_day(ev):
        return 0
    start = event_start_dt(ev)
    end = event_end_dt(ev)
    return (end - start).total_seconds() / 60


# ─── HTML builder ──────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
       background: #f4f1ec; color: #2d2d2d; }
.wrapper { max-width: 680px; margin: 0 auto; background: #f4f1ec; }
.header { background: #1a3a2a; padding: 28px 32px 22px; }
.header h1 { color: #f0ebe0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }
.header .subtitle { color: #a8c4a0; font-size: 13px; margin-top: 4px; }
.section { padding: 24px 32px 8px; }
.section-title { font-size: 13px; font-weight: 700; text-transform: uppercase;
                 letter-spacing: 1.2px; color: #1a3a2a; border-bottom: 2px solid #1a3a2a;
                 padding-bottom: 6px; margin-bottom: 16px; }
/* Weather */
.weather-grid { display: flex; gap: 12px; }
.weather-card { flex: 1; background: #e8f0f8; border-radius: 10px; padding: 16px 18px; }
.weather-card .day-label { font-size: 11px; font-weight: 700; text-transform: uppercase;
                            letter-spacing: 0.8px; color: #4a6a8a; margin-bottom: 8px; }
.weather-card .icon { font-size: 36px; line-height: 1; }
.weather-card .condition { font-size: 13px; color: #2a4a6a; margin: 6px 0 4px; font-weight: 600; }
.weather-card .temp { font-size: 20px; font-weight: 700; color: #1a3a5a; }
.weather-card .temp span { font-size: 13px; font-weight: 400; color: #4a6a8a; }
.weather-card .rain { font-size: 12px; color: #3a6a9a; margin-top: 6px; }
.weather-src { font-size: 11px; color: #999; margin-top: 10px; }
.weather-src a { color: #4a90d9; }
/* Events */
.event-row { display: flex; align-items: flex-start; padding: 9px 0;
             border-bottom: 1px solid #e8e4de; }
.event-row:last-child { border-bottom: none; }
.event-time { min-width: 70px; font-size: 12px; color: #888;
              font-variant-numeric: tabular-nums; padding-top: 2px; line-height: 1.4; }
.event-body { flex: 1; }
.event-name { font-size: 14px; font-weight: 600; color: #1e1e1e; line-height: 1.4; }
.event-name.muted { color: #bbb; font-weight: 400; }
.event-loc { font-size: 12px; color: #777; margin-top: 2px; }
.badges { display: inline-flex; gap: 5px; margin-left: 6px; vertical-align: middle; }
.badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 20px;
         text-transform: uppercase; letter-spacing: 0.5px; }
.badge-teams { background: #dbeafe; color: #1d4ed8; }
.badge-presencial { background: #fee2e2; color: #b91c1c; }
.badge-aniversario { background: #ede9fe; color: #6d28d9; }
.badge-tentative { background: #fef3c7; color: #92400e; }
.badge-feriado { background: #d1fae5; color: #065f46; }
/* Next days */
.day-block { margin-bottom: 18px; }
.day-header { font-size: 13px; font-weight: 700; color: #1a3a2a; background: #e4ded5;
              padding: 6px 12px; border-radius: 6px; margin-bottom: 4px;
              display: flex; align-items: center; gap: 8px; }
.day-full { font-size: 11px; color: #c0392b; font-weight: 600; }
.empty-note { color: #999; font-size: 13px; font-style: italic; padding: 12px 0; }
.footer { background: #1a3a2a; padding: 14px 32px; margin-top: 8px; }
.footer p { color: #a8c4a0; font-size: 11px; }
"""


def badge(label, css_class):
    return f'<span class="badge {css_class}">{label}</span>'


def event_badges(ev):
    b = []
    if is_teams(ev):
        b.append(badge("Teams", "badge-teams"))
    if is_presencial(ev):
        b.append(badge("Presencial", "badge-presencial"))
    if is_birthday(ev):
        b.append(badge("Aniversário", "badge-aniversario"))
    if is_holiday(ev):
        b.append(badge("Feriado", "badge-feriado"))
    status = ev.get("status", "")
    my_status = ev.get("attendees", [{}])
    # Check tentative via attendees
    for att in ev.get("attendees", []):
        if att.get("self") and att.get("responseStatus") == "tentative":
            b.append(badge("Pendente", "badge-tentative"))
            break
    return "".join(b)


def render_event_row(ev, show_location=True):
    if is_all_day(ev):
        time_str = "Dia todo"
    else:
        start = event_start_dt(ev)
        end = event_end_dt(ev)
        time_str = f"{fmt_time(start)}–{fmt_time(end)}"

    summary = ev.get("summary") or "(sem título)"
    if is_birthday(ev) and "🎂" not in summary:
        summary = "🎂 " + summary

    muted = "muted" if is_routine_short(ev) else ""
    badges_html = event_badges(ev)

    loc = ev.get("location") or ""
    loc_display = ""
    if show_location and loc and not is_routine_short(ev):
        # Clean up location
        loc_clean = loc.replace("Reunião do Microsoft Teams; ", "").replace("Reunião do Microsoft Teams", "").strip("; ")
        if loc_clean:
            loc_display = f'<div class="event-loc">{loc_clean}</div>'

    return f"""
    <div class="event-row">
      <div class="event-time">{time_str}</div>
      <div class="event-body">
        <div class="event-name {muted}">{summary}{f'<span class="badges">{badges_html}</span>' if badges_html else ''}</div>
        {loc_display}
      </div>
    </div>"""


def build_html(weather, today_events, next_events, now):
    weekday_idx = now.weekday()  # 0=Mon
    weekday_name = WEEKDAY_PT[weekday_idx]
    date_str = f"{now.day:02d}/{MONTH_PT[now.month]}/{now.year}"
    date_label = f"{weekday_name}, {date_str}"

    tomorrow = now + timedelta(days=1)
    tomorrow_wday = WEEKDAY_PT[tomorrow.weekday()]
    tomorrow_label = f"{tomorrow_wday} {tomorrow.day:02d}/{MONTH_PT[tomorrow.month]}"

    tw = weather["today"]
    amw = weather["tomorrow"]
    tw_icon = weather_icon(tw["desc_en"])
    amw_icon = weather_icon(amw["desc_en"])

    # ── Today events ──
    today_sorted = sorted(today_events, key=event_start_dt)
    today_rows = "".join(render_event_row(ev) for ev in today_sorted)
    if not today_rows:
        today_rows = '<p class="empty-note">Nenhum evento encontrado para hoje.</p>'

    # ── Next 7 days — group by date ──
    by_day = defaultdict(list)
    for ev in next_events:
        dt = event_start_dt(ev).astimezone(TZ)
        day_key = dt.date()
        by_day[day_key].append(ev)

    next_blocks = ""
    for day_date in sorted(by_day.keys()):
        day_events = sorted(by_day[day_date], key=event_start_dt)

        # Omit purely routine short events from next-days view
        filtered = [ev for ev in day_events if not is_routine_short(ev)]
        if not filtered:
            continue

        wday = WEEKDAY_PT[day_date.weekday()]
        day_label = f"{wday} · {day_date.day:02d}/{MONTH_PT[day_date.month]}"
        is_full = len(filtered) >= 4
        full_badge = '<span class="day-full">· Dia cheio</span>' if is_full else ""

        rows = "".join(render_event_row(ev) for ev in filtered)
        next_blocks += f"""
    <div class="day-block">
      <div class="day-header">{day_label} {full_badge}</div>
      {rows}
    </div>"""

    if not next_blocks:
        next_blocks = '<p class="empty-note">Nenhum evento nos próximos 7 dias.</p>'

    gen_time = now.strftime("%d/%m/%Y às %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Briefing do Dia — {date_label}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrapper">

  <div class="header">
    <h1>🌿 Briefing do Dia</h1>
    <div class="subtitle">{date_label} · Campinas, SP</div>
  </div>

  <div class="section">
    <div class="section-title">Previsão do Tempo</div>
    <div class="weather-grid">
      <div class="weather-card">
        <div class="day-label">Hoje · {weekday_name[:3]} {now.day:02d}/{MONTH_PT[now.month]}</div>
        <div class="icon">{tw_icon}</div>
        <div class="condition">{tw["desc"]}</div>
        <div class="temp">{tw["min"]}° <span>/ {tw["max"]}°C</span></div>
        <div class="rain">🌧️ Chuva: {tw["rain"]}% de chance</div>
      </div>
      <div class="weather-card">
        <div class="day-label">Amanhã · {tomorrow_label}</div>
        <div class="icon">{amw_icon}</div>
        <div class="condition">{amw["desc"]}</div>
        <div class="temp">{amw["min"]}° <span>/ {amw["max"]}°C</span></div>
        <div class="rain">🌦️ Chuva: {amw["rain"]}% de chance</div>
      </div>
    </div>
    <p class="weather-src">Fonte: <a href="https://wttr.in/{CITY}">wttr.in</a></p>
  </div>

  <div class="section">
    <div class="section-title">Agenda de Hoje · {weekday_name} {date_str}</div>
    {today_rows}
  </div>

  <div class="section">
    <div class="section-title">Próximos 7 Dias</div>
    {next_blocks}
  </div>

  <div class="footer">
    <p>Gerado automaticamente em {gen_time} · Campinas, SP · {RECIPIENT}</p>
  </div>

</div>
</body>
</html>"""
    return html


# ─── Gmail draft ───────────────────────────────────────────────────────────────

def create_draft(gmail_service, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["To"] = RECIPIENT
    msg["From"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    draft = gmail_service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}},
    ).execute()
    return draft["id"]


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=8)  # 7 full days ahead

    weekday_idx = now.weekday()
    weekday_name = WEEKDAY_PT[weekday_idx]
    date_str = f"{weekday_name[:3]}, {now.day:02d}/{MONTH_PT[now.month]}/{now.year}"
    subject = f"🌿 Briefing do Dia — {date_str}"

    print(f"[INFO] Generating briefing: {subject}")

    # Weather
    print("[INFO] Fetching weather...")
    weather = get_weather()
    print(f"[INFO] Today: {weather['today']['desc']} {weather['today']['min']}/{weather['today']['max']}°C")

    # Google services
    print("[INFO] Authenticating with Google...")
    creds = get_credentials()
    cal_service = build("calendar", "v3", credentials=creds)
    gmail_service = build("gmail", "v1", credentials=creds)

    # Calendar events
    print("[INFO] Fetching today's events...")
    today_events = get_all_events(cal_service, today_start, today_end)
    print(f"[INFO] Today: {len(today_events)} events")

    print("[INFO] Fetching next 7 days events...")
    next_events = get_all_events(cal_service, tomorrow_start, week_end)
    print(f"[INFO] Next 7 days: {len(next_events)} events")

    # Build HTML
    print("[INFO] Building HTML...")
    html = build_html(weather, today_events, next_events, now)

    # Create draft
    print("[INFO] Creating Gmail draft...")
    draft_id = create_draft(gmail_service, subject, html)
    print(f"[SUCCESS] Draft created: {draft_id}")
    print(f"[SUCCESS] Subject: {subject}")


if __name__ == "__main__":
    main()
