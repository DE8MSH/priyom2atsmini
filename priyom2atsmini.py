import requests
import re
from datetime import datetime, timezone, timedelta
import sys

# =============================================
# Konfiguration
# =============================================
MAX_STATIONS = 64
MEM_FILE = "mem.txt"
USER_FILE = "user.txt"
PLAYLIST_FILE = "playlist.txt"

# Regex
regex = re.compile(r'(\w+)\s+(\d+)kHz.*?(USB/AM|USB|AM|CW|LSB|PSK|FSK|RTTY)?', re.IGNORECASE)
target_regex = re.compile(r'\[Target:\s*([^\]]+)\]', re.IGNORECASE)

def get_current_utc():
    return datetime.now(timezone.utc)

def get_midnight_utc():
    now = get_current_utc()
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

def fetch_events():
    url = "https://calendar2.priyom.org/events"
    now_utc = get_current_utc()
    midnight_utc = get_midnight_utc()

    params = {
        "timeMin": now_utc.isoformat(),
        "timeMax": midnight_utc.isoformat(),
        "maxResults": 200
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        print(f"Fehler beim Abrufen der Priyom-Daten: {e}")
        sys.exit(1)

def parse_summary(summary):
    match = regex.search(summary)
    if not match:
        return None, None, "USB"

    station = match.group(1).strip().upper()
    try:
        freq = int(match.group(2))
    except:
        return None, None, "USB"

    mode_raw = match.group(3).upper() if match.group(3) else ""

    if "USB/AM" in mode_raw or "USB" in mode_raw:
        display_mode = "USB"
    elif "AM" in mode_raw:
        display_mode = "AM "
    elif "CW" in mode_raw:
        display_mode = "CW "
    elif "RTTY" in mode_raw:
        display_mode = "RTTY"
    else:
        display_mode = "USB"

    return station, freq, display_mode

def has_target(summary):
    return bool(target_regex.search(summary))

# =============================================
# Hauptprogramm
# =============================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 priyom.py <DURATION> [tar|spl]")
        print("   DURATION = Minuten pro Station (z.B. 2, 5, 10)")
        print("   tar      = alle Sendungen (inkl. Targets)  ← Standard")
        print("   spl      = nur Split-Sendungen (ohne Target)")
        sys.exit(1)

    try:
        DURATION = int(sys.argv[1])
    except ValueError:
        print("Fehler: Erster Parameter muss eine Zahl sein (Minuten)!")
        sys.exit(1)

    # Modus: tar (alles) oder spl (nur ohne Target)
    mode = "tar"
    if len(sys.argv) >= 3:
        arg2 = sys.argv[2].strip().lower()
        if arg2 in ['spl', 'no', 'split', 'without']:
            mode = "spl"

    print(f"🚀 Priyom-Playlist Generator")
    print(f"   Dauer pro Station : {DURATION} Minuten")
    print(f"   Modus             : {mode.upper()} {'(alle Sendungen inkl. Targets)' if mode == 'tar' else '(nur Split-Sendungen ohne Target)'}")

    events = fetch_events()
    if not events:
        print("Keine Sendungen gefunden.")
        return

    now_utc = get_current_utc()
    collected = []

    for item in events:
        summary = item.get('summary', '')
        start_time_str = item.get('start', {}).get('dateTime')
        if not start_time_str or not summary:
            continue

        try:
            event_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        except:
            continue

        if event_time < now_utc or event_time >= get_midnight_utc():
            continue

        # Filter
        if mode == "spl" and has_target(summary):
            continue

        station, freq, display_mode = parse_summary(summary)

        if freq and 1000 <= freq <= 30000 and "Search" not in summary.upper():
            collected.append((event_time, freq, station, display_mode))

    if not collected:
        print("Keine passenden Sendungen gefunden.")
        return

    collected.sort(key=lambda x: x[0])

    # Entferne Duplikate: gleiche Frequenz + pro Minute nur eine Station
    seen_freq = {}
    seen_time = {}
    unique_list = []

    for event_time, freq, station, mode in collected:
        if freq in seen_freq:
            continue
        minute_key = event_time.strftime("%H:%M")
        if minute_key in seen_time:
            continue

        seen_freq[freq] = True
        seen_time[minute_key] = True
        unique_list.append((event_time, freq, station, mode))

    if len(unique_list) > MAX_STATIONS:
        unique_list = unique_list[:MAX_STATIONS]

    print(f"\n→ {len(unique_list)} Stationen werden gespeichert.\n")

    # mem.txt
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        f.write("9999\n")
        for i, (_, freq, _, _) in enumerate(unique_list, 1):
            f.write(f"{i},{freq:05d},19,2,0\n")

    # user.txt
    with open(USER_FILE, "w", encoding="utf-8") as f:
        f.write("9998\n")
        for _, freq, station, mode in sorted(unique_list, key=lambda x: x[1]):
            f.write(f"{freq:05d},{station} {mode}\n")

    # playlist.txt
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        for idx, (event_time, _, _, _) in enumerate(unique_list, 1):
            local_time = event_time.astimezone().strftime("%H:%M")
            f.write(f"{local_time} {idx} {DURATION}\n")

    # Übersicht
    print(f"{'Lokale Zeit':<12} {'Kanal':<6} {'Station':<12} {'Frequenz':<10} Mode")
    print("-" * 70)
    for idx, (event_time, freq, station, mode) in enumerate(unique_list, 1):
        local_time = event_time.astimezone().strftime("%H:%M")
        print(f"{local_time:<12} {idx:<6} {station:<12} {freq} kHz {mode}")

    print(f"\n🎉 Fertig! Dateien erstellt mit Dauer = {DURATION} min ({mode.upper()}-Modus)")
    print("   • mem.txt")
    print("   • user.txt")
    print("   • playlist.txt")


if __name__ == "__main__":
    main()
