"""
pmd_rainfall_parser.py - Fixed version for Lahore WASA breakdown
"""

import argparse
import difflib
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone

import pdfplumber

# --------------------------------------------------------------------------
# Station lookup
# --------------------------------------------------------------------------

STATIONS_LOOKUP = [
    {"name": "Gilgit", "lat": 35.9167, "lon": 74.3333},
    {"name": "Skardu", "lat": 35.3, "lon": 75.6833},
    {"name": "Astore", "lat": 35.3333, "lon": 74.9},
    {"name": "Attock", "lat": 33.7667, "lon": 72.3667},
    {"name": "Bacha Khan Airport", "lat": 33.99195012, "lon": 71.51571649},
    {"name": "Bagrote", "lat": 35.6664, "lon": 74.5325},
    {"name": "Bahawalnagar", "lat": 29.9986, "lon": 73.2536},
    {"name": "Bahawalpur", "lat": 29.9986, "lon": 71.7833},
    {"name": "Bajaur (Khaar)", "lat": 34.8, "lon": 71.5},
    {"name": "Balakot", "lat": 34.55, "lon": 72.35},
    {"name": "Bandi Abbas Pur", "lat": 33.8135, "lon": 73.9774},
    {"name": "Bannu", "lat": 33.0, "lon": 70.1},
    {"name": "Bar Khan", "lat": 29.8833, "lon": 69.5167},
    {"name": "Barnala", "lat": 32.8707, "lon": 74.2475},
    {"name": "Bhakkar", "lat": 31.6167, "lon": 71.0667},
    {"name": "Bunji", "lat": 35.6667, "lon": 74.6333},
    {"name": "Chakwal", "lat": 32.9307, "lon": 72.8532},
    {"name": "Chattar Kalas", "lat": 33.87, "lon": 73.79},
    {"name": "Cherat", "lat": 33.8167, "lon": 71.55},
    {"name": "Chhor", "lat": 24.8333, "lon": 69.7833},
    {"name": "Chilas", "lat": 35.4167, "lon": 74.1},
    {"name": "Chitral", "lat": 35.85, "lon": 71.8333},
    {"name": "D G Khan", "lat": 30.05, "lon": 70.6667},
    {"name": "D I Khan", "lat": 31.8167, "lon": 70.9333},
    {"name": "Dadu", "lat": 26.7167, "lon": 67.7667},
    {"name": "Dhulli", "lat": 33.1812, "lon": 73.6815},
    {"name": "Dir", "lat": 35.2, "lon": 71.85},
    {"name": "Drosh", "lat": 35.5667, "lon": 71.7833},
    {"name": "Faisalabad", "lat": 31.4333, "lon": 73.15},
    {"name": "Garhi Dopatta", "lat": 34.2256, "lon": 73.6154},
    {"name": "Ghalanai", "lat": 34.32561066, "lon": 71.39578112},
    {"name": "Gujranwala", "lat": 32.16266251, "lon": 74.15911639},
    {"name": "Gujrat", "lat": 32.5742, "lon": 74.0754},
    {"name": "Gupis", "lat": 36.1667, "lon": 73.4},
    {"name": "Hafizabad", "lat": 32.0679, "lon": 73.685},
    {"name": "Hunza", "lat": 36.3167, "lon": 74.65},
    {"name": "Hyderabad", "lat": 25.4039, "lon": 68.3561},
    {"name": "Islamabad", "lat": 33.6844, "lon": 73.0479},
    {"name": "Jacobabad", "lat": 28.2833, "lon": 68.45},
    {"name": "Jhang", "lat": 31.2667, "lon": 72.3167},
    {"name": "Jhelum", "lat": 32.9333, "lon": 73.6833},
    {"name": "Joharabad", "lat": 32.5, "lon": 72.4333},
    {"name": "Kakul", "lat": 34.1831, "lon": 73.2421},
    {"name": "Kalam", "lat": 35.8333, "lon": 72.9833},
    {"name": "Kalat", "lat": 29.0333, "lon": 66.5667},
    {"name": "Karor(Layyah)", "lat": 30.9646, "lon": 70.9444},
    {"name": "Kasur", "lat": 31.1165, "lon": 74.4467},
    {"name": "Khanewal", "lat": 30.3017, "lon": 71.9326},
    {"name": "Khanpur", "lat": 28.65, "lon": 70.6833},
    {"name": "Khuzdar", "lat": 27.8167, "lon": 66.6333},
    {"name": "Kot Addu", "lat": 30.4667, "lon": 70.9667},
    {"name": "Kotli", "lat": 33.5167, "lon": 73.9},
    {"name": "Lahore", "lat": 31.5833, "lon": 74.34},
    {"name": "Landi Kota", "lat": 34.1053392, "lon": 71.1551532},
    {"name": "Larkana", "lat": 27.56, "lon": 68.2167},
    {"name": "Lasbella", "lat": 26.1833, "lon": 66.3},
    {"name": "Loralai", "lat": 30.3705, "lon": 68.598},
    {"name": "Malam Jabba", "lat": 34.75, "lon": 72.9},
    {"name": "Mandi Bahauddin", "lat": 32.2300, "lon": 72.9000},
    {"name": "Mangla", "lat": 33.0667, "lon": 72.65},
    {"name": "Mir Khani", "lat": 35.5, "lon": 74.7},
    {"name": "Mithi", "lat": 24.7406, "lon": 69.8007},
    {"name": "Mohmand (Ghalanai)", "lat": 34.3205, "lon": 71.4087},
    {"name": "Multan", "lat": 30.1575, "lon": 71.5249},
    {"name": "Murree", "lat": 33.907, "lon": 73.3907},
    {"name": "Muzaffarabad", "lat": 34.3667, "lon": 73.4833},
    {"name": "Narowal", "lat": 32.1, "lon": 74.8833},
    {"name": "Noor Pur Thal", "lat": 31.8667, "lon": 71.9},
    {"name": "Okara", "lat": 30.8, "lon": 73.8},
    {"name": "Parachinar", "lat": 33.8667, "lon": 70.0833},
    {"name": "Pathan (Kohistan)", "lat": 35.0667, "lon": 73.0},
    {"name": "Peshawar", "lat": 34.0151, "lon": 71.5805},
    {"name": "Quetta", "lat": 30.1798, "lon": 66.975},
    {"name": "Rahim Yar Khan", "lat": 28.4195, "lon": 70.2989},
    {"name": "Rawalakot", "lat": 33.8667, "lon": 73.6833},
    {"name": "Rawalpindi", "lat": 33.5651, "lon": 73.0169},
    {"name": "Sahiwal", "lat": 30.65, "lon": 73.1667},
    {"name": "Saidu Sharif", "lat": 34.7333, "lon": 72.55},
    {"name": "Samungli", "lat": 30.255, "lon": 66.9376},
    {"name": "Sargodha", "lat": 32.05, "lon": 72.6667},
    {"name": "Sheikhupura", "lat": 31.7131, "lon": 73.9783},
    {"name": "Sialkot", "lat": 32.50306337, "lon": 74.54033488},
    {"name": "Sibbi", "lat": 29.5435, "lon": 67.8773},
    {"name": "Tandali", "lat": 34.4, "lon": 73.5},
    {"name": "Tharparkar", "lat": 24.88213673, "lon": 69.98613515},
    {"name": "Timergara (Lower Dir)", "lat": 34.85, "lon": 71.85},
    {"name": "Toba Tek Singh", "lat": 30.97127, "lon": 72.48275},
    {"name": "Zhob", "lat": 31.3404, "lon": 69.4496},
    {"name": "Ziarat", "lat": 30.3818, "lon": 67.7253},
    {"name": "Karachi", "lat": 25.04030296, "lon": 67.13690003},
    {"name": "Shaheed Benazirabad", "lat": 26.39555653, "lon": 68.40232736},
    {"name": "Sakrand", "lat": 26.14472159, "lon": 68.26852179},
    {"name": "Mir Pur Khas", "lat": 25.52281047, "lon": 69.00371803},
    {"name": "Tando Jam", "lat": 25.42646362, "lon": 68.53298908},
    {"name": "Thatta", "lat": 24.75057099, "lon": 67.91016402},
    {"name": "Pasni", "lat": 25.29109834, "lon": 63.36130529},
    {"name": "Takht Bai", "lat": 34.28673765, "lon": 71.9321852},
    {"name": "Mardan", "lat": 34.20338568, "lon": 72.04287245},
]

