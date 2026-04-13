import pandas as pd
import requests
from pybaseball import statcast_batter, playerid_lookup
from datetime import datetime, timedelta
from src.config import BALLDONTLIE_KEY

def fetch_recent_statcast(days=14):
    """Fetches pitch-by-pitch data for baseline calculations."""
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    # Fetching aggregate statcast data (simplified for runnable scope)
    from pybaseball import statcast
    df = statcast(start_dt=start_date, end_dt=end_date)
    return df

def fetch_daily_lineups():
    """Fetches confirmed daily lineups using BallDontLie API."""
    url = "https://api.balldontlie.io/v1/lineups"
    headers = {"Authorization": BALLDONTLIE_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('data',)
    return

def fetch_weather_forecast(lat, lon):
    """Fetches hourly weather forecast via Open-Meteo free API.[2]"""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,windspeed_10m"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return {}