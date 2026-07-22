"""
pmd_rainfall_parser.py

Parses a single PMD Daily Rainfall Report PDF into structured station
readings, and stores them date-by-date in a SQLite database (rainfall.db).

This is a server-side Python port of the parsing logic already used by the
dashboard's client-side pdf.js code, so a station/value extracted here will
match what the dashboard would have computed by parsing the same PDF in the
browser. The port mirrors, on purpose:
  - column splitting by x-position (Stations column vs Rainfall(mm) column)
  - region header detection (SINDH, PUNJAB, etc.)
  - "Trace" -> 1mm, "NIL" -> 0mm
  - grouped sub-station breakdowns (e.g. "Sialkot Airport 95, City 44")
    collapsing to ONE reading for the primary station, using the MAXIMUM
    value in the group
  - multiple station names sharing one simple value on a row
  - stopping at the first non-rainfall section (Maximum Wind Reported,
    Water Level, Flood Situation, etc.)

Real PMD PDFs occasionally contain messy free-text asides (e.g. a WASA
sub-station breakdown wrapped across several lines with no clean column
alignment). The heuristics below handle the vast majority of rows cleanly;
a few odd lines may fail to match any known station and are silently
skipped (recorded in `unmatched` for logging only) — the same behavior as
the existing browser-side parser on the same PDFs.
"""

import json
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import pdfplumber

# --------------------------------------------------------------------------
# Station lookup — kept in sync with STATIONS_LOOKUP in the dashboard HTML.
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
    {"name": "Mandi Bahauddin", "lat": 32.9667, "lon": 73.8},
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

SIMPLE_VALUE_RE = re.compile(r"^\(?\s*(\d{1,3}(?:\.\d+)?|Trace|NIL)\s*\)?$", re.I)
SUB_PAIR_RE = re.compile(r"([A-Za-z][A-Za-z .'/\-]*?)\s+(\d{1,3}(?:\.\d+)?|Trace|NIL)\b", re.I)
LEAD_VALUE_RE = re.compile(r"^(\d{1,3}(?:\.\d+)?|Trace|NIL)\b", re.I)
STOP_RE = re.compile(
    r"Maximum\s+Wind|Wind\s*\(\s*KT\s*\)|Water\s+Level|Nullah\s+Lai|Flood\s+Situation", re.I
)
DATE_RE = re.compile(r"(\d{2}-\d{2}-\d{4})")


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