REGION_HEADERS = {
    "SINDH", "KHYBER PAKHTUNKHWA", "PUNJAB", "KASHMIR",
    "GILGIT BALTISTAN", "BALOCHISTAN",
}

NAME_ALIASES = {
    "pattan": "pathan kohistan",
    "dera ismail khan": "d i khan",
    "dera ghazi khan": "d g khan",
}

# A word is a "value word" if it matches this
VALUE_TOKEN_RE = re.compile(r"^\(?\d{1,3}(?:\.\d+)?\)?,?$|^\(?Trace\)?,?$|^\(?NIL\)?,?$", re.I)
STATION_ZONE_MAX_X = 250

# Updated regex to capture ALL numbers including those with parentheses
NUMBER_IN_TEXT_RE = re.compile(r"\(?(\d{1,3}(?:\.\d+)?)\)?|\bTrace\b|\bNIL\b", re.I)

STOP_RE = re.compile(
    r"Maximum\s+Wind|Wind\s*\(\s*KT\s*\)|Water\s+Level|Nullah\s+Lai|Flood\s+Situation", re.I
)
DATE_RE = re.compile(r"(\d{2}-\d{2}-\d{4})")

FUZZY_MATCH_THRESHOLD = 0.82

CUSTOM_STATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_stations.json")


