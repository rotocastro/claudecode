#!/usr/bin/env python3
"""
Briefing diário via Telegram.
Lê calendário via iCal (sem OAuth) e envia mensagem no Telegram.
"""

import os
import requests
from datetime import datetime, timedelta, date
from collections import defaultdict

import pytz
import recurring_ical_events
from icalendar import Calendar

# ─── Config ────────────────────────────────────────────────────────────────────

TZ = pytz.timezone("America/Sao_Paulo")
CITY_WEATHER = "Campinas,BR"

WEEKDAY_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTH_PT = ["", "jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez"]

WEATHER_ICONS = {
    "thundery": "⛈️", "blizzard": "🌨️", "heavy rain": "🌧️",
    "rain": "🌦️", "drizzle": "🌦️", "shower": "🌦️",
    "overcast": "☁️", "cloudy": "⛅", "partly": "⛅",
    "mist": "🌫️", "fog": "🌫️", "clear": "☀️", "sunny": "☀️",
}

DESC_PT = {
    "Sunny": "Ensolarado", "Clear": "Céu limpo",
    "Partly cloudy": "Parc. nublado", "Cloudy": "Nublado",
    "Overcast": "Fechado", "Mist": "Névoa", "Fog": "Nevoeiro",
    "Patchy rain possible": "Chuva isolada possível",
    "Light rain": "Chuva fraca", "Moderate rain": "Chuva moderada",
    "Heavy rain": "Chuva forte", "Light drizzle": "Garoa",
    "Light rain shower": "Pancada fraca",
    "Moderate or heavy rain shower": "Pancada forte",
    "Patchy light rain": "Chuva fraca isolada",
    "Moderate rain at times": "Chuva moderada",
    "Heavy rain at times": "Chuva forte a intervalos",
    "Patchy light rain with thunder": "Chuva com trovoadas",
    "Moderate or heavy rain with thunder": "Chuva forte com trovoadas",
    "Thundery outbreaks possible": "Trovoadas possíveis",
    "Thunder outbreaks possible": "Trovoadas possíveis",
}


def weather_icon(desc: str) -> str:
    dl = desc.lower()
    for key, icon in WEATHER_ICONS.items():
        if key in dl:
            return icon
    return "🌤️"


# ─── Weather ───────────────────────────────────────────────────────────────────

def get_weather() -> dict:
    try:
        r = requests.get(
            f"https://wttr.in/{CITY_WEATHER}?format=j1",
            timeout=12, headers={"User-Agent": "curl/7.68.0"}
        )
        data = r.json()

        def parse(day):
            mid = day["hourly"][min(4, len(day["hourly"]) - 1)]
            desc = mid["weatherDesc"][0]["value"]
            return {
                "desc": DESC_PT.get(desc, desc),
                "desc_en": desc,
                "min": day["mintempC"],
                "max": day["maxtempC"],
                "rain": mid.get("chanceofrain", "?"),
            }

        return {"today": parse(data["weather"][0]), "tomorrow": parse(data["weather"][1])}
    except Exception as e:
        print(f"[WARN] Weather: {e}")
        fb = {"desc": "Indisponível", "desc_en": "", "min": "–", "max": "–", "rain": "–"}
        return {"today": fb, "tomorrow": fb}


# ─── Calendar (iCal) ───────────────────────────────────────────────────────────

def fetch_ical(url: str) -> Calendar:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return Calendar.from_ical(r.content)


def get_events(ical_urls: list, start_dt: datetime, end_dt: datetime) -> list:
    events = []
    for url in ical_urls:
        try:
            cal = fetch_ical(url)
            for component in recurring_ical_events.of(cal).between(start_dt, end_dt):
                ev_start = component.get("DTSTART").dt
                ev_end_raw = component.get("DTEND")
                ev_end = ev_end_raw.dt if ev_end_raw else ev_start
                summary = str(component.get("SUMMARY", "(sem título)"))
                location = str(component.get("LOCATION", "")) if component.get("LOCATION") else ""

                if isinstance(ev_start, date) and not isinstance(ev_start, datetime):
                    ev_start = TZ.localize(datetime.combine(ev_start, datetime.min.time()))
                    ev_end = TZ.localize(datetime.combine(ev_end, datetime.min.time()))
                    all_day = True
                else:
                    ev_start = ev_start.astimezone(TZ) if ev_start.tzinfo else TZ.localize(ev_start)
                    ev_end = ev_end.astimezone(TZ) if ev_end.tzinfo else TZ.localize(ev_end)
                    all_day = False

                events.append({
                    "summary": summary,
                    "location": location,
                    "start": ev_start,
                    "end": ev_end,
                    "all_day": all_day,
                })
        except Exception as e:
            print(f"[WARN] iCal fetch error: {e}")

    # Deduplicate by (summary, start)
    seen, unique = set(), []
    for ev in events:
        key = (ev["summary"], ev["start"])
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return sorted(unique, key=lambda x: x["start"])


