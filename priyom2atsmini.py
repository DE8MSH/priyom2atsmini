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
        print(f"Fehler beim Abrufen: {e}")
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

# =============================================
# Hauptprogramm
# =============================================
def main():
    print("🚀 Hole Priyom Sendungen ab jetzt bis 00:00 UTC...\n")
    
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
        
        station, freq, display_mode = parse_summary(summary)
        
        if freq and 1000 <= freq <= 30000 and "Search" not in summary.upper():
            collected.append((event_time, freq, station, display_mode))   # Zeit zuerst für Sortierung
    
    if not collected:
        print("Keine Sendungen gefunden.")
        return
    
    # Sortiere nach UTC-Zeit (wichtig für "erste Station bei gleicher Zeit")
    collected.sort(key=lambda x: x[0])
    
    # Doppelte Frequenzen entfernen + bei gleicher Minute nur die erste Station behalten
    seen_freq = {}
    seen_time = {}          # Neue Regel: pro Minute nur eine Station
    unique_list = []
    
    for event_time, freq, station, mode in collected:
        # Frequenz schon vorhanden? → überspringen
        if freq in seen_freq:
            continue
        
        # Gleiche Minute schon verarbeitet? → nur die erste Station nehmen
        minute_key = event_time.strftime("%H:%M")
        if minute_key in seen_time:
            continue
        
        seen_freq[freq] = True
        seen_time[minute_key] = True
        unique_list.append((event_time, freq, station, mode))
    
    # Auf max 64 begrenzen
    if len(unique_list) > MAX_STATIONS:
        unique_list = unique_list[:MAX_STATIONS]
    
    print(f"{len(unique_list)} Stationen für mem.txt / user.txt / playlist.txt\n")
    
    # ====================== mem.txt ======================
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        f.write("9999\n")
        for i, (_, freq, station, mode) in enumerate(unique_list, 1):
            freq_str = f"{freq:05d}"
            f.write(f"{i},{freq_str},19,2,0\n")
    
    # ====================== user.txt ======================
    freq_sorted = sorted(unique_list, key=lambda x: x[1])   # nach Frequenz
    with open(USER_FILE, "w", encoding="utf-8") as f:
        f.write("9998\n")
        for _, freq, station, mode in freq_sorted:
            freq_str = f"{freq:05d}"
            name = f"{station} {mode}"
            f.write(f"{freq_str},{name}\n")
    
    # ====================== playlist.txt (nur erste Station pro Minute) ======================
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        for idx, (event_time, freq, station, mode) in enumerate(unique_list, 1):
            local_dt = event_time.astimezone()           # Umrechnung auf deine lokale PC-Zeit
            time_str = local_dt.strftime("%H:%M")
            f.write(f"{time_str} {idx} 5\n")
    
    # ====================== Übersicht ======================
    print(f"{'Lokale Zeit':<12} {'Kanal':<6} {'Station':<12} {'Frequenz':<10} Mode")
    print("-" * 68)
    
    for idx, (event_time, freq, station, mode) in enumerate(unique_list, 1):
        local_dt = event_time.astimezone()
        time_str = local_dt.strftime("%H:%M")
        print(f"{time_str:<12} {idx:<6} {station:<12} {freq} kHz   {mode}")
    
    print(f"\n🎉 Fertig! Alle Dateien wurden erstellt:")
    print(f"   • mem.txt       → Speicherplätze (Mode 2 = USB)")
    print(f"   • user.txt      → Stationsnamen")
    print(f"   • playlist.txt  → Automatische Wiedergabe (nur erste Station pro Minute, 5 Min Dauer)")

if __name__ == "__main__":
    main()
