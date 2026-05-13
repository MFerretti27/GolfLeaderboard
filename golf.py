import requests  # type: ignore[import]
from datetime import datetime
from pathlib import Path
import re

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
CORE_EVENT_URL = "https://sports.core.api.espn.com/v2/sports/golf/leagues/pga/events/{event_id}"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Round stat indices from ESPN's statistics categories
# Order: birdies, eagles, double_bogeys, bogeys, other, pars
ROUND_STAT_NAMES = ["Birdies", "Eagles", "Dbl Bogeys", "Bogeys", "Other", "Pars"]
EVENT_DETAILS_CACHE = {}
WEATHER_CACHE = {}
TOURNAMENT_IMAGE_DIR = Path(__file__).resolve().parent / "tournament_images"

WEATHER_CODE_DESCRIPTIONS = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Heavy rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm + hail",
    99: "Heavy thunderstorm + hail",
}


def fetch_scoreboard():
    """Fetch current PGA scoreboard JSON from ESPN."""
    response = requests.get(SCOREBOARD_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_event_details(event_id):
    """Fetch richer event metadata from ESPN's core API and cache it."""
    if not event_id:
        return {}
    if event_id in EVENT_DETAILS_CACHE:
        return EVENT_DETAILS_CACHE[event_id]

    try:
        response = requests.get(CORE_EVENT_URL.format(event_id=event_id), timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        data = {}

    EVENT_DETAILS_CACHE[event_id] = data
    return data


def get_location_weather(location_text):
    """Return current weather text for a location using free Open-Meteo APIs."""
    query = str(location_text or "").strip()
    if not query or query == "N/A":
        return "N/A"

    if query in WEATHER_CACHE:
        return WEATHER_CACHE[query]

    query_variants = [query]
    if "," in query:
        city_only = query.split(",", 1)[0].strip()
        if city_only and city_only not in query_variants:
            query_variants.append(city_only)

    weather_text = "N/A"
    try:
        latitude = None
        longitude = None
        for candidate in query_variants:
            geo_response = requests.get(
                GEOCODING_URL,
                params={"name": candidate, "count": 1, "language": "en", "format": "json"},
                timeout=10,
            )
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            results = geo_data.get("results", [])
            if results:
                first = results[0]
                latitude = first.get("latitude")
                longitude = first.get("longitude")
                if latitude is not None and longitude is not None:
                    break

        if latitude is not None and longitude is not None:
            weather_response = requests.get(
                WEATHER_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "temperature_unit": "fahrenheit",
                    "wind_speed_unit": "mph",
                },
                timeout=10,
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()
            current = weather_data.get("current", {})
            temperature = current.get("temperature_2m")
            feels_like = current.get("apparent_temperature")
            wind_mph = current.get("wind_speed_10m")
            weather_code = current.get("weather_code")

            conditions = WEATHER_CODE_DESCRIPTIONS.get(weather_code, "Current conditions")
            parts = [conditions]
            if temperature is not None:
                parts.append(f"{round(float(temperature))}F")
            if feels_like is not None:
                parts.append(f"Feels {round(float(feels_like))}F")
            if wind_mph is not None:
                parts.append(f"Wind {round(float(wind_mph))} mph")

            weather_text = " | ".join(parts)
    except (requests.RequestException, ValueError, TypeError):
        weather_text = "N/A"

    WEATHER_CACHE[query] = weather_text
    return weather_text


def is_live_event(event):
    """Return True when the tournament is currently in progress."""
    status_type = event.get("status", {}).get("type", {})
    state = str(status_type.get("state", "")).lower()
    description = str(status_type.get("description", "")).lower()
    return state == "in" or "in progress" in description


def get_live_events():
    """Fetch and return only live events."""
    data = fetch_scoreboard()
    return [event for event in data.get("events", []) if is_live_event(event)]


def get_preferred_events():
    """Return live events when available, otherwise fall back to all events."""
    data = fetch_scoreboard()
    events = data.get("events", [])
    live_events = [event for event in events if is_live_event(event)]
    return live_events if live_events else events


def safe_int(value, default=9999):
    """Convert a value to int safely for sorting/position fields."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_day_ordinal(day):
    """Return a day number with its ordinal suffix."""
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_date_range(start_date, end_date):
    """Format a tournament date range in a readable style."""
    try:
        start = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")
        end = datetime.strptime(str(end_date)[:10], "%Y-%m-%d")
    except ValueError:
        return f"{str(start_date)[:10]} -> {str(end_date)[:10]}"

    start_month = start.strftime("%B")
    end_month = end.strftime("%B")
    start_day = get_day_ordinal(start.day)
    end_day = get_day_ordinal(end.day)

    if start.year == end.year and start.month == end.month:
        return f"{start_month} {start_day} - {end_day}, {start.year}"
    if start.year == end.year:
        return f"{start_month} {start_day} - {end_month} {end_day}, {start.year}"
    return f"{start_month} {start_day}, {start.year} - {end_month} {end_day}, {end.year}"


def get_round_score(competitor, round_number):
    """Return the display score for a given round (1-indexed), or '-' if not played."""
    for ls in competitor.get("linescores", []):
        if ls.get("period") == round_number:
            return ls.get("displayValue", "-")
    return "-"


def get_round_stats(competitor, round_number):
    """Return a dict of round statistics (birdies, pars, bogeys, etc.) for a given round."""
    for ls in competitor.get("linescores", []):
        if ls.get("period") == round_number:
            stats_list = (
                ls.get("statistics", {})
                .get("categories", [{}])[0]
                .get("stats", [])
            )
            result = {}
            for i, name in enumerate(ROUND_STAT_NAMES):
                if i < len(stats_list):
                    result[name] = stats_list[i].get("displayValue", "-")
            return result
    return {}


def format_score(score):
    """Format a score string: prefix + if positive, leave as-is otherwise."""
    try:
        val = int(score)
        if val > 0:
            return f"+{val}"
        return str(val)
    except (ValueError, TypeError):
        return score or "E"


def get_max_rounds(competitors):
    """Determine the highest round that has been played so far."""
    max_round = 0
    for competitor in competitors:
        for linescore in competitor.get("linescores", []):
            period = linescore.get("period", 0)
            if isinstance(period, int) and 1 <= period <= 4:
                max_round = max(max_round, period)
    return max_round


def get_current_round_linescore(competitor):
    """Return the most relevant round linescore for a live event."""
    latest = None
    for linescore in competitor.get("linescores", []):
        if not isinstance(linescore.get("period"), int):
            continue
        if not linescore.get("linescores"):
            continue
        if latest is None or linescore.get("period", 0) > latest.get("period", 0):
            latest = linescore
    return latest


def get_hole_display_value(hole):
    """Return the score display for a hole, preferring relative score."""
    score_type = hole.get("scoreType", {}).get("displayValue")
    if score_type not in (None, ""):
        return score_type
    display_value = hole.get("displayValue")
    if display_value in (None, ""):
        return "-"
    return str(display_value)


def get_current_round_number(competition):
    """Find the highest round number that currently has hole-by-hole data."""
    current_round = 0
    for competitor in competition.get("competitors", []):
        for linescore in competitor.get("linescores", []):
            period = linescore.get("period", 0)
            if isinstance(period, int) and linescore.get("linescores"):
                current_round = max(current_round, period)
    return current_round


def get_status_text(event, competition):
    """Return the best available status description and detail text."""
    event_status_type = event.get("status", {}).get("type", {})
    competition_status_type = competition.get("status", {}).get("type", {})

    status_desc = (
        competition_status_type.get("description")
        or event_status_type.get("description")
        or ""
    )
    status_detail = (
        competition_status_type.get("shortDetail")
        or competition_status_type.get("detail")
        or event_status_type.get("shortDetail")
        or event_status_type.get("detail")
        or ""
    )
    return status_desc, status_detail


def format_status_line(status_desc, status_detail):
    """Format status text, omitting redundant detail when it adds no value."""
    desc = str(status_desc or "").strip()
    detail = str(status_detail or "").strip()

    if not detail:
        return f"Status: {desc}"

    if detail.lower() in {desc.lower(), "complete"}:
        return f"Status: {desc}"

    return f"Status: {desc}  |  {detail}"


def get_event_metadata(event):
    """Return course, location, weather text, and local logo path for an event."""
    details = fetch_event_details(event.get("id"))
    courses = details.get("courses", []) if isinstance(details, dict) else []

    course_name = "N/A"
    location_text = "N/A"
    if courses:
        course = courses[0]
        course_name = course.get("name") or "N/A"
        address = course.get("address", {})
        city = address.get("city")
        state = address.get("state") or address.get("country")
        if city and state:
            location_text = f"{city}, {state}"
        elif city:
            location_text = city
        elif state:
            location_text = state

    logo_path = ""
    if TOURNAMENT_IMAGE_DIR.exists() and TOURNAMENT_IMAGE_DIR.is_dir():
        event_id = str(event.get("id", "")).strip()
        name = str(event.get("name", "")).strip()
        short_name = str(event.get("shortName", "")).strip()
        slug_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        slug_short_name = re.sub(r"[^a-z0-9]+", "_", short_name.lower()).strip("_")

        candidates = []
        for base in (event_id, short_name, name, slug_short_name, slug_name):
            if not base:
                continue
            for ext in ("png", "jpg", "jpeg", "webp", "gif"):
                candidates.append(TOURNAMENT_IMAGE_DIR / f"{base}.{ext}")

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                logo_path = str(candidate)
                break

    weather_text = get_location_weather(location_text)
    return course_name, location_text, weather_text, logo_path


def get_tournament_presentation_data(event, top_n=None):
    """Return structured metadata, headers, and rows for GUI rendering."""
    competition = event.get("competitions", [{}])[0]
    status_desc, status_detail = get_status_text(event, competition)
    course_name, location_text, weather_text, logo_path = get_event_metadata(event)

    competitors = sorted(
        competition.get("competitors", []),
        key=lambda competitor: safe_int(competitor.get("order")),
    )
    if top_n is not None:
        competitors = competitors[:top_n]

    metadata = {
        "title": event.get("shortName", event.get("name", "Tournament")),
        "date_range": format_date_range(event.get("date", ""), event.get("endDate", "")),
        "status": format_status_line(status_desc, status_detail),
        "course": course_name,
        "location": location_text,
        "weather": weather_text,
        "logo_path": logo_path,
        "broadcast": competition.get("broadcast", ""),
        "is_live": is_live_event(event),
        "today": "",
    }

    if metadata["is_live"]:
        current_round = get_current_round_number(competition)
        if current_round:
            metadata["today"] = f"Round {current_round}"

        hole_count = 18
        for competitor in competitors:
            round_linescore = get_current_round_linescore(competitor)
            if round_linescore and round_linescore.get("linescores"):
                hole_count = max(hole_count, len(round_linescore.get("linescores", [])))
        hole_count = min(hole_count, 18)

        headers = ["Pos", "Player", "Tot", "Today"] + [str(hole) for hole in range(1, hole_count + 1)]
        rows = []
        for competitor in competitors:
            athlete = competitor.get("athlete", {})
            round_linescore = get_current_round_linescore(competitor)
            today_score = "-"
            hole_values = ["-"] * hole_count
            if round_linescore:
                today_score = round_linescore.get("displayValue", "-")
                for idx, hole in enumerate(round_linescore.get("linescores", [])[:hole_count]):
                    hole_values[idx] = get_hole_display_value(hole)

            rows.append([
                str(safe_int(competitor.get("order"), default=0) or "?"),
                athlete.get("shortName", athlete.get("displayName", "Unknown")),
                format_score(competitor.get("score", "E")),
                today_score,
                *hole_values,
            ])
        return metadata, headers, rows

    max_rounds = get_max_rounds(competitors)
    headers = ["Pos", "Player", "Ctry", "Tot"] + [f"R{round_number}" for round_number in range(1, max_rounds + 1)]
    rows = []
    for competitor in competitors:
        athlete = competitor.get("athlete", {})
        rows.append([
            str(safe_int(competitor.get("order"), default=0) or "?"),
            athlete.get("shortName", athlete.get("displayName", "Unknown")),
            str(athlete.get("flag", {}).get("alt", ""))[:4],
            format_score(competitor.get("score", "E")),
            *[get_round_score(competitor, round_number) for round_number in range(1, max_rounds + 1)],
        ])
    return metadata, headers, rows


def build_tournament_text(event, top_n=None):
    """Build full leaderboard text for one tournament event."""
    name = event.get("name", "Unknown Tournament")
    date_range = format_date_range(event.get("date", ""), event.get("endDate", ""))

    competition = event.get("competitions", [{}])[0]
    status_desc, status_detail = get_status_text(event, competition)
    broadcast = competition.get("broadcast", "")
    course_name, location_text, weather_text, _ = get_event_metadata(event)

    competitors = sorted(
        competition.get("competitors", []),
        key=lambda competitor: safe_int(competitor.get("order")),
    )
    if top_n is not None:
        competitors = competitors[:top_n]
    max_rounds = get_max_rounds(competitors)

    lines = []
    lines.append("=" * 62)
    lines.append(f"  {name}")
    lines.append(f"  Dates : {date_range}")
    lines.append(f"  {format_status_line(status_desc, status_detail)}")
    lines.append(f"  Course: {course_name}")
    lines.append(f"  Location : {location_text}")
    if broadcast:
        lines.append(f"  TV    : {broadcast}")
    lines.append("=" * 62)

    if not competitors:
        lines.append("  No competitor data available.")
        return "\n".join(lines)

    round_cols = "".join(f"  R{round_number}" for round_number in range(1, max_rounds + 1))
    header_label = "Pos"
    if top_n is not None:
        header_label = f"Pos(T{top_n})"
    lines.append(f"  {header_label:>8}  {'Player':<22}  {'Ctry':<4}  {'Tot':>4}{round_cols}")
    lines.append("-" * 62)

    for competitor in competitors:
        athlete = competitor.get("athlete", {})
        player_name = athlete.get("shortName", athlete.get("displayName", "Unknown"))
        country = str(athlete.get("flag", {}).get("alt", ""))[:4]

        total_score = format_score(competitor.get("score", "E"))
        position = safe_int(competitor.get("order"), default=0)
        position_display = str(position) if position > 0 else "?"

        round_scores = "".join(
            f"  {get_round_score(competitor, round_number):>2}"
            for round_number in range(1, max_rounds + 1)
        )

        lines.append(
            f"  {position_display:>8}  {str(player_name):<22}  {country:<4}  {total_score:>4}{round_scores}"
        )

    return "\n".join(lines)


def build_live_tournament_text(event, top_n=None):
    """Build a live leaderboard with today's hole-by-hole scores."""
    name = event.get("name", "Unknown Tournament")
    date_range = format_date_range(event.get("date", ""), event.get("endDate", ""))

    competition = event.get("competitions", [{}])[0]
    status_desc, status_detail = get_status_text(event, competition)
    broadcast = competition.get("broadcast", "")
    course_name, location_text, weather_text, _ = get_event_metadata(event)

    competitors = sorted(
        competition.get("competitors", []),
        key=lambda competitor: safe_int(competitor.get("order")),
    )
    if top_n is not None:
        competitors = competitors[:top_n]

    current_round = get_current_round_number(competition)

    lines = []
    lines.append("=" * 62)
    lines.append(f"  {name}")
    lines.append(f"  Dates : {date_range}")
    lines.append(f"  {format_status_line(status_desc, status_detail)}")
    lines.append(f"  Course: {course_name}")
    lines.append(f"  Place : {location_text}")
    lines.append(f"  Weather: {weather_text}")
    if broadcast:
        lines.append(f"  TV    : {broadcast}")
    if current_round:
        lines.append(f"  Today : Round {current_round}")
    lines.append("=" * 62)

    if not competitors:
        lines.append("  No competitor data available.")
        return "\n".join(lines)

    hole_count = 18
    for competitor in competitors:
        round_linescore = None
        if current_round:
            for linescore in competitor.get("linescores", []):
                if linescore.get("period") == current_round:
                    round_linescore = linescore
                    break
        if round_linescore and round_linescore.get("linescores"):
            hole_count = max(hole_count, len(round_linescore.get("linescores", [])))

    hole_count = min(hole_count, 18)
    hole_headers = "".join(f" {hole:>2}" for hole in range(1, hole_count + 1))
    lines.append(f"  {'Pos':>4}  {'Player':<20}  {'Tot':>4}  {'Today':>5}{hole_headers}")
    lines.append("-" * 62)

    for competitor in competitors:
        athlete = competitor.get("athlete", {})
        player_name = athlete.get("shortName", athlete.get("displayName", "Unknown"))
        total_score = format_score(competitor.get("score", "E"))
        position = safe_int(competitor.get("order"), default=0)
        position_display = str(position) if position > 0 else "?"

        today_score = "-"
        hole_values = ["-"] * hole_count
        round_linescore = get_current_round_linescore(competitor)
        if round_linescore:
            today_score = round_linescore.get("displayValue", "-")
            holes = round_linescore.get("linescores", [])
            for idx, hole in enumerate(holes[:hole_count]):
                hole_values[idx] = get_hole_display_value(hole)

        lines.append(
            f"  {position_display:>4}  {str(player_name):<20}  {total_score:>4}  {today_score:>5}{''.join(f' {value:>2}' for value in hole_values)}"
        )

    return "\n".join(lines)


def print_tournament_leaderboard(event):
    """Print the full leaderboard for a tournament event."""
    print(build_tournament_text(event))
    print()


def print_round_stats_summary(event, top_n=10):
    """Print round-by-round stats for the top N players."""
    competition = event.get("competitions", [{}])[0]
    competitors = sorted(
        competition.get("competitors", []),
        key=lambda c: int(c.get("order", 9999)),
    )[:top_n]

    if not competitors:
        return

    max_rounds = 0
    for comp in competitors:
        for ls in comp.get("linescores", []):
            p = ls.get("period", 0)
            if isinstance(p, int) and p < 5:
                max_rounds = max(max_rounds, p)

    print(f"  --- Round Stats (Top {top_n}) ---")

    for comp in competitors:
        athlete = comp.get("athlete", {})
        name = athlete.get("shortName", athlete.get("displayName", "?"))
        pos = comp.get("order", "?")
        print(f"\n  #{pos} {name}")
        for r in range(1, max_rounds + 1):
            stats = get_round_stats(comp, r)
            if stats:
                parts = "  ".join(f"{k}: {v}" for k, v in stats.items())
                score = get_round_score(comp, r)
                print(f"    R{r} ({score:>3}):  {parts}")

    print()


def main():
    res = fetch_scoreboard()

    events = res.get("events", [])
    season_year = res.get("season", {}).get("year", "")
    league_name = res.get("leagues", [{}])[0].get("name", "PGA TOUR")

    print(f"\n{league_name}  |  Season {season_year}")
    print(f"Active Tournaments: {len(events)}\n")

    for event in events:
        print_tournament_leaderboard(event)
        print_round_stats_summary(event, top_n=10)


if __name__ == "__main__":
    main()
