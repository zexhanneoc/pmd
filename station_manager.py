"""
station_manager.py - Unified station management system

Handles all station data in one place with:
- Automatic duplicate detection
- Alias management
- Merging of duplicate entries
- Import/export functionality
"""

import json
import os
import re
from difflib import SequenceMatcher

# File paths
STATIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.json")
ALIASES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "station_aliases.json")

# Default stations (built-in)
DEFAULT_STATIONS = [
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

# Default aliases
DEFAULT_ALIASES = {
    "pattan": "pathan kohistan",
    "dera ismail khan": "d i khan",
    "dera ghazi khan": "d g khan",
    "di khan airport": "d i khan",
    "d.i. khan": "d i khan",
    "d i khan": "d i khan",
    "t t singh": "toba tek singh",
    "toba take singh": "toba tek singh",
    "layyah r": "karor(layyah)",
    "r y khan": "rahim yar khan",
    "chaklala": "rawalpindi",
    "chaklala-": "rawalpindi",
    "di khan": "d i khan",
    "dera ismail khan (airport)": "d i khan",
}


def normalize_name(name):
    """Normalize station name for comparison"""
    name = name.lower().strip()
    # Remove common separators and extra spaces
    name = re.sub(r'[\(\)\-_]', ' ', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def similarity_score(name1, name2):
    """Calculate similarity between two names"""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()


def load_stations():
    """Load stations from JSON file, or create with defaults if doesn't exist"""
    if os.path.exists(STATIONS_FILE):
        try:
            with open(STATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # If file is corrupted, recreate from defaults
            save_stations(DEFAULT_STATIONS)
            return DEFAULT_STATIONS
    else:
        # Create file with defaults
        save_stations(DEFAULT_STATIONS)
        return DEFAULT_STATIONS


def save_stations(stations):
    """Save stations to JSON file"""
    # Sort by name for consistency
    stations.sort(key=lambda x: x['name'].lower())
    with open(STATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stations, f, indent=2, ensure_ascii=False)


def load_aliases():
    """Load aliases from JSON file, or create with defaults if doesn't exist"""
    if os.path.exists(ALIASES_FILE):
        try:
            with open(ALIASES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            save_aliases(DEFAULT_ALIASES)
            return DEFAULT_ALIASES
    else:
        save_aliases(DEFAULT_ALIASES)
        return DEFAULT_ALIASES


def save_aliases(aliases):
    """Save aliases to JSON file"""
    # Sort by key for consistency
    sorted_aliases = {k: aliases[k] for k in sorted(aliases.keys())}
    with open(ALIASES_FILE, 'w', encoding='utf-8') as f:
        json.dump(sorted_aliases, f, indent=2, ensure_ascii=False)


def find_station_by_name(name, stations=None, aliases=None):
    """Find station by name, checking aliases first"""
    if stations is None:
        stations = load_stations()
    if aliases is None:
        aliases = load_aliases()
    
    normalized = normalize_name(name)
    
    # Check if this name is an alias
    if normalized in aliases:
        canonical = aliases[normalized]
        # Find the canonical station
        for station in stations:
            if normalize_name(station['name']) == normalize_name(canonical):
                return station
        # If canonical not found, try direct match
        return find_station_by_name(canonical, stations, {})
    
    # Direct match
    for station in stations:
        if normalize_name(station['name']) == normalized:
            return station
    
    # Fuzzy match (threshold 0.85)
    best_match = None
    best_score = 0.85
    for station in stations:
        score = similarity_score(name, station['name'])
        if score > best_score:
            best_score = score
            best_match = station
    
    return best_match


def add_station(name, lat, lon, stations=None, aliases=None):
    """
    Add a new station with duplicate checking.
    Returns: (success, message, station)
    """
    if stations is None:
        stations = load_stations()
    if aliases is None:
        aliases = load_aliases()
    
    normalized_new = normalize_name(name)
    
    # Check if station already exists (exact match)
    for station in stations:
        if normalize_name(station['name']) == normalized_new:
            return False, f"Station '{name}' already exists as '{station['name']}'", station
    
    # Check for similar stations (fuzzy match)
    for station in stations:
        score = similarity_score(name, station['name'])
        if score > 0.9:  # Very similar
            return False, f"Station '{name}' is very similar to '{station['name']}' (similarity: {score:.2%})", station
    
    # Check if this name is already an alias
    if normalized_new in aliases:
        canonical = aliases[normalized_new]
        return False, f"'{name}' is already an alias for '{canonical}'", None
    
    # Check if this is similar to an alias
    for alias, canonical in aliases.items():
        if similarity_score(name, alias) > 0.9:
            return False, f"'{name}' is very similar to alias '{alias}' -> '{canonical}'", None
    
    # Add the new station
    new_station = {"name": name.strip(), "lat": lat, "lon": lon}
    stations.append(new_station)
    save_stations(stations)
    
    return True, f"Added station '{name}' successfully", new_station


def add_alias(alias, canonical, aliases=None):
    """
    Add a new alias mapping.
    Returns: (success, message)
    """
    if aliases is None:
        aliases = load_aliases()
    
    normalized_alias = normalize_name(alias)
    normalized_canonical = normalize_name(canonical)
    
    # Check if alias already exists
    if normalized_alias in aliases:
        return False, f"Alias '{alias}' already maps to '{aliases[normalized_alias]}'"
    
    # Check if alias is a station name
    stations = load_stations()
    for station in stations:
        if normalize_name(station['name']) == normalized_alias:
            return False, f"'{alias}' is already a station name"
    
    # Add the alias
    aliases[normalized_alias] = canonical
    save_aliases(aliases)
    
    return True, f"Added alias '{alias}' -> '{canonical}'"


def merge_duplicates(primary_name, duplicate_names):
    """
    Merge duplicate stations into one.
    All duplicates will be added as aliases to the primary station.
    """
    stations = load_stations()
    aliases = load_aliases()
    
    # Find primary station
    primary = find_station_by_name(primary_name, stations, aliases)
    if not primary:
        return False, f"Primary station '{primary_name}' not found"
    
    results = []
    for dup_name in duplicate_names:
        # Add as alias
        success, msg = add_alias(dup_name, primary['name'], aliases)
        results.append(f"{dup_name}: {msg}")
        
        # Remove if it exists as a station
        stations = [s for s in stations if normalize_name(s['name']) != normalize_name(dup_name)]
    
    save_stations(stations)
    return True, "\n".join(results)


def list_all_stations():
    """Return all stations with their aliases"""
    stations = load_stations()
    aliases = load_aliases()
    
    result = []
    for station in stations:
        station_aliases = [a for a, c in aliases.items() if normalize_name(c) == normalize_name(station['name'])]
        result.append({
            "name": station['name'],
            "lat": station['lat'],
            "lon": station['lon'],
            "aliases": station_aliases
        })
    return result


def export_custom_stations():
    """Export only custom stations (those not in DEFAULT_STATIONS)"""
    stations = load_stations()
    default_names = {normalize_name(s['name']) for s in DEFAULT_STATIONS}
    
    custom = [
        s for s in stations 
        if normalize_name(s['name']) not in default_names
    ]
    
    return custom


# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Station Management System")
    parser.add_argument("--list", action="store_true", help="List all stations")
    parser.add_argument("--list-custom", action="store_true", help="List only custom stations")
    parser.add_argument("--add", nargs=3, metavar=("NAME", "LAT", "LON"), help="Add a new station")
    parser.add_argument("--add-alias", nargs=2, metavar=("ALIAS", "CANONICAL"), help="Add an alias")
    parser.add_argument("--search", metavar="NAME", help="Search for a station")
    parser.add_argument("--export-custom", action="store_true", help="Export custom stations as JSON")
    
    args = parser.parse_args()
    
    if args.list:
        stations = list_all_stations()
        print(f"\nTotal stations: {len(stations)}\n")
        for s in stations:
            print(f"📌 {s['name']} ({s['lat']}, {s['lon']})")
            if s['aliases']:
                print(f"   Aliases: {', '.join(s['aliases'])}")
            print()
    
    elif args.list_custom:
        custom = export_custom_stations()
        print(f"\nCustom stations: {len(custom)}\n")
        print(json.dumps(custom, indent=2))
    
    elif args.add:
        name, lat, lon = args.add[0], float(args.add[1]), float(args.add[2])
        success, msg, station = add_station(name, lat, lon)
        print(f"{'✅' if success else '❌'} {msg}")
        if station:
            print(f"   Added: {station}")
    
    elif args.add_alias:
        alias, canonical = args.add_alias[0], args.add_alias[1]
        success, msg = add_alias(alias, canonical)
        print(f"{'✅' if success else '❌'} {msg}")
    
    elif args.search:
        stations = load_stations()
        aliases = load_aliases()
        result = find_station_by_name(args.search, stations, aliases)
        if result:
            print(f"\n✅ Found: {result['name']} ({result['lat']}, {result['lon']})")
            # Check for aliases
            station_aliases = [a for a, c in aliases.items() if normalize_name(c) == normalize_name(result['name'])]
            if station_aliases:
                print(f"   Aliases: {', '.join(station_aliases)}")
        else:
            print(f"\n❌ No station found matching '{args.search}'")
    
    elif args.export_custom:
        custom = export_custom_stations()
        print(json.dumps(custom, indent=2))
    
    else:
        parser.print_help()