def normalize_name(s):
    s = s.lower()
    s = re.sub(r"[().&']", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_station(raw_name):
    n = normalize_name(raw_name)
    if not n:
        return None
    for s in STATIONS_LOOKUP:
        if normalize_name(s["name"]) == n:
            return s
    for s in STATIONS_LOOKUP:
        sn = normalize_name(s["name"])
        if sn and (sn in n or n in sn):
            return s
    return None


def extract_lines(pdf_path):
    """Groups words into visual text lines using x/y position, mirroring
    the pdf.js-based line grouping the dashboard does in the browser."""
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


def find_column_split_x(lines):
    for line in lines:
        text = " ".join(w["text"] for w in line["items"])
        if re.search(r"Stations", text, re.I) and re.search(r"Rainfall", text, re.I):
            for w in line["items"]:
                if re.search(r"Rainfall", w["text"], re.I):
                    return w["x0"] - 10  # slightly wider buffer than the
                    # browser parser's -5 to absorb the sub-label jitter
                    # seen on real PDFs (e.g. "Airport"/"ZP" landing a few
                    # px left of the header's x-position on some rows).
    return 300


def parse_pdf(pdf_path):
    """Returns (date_label, stations, unmatched) — same shape as the
    dashboard's client-side parseBulletin()."""
    lines = extract_lines(pdf_path)
    full_text = "\n".join(" ".join(w["text"] for w in l["items"]) for l in lines)
    dm = DATE_RE.search(full_text)
    date_label = dm.group(1) if dm else None

    split_x = find_column_split_x(lines)

    rows = []
    current_region = "Unspecified"
    saw_region = False
    for line in lines:
        text = " ".join(w["text"] for w in line["items"])
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        upper = text.upper()
        if upper in REGION_HEADERS:
            current_region = upper
            saw_region = True
            continue
        if not saw_region:
            continue
        if re.match(r"^Stations\s+Rainfall", text, re.I):
            continue
        if STOP_RE.search(text):
            break

        station = " ".join(w["text"] for w in line["items"] if w["x0"] < split_x)
        station = re.sub(r"\s+", " ", station).strip()
        value = " ".join(w["text"] for w in line["items"] if w["x0"] >= split_x)
        value = re.sub(r"\s+", " ", value).strip()
        if not station and not value:
            continue

        if not station and value and rows:
            rows[-1]["value"] += " " + value
        elif station:
            rows.append({"region": current_region, "station": station, "value": value})

    results = []
    unmatched = []

    for row in rows:
        region_name = row["region"].title()
        value_text = row["value"].strip()
        station_text = row["station"].strip()
        if not station_text:
            continue

        looks_like_list = bool(re.search(r",| and ", station_text, re.I))
        if looks_like_list and SIMPLE_VALUE_RE.match(value_text):
            mm = token_to_mm(re.sub(r"[()]", "", value_text).strip())
            if mm is None:
                continue
            for name_raw in re.split(r",| and ", station_text, flags=re.I):
                name_raw = name_raw.strip()
                if not name_raw:
                    continue
                station = find_station(name_raw)
                if station:
                    results.append({"name": station["name"], "lat": station["lat"],
                                     "lon": station["lon"], "mm": mm, "region": region_name,
                                     "note": None})
                else:
                    unmatched.append({"name": name_raw, "mm": mm, "region": region_name})
            continue

        sub_pairs = []
        for m in SUB_PAIR_RE.finditer(value_text):
            v = token_to_mm(m.group(2))
            if v is not None:
                sub_pairs.append(v)

        mm = None
        note = None
        if sub_pairs:
            mm = max(sub_pairs)
            if len(sub_pairs) > 1:
                note = value_text
        elif SIMPLE_VALUE_RE.match(value_text):
            mm = token_to_mm(re.sub(r"[()]", "", value_text).strip())
        else:
            lead = LEAD_VALUE_RE.match(value_text)
            if lead:
                mm = token_to_mm(lead.group(1))

        if mm is None:
            continue

        station = find_station(station_text)
        if station:
            results.append({"name": station["name"], "lat": station["lat"],
                             "lon": station["lon"], "mm": mm, "region": region_name,
                             "note": note})
        else:
            unmatched.append({"name": station_text, "mm": mm, "region": region_name})

    # One reading per station per region — keep the max if a station repeats.
    seen = {}
    for r in results:
        key = (r["name"], r["region"])
        if key not in seen or seen[key]["mm"] < r["mm"]:
            seen[key] = r

    return date_label, list(seen.values()), unmatched


# --------------------------------------------------------------------------
# SQLite storage
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    date TEXT PRIMARY KEY,      -- ISO date, e.g. '2026-07-22' (matches the PDF filename)
    label TEXT,                 -- date label extracted from the PDF text (e.g. '22-07-2026')
    fetched_at TEXT NOT NULL    -- UTC timestamp this row was parsed/inserted
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


def upsert_date(conn, iso_date, date_label, stations):
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
    conn.commit()


def sync_pdfs_to_db(pdf_dir, db_path, logger=None, force=False):
    """Parses every PDF in pdf_dir whose date isn't already in the DB (or
    all of them if force=True) and upserts the results. Returns the list
    of ISO dates that were (re)parsed."""
    conn = init_db(db_path)
    updated = []
    try:
        for fname in sorted(os.listdir(pdf_dir)):
            if not fname.lower().endswith(".pdf"):
                continue
            iso_date = fname[:-4]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", iso_date):
                continue
            if not force and date_already_parsed(conn, iso_date):
                continue
            pdf_path = os.path.join(pdf_dir, fname)
            try:
                date_label, stations, unmatched = parse_pdf(pdf_path)
                upsert_date(conn, iso_date, date_label, stations)
                updated.append(iso_date)
                if logger:
                    msg = f"Parsed {fname}: {len(stations)} station reading(s)"
                    if unmatched:
                        msg += f", {len(unmatched)} unmatched name(s) skipped"
                    logger.info(msg)
            except Exception as e:  # noqa: BLE001 - one bad PDF shouldn't kill the run
                if logger:
                    logger.error(f"Failed to parse {fname}: {e}")
    finally:
        conn.close()
    return updated


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Parse PMD rainfall PDFs into rainfall.db")
    ap.add_argument("--pdf-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "pmd_rainfall_pdfs"))
    ap.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "rainfall.db"))
    ap.add_argument("--force", action="store_true", help="Reparse every PDF, even already-synced dates")
    args = ap.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("pmd_parser")

    updated = sync_pdfs_to_db(args.pdf_dir, args.db, logger=log, force=args.force)
    print(f"\nSynced {len(updated)} date(s) into {args.db}")