# ─── Formatting ────────────────────────────────────────────────────────────────

def is_birthday(ev) -> bool:
    s = ev["summary"].lower()
    return "aniversário" in s or "aniversario" in s or "birthday" in s


def is_teams(ev) -> bool:
    return "teams" in ev["location"].lower()


def is_routine(ev) -> bool:
    if ev["all_day"]:
        return False
    dur = (ev["end"] - ev["start"]).total_seconds() / 60
    s = ev["summary"].lower()
    return dur <= 15 and any(x in s for x in ["aplicação", "resgate"])


def fmt_event(ev) -> str | None:
    if is_routine(ev):
        return None

    time_str = "Dia todo" if ev["all_day"] else f"{ev['start'].strftime('%H:%M')}–{ev['end'].strftime('%H:%M')}"
    summary = ("🎂 " if is_birthday(ev) else "") + ev["summary"]

    tag = ""
    if is_teams(ev):
        tag = " [Teams]"
    elif ev["location"] and len(ev["location"]) > 3 and "teams" not in ev["location"].lower():
        tag = " [📍]"

    return f"  {time_str}  {summary}{tag}"


def build_message(weather: dict, today_events: list, next_events: list, now: datetime) -> str:
    wday = WEEKDAY_SHORT[now.weekday()]
    date_str = f"{wday}, {now.day:02d}/{MONTH_PT[now.month]}/{now.year}"
    tomorrow = now + timedelta(days=1)
    tw, amw = weather["today"], weather["tomorrow"]
    tw_icon = weather_icon(tw["desc_en"])
    amw_icon = weather_icon(amw["desc_en"])
    amw_wday = WEEKDAY_SHORT[tomorrow.weekday()]

    lines = [
        "🌿 <b>Briefing do Dia</b>",
        f"<b>{date_str}</b> · Campinas, SP",
        "",
        f"{tw_icon} <b>Hoje</b>  {tw['desc']}  {tw['min']}°/{tw['max']}°C  🌧 {tw['rain']}%",
        f"{amw_icon} <b>{amw_wday}</b>  {amw['desc']}  {amw['min']}°/{amw['max']}°C  🌧 {amw['rain']}%",
        "",
        f"📅 <b>Hoje — {wday} {now.day:02d}/{MONTH_PT[now.month]}</b>",
    ]

    today_rows = [fmt_event(ev) for ev in today_events]
    today_rows = [r for r in today_rows if r]
    lines += today_rows if today_rows else ["  (sem eventos)"]

    by_day = defaultdict(list)
    for ev in next_events:
        by_day[ev["start"].date()].append(ev)

    if by_day:
        lines.append("")
        lines.append("📆 <b>Próximos dias</b>")
        for day_date in sorted(by_day.keys()):
            rows = [fmt_event(ev) for ev in by_day[day_date]]
            rows = [r for r in rows if r]
            if not rows:
                continue
            dw = WEEKDAY_SHORT[day_date.weekday()]
            lines.append(f"<b>{dw} {day_date.day:02d}/{MONTH_PT[day_date.month]}</b>")
            lines += rows

    lines += ["", f"<i>Gerado às {now.strftime('%H:%M')}</i>"]
    return "\n".join(lines)


# ─── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def post(chunk):
        r = requests.post(url, json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"})
        r.raise_for_status()

    if len(text) <= 4096:
        post(text)
        return

    # Split at line breaks if too long
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > 4000:
            chunks.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current)
    for chunk in chunks:
        post(chunk)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=8)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    ical_urls = [u.strip() for u in os.environ.get("GCAL_ICAL_URLS", "").split(",") if u.strip()]

    print(f"[INFO] {len(ical_urls)} calendário(s) configurado(s)")

    print("[INFO] Buscando clima...")
    weather = get_weather()
    print(f"[INFO] Hoje: {weather['today']['desc']} {weather['today']['min']}/{weather['today']['max']}°C")

    print("[INFO] Buscando eventos de hoje...")
    today_events = get_events(ical_urls, today_start, today_end)
    print(f"[INFO] Hoje: {len(today_events)} evento(s)")

    print("[INFO] Buscando próximos 7 dias...")
    next_events = get_events(ical_urls, tomorrow_start, week_end)
    print(f"[INFO] Próximos 7 dias: {len(next_events)} evento(s)")

    message = build_message(weather, today_events, next_events, now)

    print("[INFO] Enviando para o Telegram...")
    send_telegram(token, chat_id, message)
    print("[OK] Mensagem enviada!")


if __name__ == "__main__":
    main()