def load_custom_stations(path=CUSTOM_STATIONS_PATH):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_custom_station(entry, path=CUSTOM_STATIONS_PATH):
    stations = load_custom_stations(path)
    stations = [s for s in stations if s["name"].strip().lower() != entry["name"].strip().lower()]
    stations.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=2, ensure_ascii=False)


def build_lookup():
    lookup = list(STATIONS_LOOKUP)
    lookup.extend(load_custom_stations())
    return lookup


def token_to_mm(tok):
    tok = tok.strip()
    if re.match(r"^nil$", tok, re.I):
        return 0.0
    if re.match(r"^trace$", tok, re.I):
        return 1.0
    try:
        return float(tok)
    except ValueError:
        return None


def extract_all_values(value_text):
    """Extract ALL numeric values from text and return the MAXIMUM.
    For Lahore with WASA breakdown, this ensures we take 43mm not 9mm."""
    vals = []
    for m in NUMBER_IN_TEXT_RE.finditer(value_text):
        raw = m.group(0)
        # Clean up parentheses and spaces
        raw = re.sub(r"[()]", "", raw)
        v = token_to_mm(raw)
        if v is not None:
            vals.append(v)
    
    # Return all values found (will be used by caller to take max)
    return vals


def normalize_name(s):
    s = s.lower()
    s = re.sub(r"[().&']", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_station(raw_name, lookup):
    n = normalize_name(raw_name)
    if not n:
        return None

    # Tier 0: known naming-variant alias
    if n in NAME_ALIASES:
        target = NAME_ALIASES[n]
        for s in lookup:
            if normalize_name(s["name"]) == target:
                return s

    # Tier 1: exact normalized match
    for s in lookup:
        if normalize_name(s["name"]) == n:
            return s

    # Tier 2: substring containment either way
    for s in lookup:
        sn = normalize_name(s["name"])
        if sn and (sn in n or n in sn):
            return s

    # Tier 3: fuzzy match
    names = [normalize_name(s["name"]) for s in lookup]
    close = difflib.get_close_matches(n, names, n=1, cutoff=FUZZY_MATCH_THRESHOLD)
    if close:
        for s in lookup:
            if normalize_name(s["name"]) == close[0]:
                return s

    # Tier 4: word-by-word shrinking
    words = n.split()
    for length in range(len(words) - 1, 0, -1):
        for start in range(0, len(words) - length + 1):
            candidate = " ".join(words[start:start + length])
            for s in lookup:
                if normalize_name(s["name"]) == candidate:
                    return s

    return None


def extract_lines(pdf_path):
    """Groups words into visual text lines using x/y position."""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            page_lines = []
            TOL = 3
            for w in words:
                match = None
                for l in page_lines:
                    if abs(l["top"] - w["top"]) <= TOL:
                        match = l
                        break
                if match is None:
                    match = {"top": w["top"], "items": []}
                    page_lines.append(match)
                match["items"].append(w)
            for l in page_lines:
                l["items"].sort(key=lambda w: w["x0"])
            page_lines.sort(key=lambda l: l["top"])
            lines.extend(page_lines)
    return lines


def classify_line(items):
    """Splits a line's words into (station_text, value_text)."""
    station_words, value_words = [], []
    for w in items:
        if VALUE_TOKEN_RE.match(w["text"]) or w["x0"] >= STATION_ZONE_MAX_X:
            value_words.append(w)
        else:
            station_words.append(w)
    station_text = re.sub(r"\s+", " ", " ".join(w["text"] for w in station_words)).strip()
    value_text = re.sub(r"\s+", " ", " ".join(w["text"] for w in value_words)).strip()
    return station_text, value_text


def _is_dangling(station_text):
    """True if station-name fragment looks like an incomplete list."""
    t = station_text.rstrip()
    if t.endswith((",", "&")):
        return True
    if re.search(r"\band\b\s*$", t, re.I):
        return True
    return False


def build_rows(lines):
    """Row-builder with improved value extraction."""
    rows = []
    pending = None
    current_region = "Unspecified"
    saw_region = False

    def flush():
        nonlocal pending
        if pending is not None:
            rows.append(pending)
            pending = None

    for line in lines:
        raw_text = " ".join(w["text"] for w in line["items"])
        raw_text = re.sub(r"\s+", " ", raw_text).strip()
        if not raw_text:
            continue

        upper = raw_text.upper()
        if upper in REGION_HEADERS:
            flush()
            current_region = upper
            saw_region = True
            continue
        if not saw_region:
            continue
        if re.match(r"^Stations\s+Rainfall", raw_text, re.I):
            continue
        if re.search(r"Total\s+Rainfall\s*\(mm\)|\bPST\b", raw_text, re.I):
            continue
        if STOP_RE.search(raw_text):
            break

        station_text, value_text = classify_line(line["items"])
        if not station_text and not value_text:
            continue

        if station_text:
            if pending is not None and (pending["awaiting_name"] or pending["dangling"]):
                pending["station"] = (pending["station"] + " " + station_text).strip() \
                    if pending["station"] else station_text
                pending["awaiting_name"] = False
                pending["dangling"] = _is_dangling(station_text)
                if value_text:
                    pending["value"] = (pending["value"] + " " + value_text).strip() \
                        if pending["value"] else value_text
            else:
                flush()
                pending = {
                    "region": current_region, "station": station_text, "value": value_text,
                    "awaiting_name": False, "dangling": _is_dangling(station_text),
                }
        else:
            if value_text:
                if pending is not None:
                    pending["value"] = (pending["value"] + " " + value_text).strip() \
                        if pending["value"] else value_text
                else:
                    pending = {
                        "region": current_region, "station": "", "value": value_text,
                        "awaiting_name": True, "dangling": False,
                    }

    flush()
    return rows


def parse_pdf(pdf_path, lookup=None, interactive=False):
    """Returns (date_label, stations, unmatched)."""
    if lookup is None:
        lookup = build_lookup()

    lines = extract_lines(pdf_path)
    full_text = "\n".join(" ".join(w["text"] for w in l["items"]) for l in lines)
    dm = DATE_RE.search(full_text)
    date_label = dm.group(1) if dm else None

    rows = build_rows(lines)

    results = []
    unmatched = []
    prompted_this_run = {}

    for row in rows:
        region_name = row["region"].title()
        station_text = row["station"].strip()
        value_text = row["value"].strip()
        
        if not station_text:
            continue

        # Extract ALL values and take the maximum
        all_vals = extract_all_values(value_text)
        
        # Special handling for Lahore and other cities with WASA breakdowns
        # If we have multiple values, take the maximum (for Lahore, this will be 43mm not 9mm)
        if all_vals:
            mm = max(all_vals)
        else:
            # No values found, skip this row
            continue

        # Check if this is a list of stations sharing values
        looks_like_list = bool(re.search(r",|\band\b|&", station_text, re.I))

        if looks_like_list and len(all_vals) >= 1:
            # Multiple stations sharing one value
            for name_raw in re.split(r",|\s+and\s+|\s*&\s*", station_text, flags=re.I):
                name_raw = name_raw.strip()
                if not name_raw:
                    continue
                station = _resolve_station(name_raw, lookup, mm, region_name, unmatched,
                                          prompted_this_run, interactive)
                if station:
                    results.append(station)
            continue

        # Single station with its value
        note = value_text if len(all_vals) > 1 else None
        station = _resolve_station(station_text, lookup, mm, region_name, unmatched,
                                   prompted_this_run, interactive, note=note)
        if station:
            results.append(station)

    # Deduplicate: keep max value per station per region
    seen = {}
    for r in results:
        key = (r["name"], r["region"])
        if key not in seen or seen[key]["mm"] < r["mm"]:
            seen[key] = r

    return date_label, list(seen.values()), unmatched


def _resolve_station(name_raw, lookup, mm, region_name, unmatched, prompted_this_run, interactive, note=None):
    station = find_station(name_raw, lookup)
    if station:
        return {"name": station["name"], "lat": station["lat"], "lon": station["lon"],
                "mm": mm, "region": region_name, "note": note}

    key = normalize_name(name_raw)
    if key in prompted_this_run:
        added = prompted_this_run[key]
        if added is None:
            unmatched.append({"name": name_raw, "mm": mm, "region": region_name})
            return None
        return {"name": added["name"], "lat": added["lat"], "lon": added["lon"],
                "mm": mm, "region": region_name, "note": note}

    if interactive:
        added = _prompt_for_station(name_raw, mm, region_name)
        prompted_this_run[key] = added
        if added:
            lookup.append(added)
            save_custom_station(added)
            return {"name": added["name"], "lat": added["lat"], "lon": added["lon"],
                    "mm": mm, "region": region_name, "note": note}

    prompted_this_run[key] = None
    unmatched.append({"name": name_raw, "mm": mm, "region": region_name})
    return None


def _prompt_for_station(name_raw, mm, region_name):
    print(f"\n[unresolved station] '{name_raw}' ({region_name}, {mm}mm) is not in the station lookup.")
    resp = input("  Enter 'lat,lon' to add it (or press Enter to skip): ").strip()
    if not resp:
        return None
    try:
        lat_str, lon_str = [p.strip() for p in resp.split(",", 1)]
        lat, lon = float(lat_str), float(lon_str)
    except (ValueError, IndexError):
        print("  Couldn't parse that as 'lat,lon' — skipping.")
        return None
    return {"name": name_raw.strip(), "lat": lat, "lon": lon}


# --------------------------------------------------------------------------
# SQLite storage
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    date TEXT PRIMARY KEY,
    label TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (
    date TEXT NOT NULL,
    station TEXT NOT NULL,
    lat REAL,
    lon REAL,
    region TEXT,
    mm REAL NOT NULL,
    note TEXT,
    PRIMARY KEY (date, station),
    FOREIGN KEY (date) REFERENCES reports(date)
);

CREATE TABLE IF NOT EXISTS unresolved_stations (
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    region TEXT,
    mm REAL,
    first_seen TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, name)
);

CREATE INDEX IF NOT EXISTS idx_readings_station ON readings(station);
CREATE INDEX IF NOT EXISTS idx_readings_date ON readings(date);
"""


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def date_already_parsed(conn, iso_date):
    cur = conn.execute("SELECT 1 FROM reports WHERE date = ?", (iso_date,))
    return cur.fetchone() is not None


def upsert_date(conn, iso_date, date_label, stations, unmatched):
    with closing(conn.cursor()) as cur:
        cur.execute(
            "INSERT INTO reports(date, label, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET label=excluded.label, fetched_at=excluded.fetched_at",
            (iso_date, date_label or iso_date, datetime.now(timezone.utc).isoformat()),
        )
        cur.execute("DELETE FROM readings WHERE date = ?", (iso_date,))
        cur.executemany(
            "INSERT INTO readings(date, station, lat, lon, region, mm, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (iso_date, s["name"], s["lat"], s["lon"], s["region"], s["mm"], s.get("note"))
                for s in stations
            ],
        )
        cur.execute("DELETE FROM unresolved_stations WHERE date = ?", (iso_date,))
        if unmatched:
            now = datetime.now(timezone.utc).isoformat()
            cur.executemany(
                "INSERT INTO unresolved_stations(date, name, region, mm, first_seen, resolved) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                [(iso_date, u["name"], u["region"], u["mm"], now) for u in unmatched],
            )
    conn.commit()


def sync_pdfs_to_db(pdf_dir, db_path, logger=None, force=False, interactive=False):
    """Parses every PDF in pdf_dir whose date isn't already in the DB."""
    conn = init_db(db_path)
    lookup = build_lookup()
    updated = []
    
    # Get all PDFs in the directory
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        if logger:
            logger.warning(f"No PDF files found in {pdf_dir}")
        conn.close()
        return updated
    
    if logger:
        logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    try:
        for fname in sorted(pdf_files):
            iso_date = fname[:-4]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", iso_date):
                if logger:
                    logger.warning(f"Skipping {fname}: invalid date format")
                continue
            
            # Skip if already parsed and not forcing
            if not force and date_already_parsed(conn, iso_date):
                if logger:
                    logger.debug(f"Skipping {fname}: already in database")
                continue
            
            pdf_path = os.path.join(pdf_dir, fname)
            try:
                if logger:
                    logger.info(f"Parsing {fname}...")
                
                date_label, stations, unmatched = parse_pdf(pdf_path, lookup=lookup, interactive=interactive)
                upsert_date(conn, iso_date, date_label, stations, unmatched)
                updated.append(iso_date)
                
                if logger:
                    msg = f"✓ Parsed {fname}: {len(stations)} station reading(s)"
                    if unmatched:
                        msg += f", {len(unmatched)} unmatched name(s) saved to unresolved_stations"
                    logger.info(msg)
                    
            except Exception as e:
                if logger:
                    logger.error(f"✗ Failed to parse {fname}: {e}")
                import traceback
                if logger:
                    logger.debug(traceback.format_exc())
                    
    finally:
        conn.close()
    
    return updated


