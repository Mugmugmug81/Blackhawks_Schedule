import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import pytz
import platform
from io import BytesIO

# --- Custom CSS styling ---
st.markdown(
    """
    <style>
    /* Background */
    .main {
        background-color: #000000;
        color: white;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    /* Title */
    .css-18e3th9 {
        color: #d32f2f;
        font-weight: 700;
        font-size: 2.5rem;
    }
    /* Table header */
    thead tr th {
        background-color: #d32f2f !important;
        color: white !important;
        font-weight: bold;
        text-align: center;
    }
    /* Table rows */
    tbody tr:nth-child(odd) {
        background-color: #1a1a1a !important;
        color: white !important;
    }
    tbody tr:nth-child(even) {
        background-color: #333333 !important;
        color: white !important;
    }
    /* Download button */
    .stDownloadButton>button {
        background-color: #d32f2f;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    .stDownloadButton>button:hover {
        background-color: #b71c1c;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True
)

# Timezone configurations
eastern = pytz.timezone('US/Eastern')
central = pytz.timezone('US/Central')

# OS-specific date formatting
if platform.system() == 'Windows':
    DATE_FORMAT = '%#m/%d/%y'
else:
    DATE_FORMAT = '%-m/%d/%y'

# --- New NHL API Configuration ---
TEAM_ID = 'CHI'
current_year = datetime.now().year
next_year = current_year + 1
CURRENT_SEASON = f"{current_year}{next_year}"
NHL_API_URL = f'https://api-web.nhle.com/v1/club-schedule-season/{TEAM_ID}/{CURRENT_SEASON}'

# --- The Odds API Configuration ---
ODDS_API_KEY = "fe20507336eda30c02f7e8cffd7fad39"
SPORT_KEY = "icehockey_nhl"
REGIONS = "us"
MARKET = "h2h"
ODDS_API_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds?regions={REGIONS}&markets={MARKET}&apiKey={ODDS_API_KEY}"

# Map NHL API team abbreviations to full names for The Odds API
team_map = {
    'ANA': 'Anaheim Ducks', 'ARI': 'Arizona Coyotes', 'BOS': 'Boston Bruins', 'BUF': 'Buffalo Sabres',
    'CAR': 'Carolina Hurricanes', 'CBJ': 'Columbus Blue Jackets', 'CGY': 'Calgary Flames', 'CHI': 'Chicago Blackhawks',
    'COL': 'Colorado Avalanche', 'DAL': 'Dallas Stars', 'DET': 'Detroit Red Wings', 'EDM': 'Edmonton Oilers',
    'FLA': 'Florida Panthers', 'LAK': 'Los Angeles Kings', 'MIN': 'Minnesota Wild', 'MTL': 'Montreal Canadiens',
    'NJD': 'New Jersey Devils', 'NSH': 'Nashville Predators', 'NYI': 'New York Islanders', 'NYR': 'New York Rangers',
    'OTT': 'Ottawa Senators', 'PHI': 'Philadelphia Flyers', 'PIT': 'Pittsburgh Penguins', 'SEA': 'Seattle Kraken',
    'SJS': 'San Jose Sharks', 'STL': 'St. Louis Blues', 'TBL': 'Tampa Bay Lightning', 'TOR': 'Toronto Maple Leafs',
    'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights', 'WPG': 'Winnipeg Jets', 'WSH': 'Washington Capitals'
}

@st.cache_data(ttl=3600)
def get_live_odds():
    """
    Fetches live betting odds for all upcoming NHL games.
    The Odds API returns a list of games, so we'll fetch them once.
    """
    try:
        response = requests.get(ODDS_API_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching odds from API: {e}")
        return None

def find_game_odds(odds_data, home_team_abbrev, away_team_abbrev):
    """
    Parses the odds data to find a specific game's odds.
    """
    if not odds_data:
        return "N/A"

    home_team_full = team_map.get(home_team_abbrev)
    away_team_full = team_map.get(away_team_abbrev)

    if not home_team_full or not away_team_full:
        return "N/A"

    for game in odds_data:
        if (game['home_team'] == home_team_full and game['away_team'] == away_team_full) or \
           (game['away_team'] == home_team_full and game['home_team'] == away_team_full):
            
            for bookmaker in game['bookmakers']:
                if bookmaker['key'] == 'draftkings':
                    for market in bookmaker['markets']:
                        if market['key'] == MARKET:
                            try:
                                home_odds = next(outcome['price'] for outcome in market['outcomes'] if outcome['name'] == home_team_full)
                                away_odds = next(outcome['price'] for outcome in market['outcomes'] if outcome['name'] == away_team_full)
                                return f"{home_team_full}: {home_odds} | {away_team_full}: {away_odds}"
                            except StopIteration:
                                return "Odds not available"
    return "N/A"

@st.cache_data(ttl=3600)
def fetch_full_schedule():
    """Fetches full Blackhawks schedule from the new NHL API."""
    try:
        # Fetch odds data first, so we don't call the API in a loop
        odds_data = get_live_odds()

        response = requests.get(NHL_API_URL)
        response.raise_for_status()
        schedule_data = response.json()
        
        games = []
        for game in schedule_data['games']:
            game_date_time_utc = datetime.fromisoformat(game['gameDate']).replace(tzinfo=pytz.utc)
            game_date_time_central = game_date_time_utc.astimezone(central)

            is_home_game = game['homeTeam']['abbrev'] == TEAM_ID
            opponent_abbrev = game['awayTeam']['abbrev'] if is_home_game else game['homeTeam']['abbrev']
            opponent = f'vs. {opponent_abbrev}' if is_home_game else f'@ {opponent_abbrev}'
            
            if game['gameState'] == 'FINAL':
                home_score = game['homeTeam']['score']
                away_score = game['awayTeam']['score']
                
                if is_home_game:
                    result = "Win" if home_score > away_score else "Loss"
                    score_str = f"{home_score}-{away_score} ({result})"
                else:
                    result = "Win" if away_score > home_score else "Loss"
                    score_str = f"{away_score}-{home_score} ({result})"

                games.append({
                    'Date': game_date_time_central.strftime(DATE_FORMAT),
                    'Start Time (CST/CDT)': game_date_time_central.strftime('%I:%M %p'),
                    'Opponent': opponent,
                    'Result': score_str,
                    'Odds': 'N/A'
                })

            else:
                home_team_abbrev = game['homeTeam']['abbrev']
                away_team_abbrev = game['awayTeam']['abbrev']
                odds = find_game_odds(odds_data, home_team_abbrev, away_team_abbrev)

                games.append({
                    'Date': game_date_time_central.strftime(DATE_FORMAT),
                    'Start Time (CST/CDT)': game_date_time_central.strftime('%I:%M %p'),
                    'Opponent': opponent,
                    'Result': 'Scheduled',
                    'Odds': odds
                })

        return pd.DataFrame(games)

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from NHL API: {e}")
        return pd.DataFrame()

def to_excel(df):
    """Converts a DataFrame to an Excel file in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Schedule')
    processed_data = output.getvalue()
    return processed_data

# Streamlit App
st.title(f"Chicago Blackhawks Complete Schedule {current_year}-{next_year}")

with st.spinner("Fetching schedule data..."):
    df_schedule = fetch_full_schedule()

if df_schedule.empty:
    st.write("No schedule data found.")
else:
    st.dataframe(df_schedule)

    excel_filename = f'blackhawks_schedule_{CURRENT_SEASON[:4]}-{CURRENT_SEASON[4:]}.xlsx'
    excel_data = to_excel(df_schedule)
    st.download_button(
        label="Download schedule",
        data=excel_data,
        file_name=excel_filename,
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )