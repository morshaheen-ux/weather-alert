#!/usr/bin/env python3
"""
Daily weather notifier — Berlin, Bremen, Vienna (tomorrow's forecast).
Runs on GitHub Actions. Uses only the Python standard library.

Channels (each is optional — configured via environment variables / GitHub Secrets):
  Email (SMTP, e.g. DreamHost):
    SMTP_HOST   e.g. smtp.dreamhost.com
    SMTP_PORT   e.g. 465 (SSL)  — default 465
    SMTP_USER   full mailbox, e.g. info@your-domain.de
    SMTP_PASS   mailbox password
    MAIL_TO     recipient(s), comma-separated
  WhatsApp (CallMeBot, free):
    WHATSAPP_PHONE   e.g. +4917612345678
    WHATSAPP_APIKEY  key you receive from CallMeBot (one-time setup)
"""

import json
import os
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.utils import formatdate

CITIES = [
    ("Berlin", 52.520, 13.405, "Europe/Berlin"),
    ("Bremen", 53.079, 8.801, "Europe/Berlin"),
    ("Wien",   48.208, 16.373, "Europe/Vienna"),
]

WMO = {
    0: "Klar ☀️", 1: "Überwiegend klar 🌤️", 2: "Teils bewölkt ⛅", 3: "Bedeckt ☁️",
    45: "Nebel 🌫️", 48: "Reifnebel 🌫️",
    51: "Leichter Niesel 🌦️", 53: "Niesel 🌦️", 55: "Starker Niesel 🌧️",
    61: "Leichter Regen 🌧️", 63: "Regen 🌧️", 65: "Starker Regen 🌧️",
    66: "Gefrierender Regen 🌧️", 67: "Starker gefrierender Regen 🌧️",
    71: "Leichter Schneefall 🌨️", 73: "Schneefall 🌨️", 75: "Starker Schneefall ❄️",
    77: "Schneegriesel ❄️",
    80: "Leichte Schauer 🌦️", 81: "Schauer 🌧️", 82: "Starke Schauer ⛈️",
    85: "Schneeschauer 🌨️", 86: "Starke Schneeschauer 🌨️",
    95: "Gewitter ⛈️", 96: "Gewitter mit Hagel ⛈️", 99: "Schweres Gewitter ⛈️",
}


def fetch_city(name, lat, lon, tz):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,wind_speed_10m_max,sunrise,sunset"
        f"&timezone={urllib.parse.quote(tz)}&forecast_days=3"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.load(r)["daily"]
    i = 1  # tomorrow
    return {
        "name": name,
        "date": d["time"][i],
        "code": d["weather_code"][i],
        "tmax": round(d["temperature_2m_max"][i]),
        "tmin": round(d["temperature_2m_min"][i]),
        "rain": d["precipitation_probability_max"][i],
        "wind": round(d["wind_speed_10m_max"][i]),
        "sunrise": d["sunrise"][i][11:16],
        "sunset": d["sunset"][i][11:16],
    }


def build_message(cities):
    date = cities[0]["date"]
    lines = [f"🌤 Wettervorhersage für morgen ({date})", ""]
    for c in cities:
        cond = WMO.get(c["code"], "–")
        lines.append(f"📍 {c['name']}: {cond}")
        lines.append(f"   🌡 {c['tmin']}° bis {c['tmax']}°C · ☔ Regen {c['rain']}% · 💨 Wind {c['wind']} km/h")
        lines.append(f"   🌅 {c['sunrise']} / 🌇 {c['sunset']}")
        lines.append("")
    lines.append("— Automatischer Wetterdienst (Open-Meteo)")
    return "\n".join(lines)


def send_email(text, date):
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    pw = os.environ.get("SMTP_PASS")
    to = os.environ.get("MAIL_TO")
    if not all([host, user, pw, to]):
        print("Email: skipped (SMTP secrets not set)")
        return
    port = int(os.environ.get("SMTP_PORT", "465"))
    recipients = [a.strip() for a in to.split(",") if a.strip()]

    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = f"Wetter morgen ({date}): Berlin · Bremen · Wien"
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, recipients, msg.as_string())
    else:  # 587 STARTTLS
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, pw)
            s.sendmail(user, recipients, msg.as_string())
    print(f"Email: sent to {len(recipients)} recipient(s)")


def send_whatsapp(text):
    phone = os.environ.get("WHATSAPP_PHONE")
    key = os.environ.get("WHATSAPP_APIKEY")
    if not all([phone, key]):
        print("WhatsApp: skipped (CallMeBot secrets not set)")
        return
    url = (
        "https://api.callmebot.com/whatsapp.php?"
        + urllib.parse.urlencode({"phone": phone, "apikey": key, "text": text})
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        print(f"WhatsApp: HTTP {r.status}")


def main():
    cities = [fetch_city(*c) for c in CITIES]
    text = build_message(cities)
    print(text)
    print("-" * 40)
    errors = []
    for fn, args in [(send_email, (text, cities[0]["date"])), (send_whatsapp, (text,))]:
        try:
            fn(*args)
        except Exception as e:  # keep other channels running
            errors.append(f"{fn.__name__}: {e}")
            print(f"ERROR {fn.__name__}: {e}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