def resolve_unmatched(db_path, pdf_dir, logger=None):
    """Interactive helper for unresolved stations."""
    conn = init_db(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT name, region, mm FROM unresolved_stations WHERE resolved = 0 ORDER BY name"
        ).fetchall()
        if not rows:
            print("No unresolved stations.")
            return
        print(f"{len(rows)} unresolved station name(s) found.\n")
        for name, region, mm in rows:
            added = _prompt_for_station(name, mm, region)
            if added:
                save_custom_station(added)
                conn.execute("UPDATE unresolved_stations SET resolved = 1 WHERE name = ?", (name,))
                conn.commit()
                print(f"  Saved. Re-run with --force to reparse affected dates.")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Parse PMD rainfall PDFs into rainfall.db")
    ap.add_argument("--pdf-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pmd_rainfall_pdfs"))
    ap.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "rainfall.db"))
    ap.add_argument("--force", action="store_true", help="Reparse every PDF, even already-synced dates")
    ap.add_argument("--interactive", action="store_true",
                    help="Prompt for lat/lon of unmatched stations as they're found")
    ap.add_argument("--no-prompt", action="store_true", help="Never prompt, even in a terminal")
    ap.add_argument("--resolve-unmatched", action="store_true",
                    help="Walk unresolved_stations in the DB and prompt for each")
    args = ap.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("pmd_parser")

    if args.resolve_unmatched:
        resolve_unmatched(args.db, args.pdf_dir, logger=log)
        sys.exit(0)

    interactive = args.interactive or (sys.stdin.isatty() and not args.no_prompt)
    updated = sync_pdfs_to_db(args.pdf_dir, args.db, logger=log, force=args.force, interactive=interactive)
    print(f"\n✓ Synced {len(updated)} date(s) into {args.db}")
    
    if updated:
        print(f"  Dates: {', '.join(updated)}")
    else:
        print("  No new dates to process")