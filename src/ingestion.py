import pandas as pd
import requests
import pybaseball
from pybaseball import statcast_batter, playerid_lookup
from datetime import datetime, timedelta
from src.config import BALLDONTLIE_KEY

# Enable pybaseball cache to prevent server timeout crashes
pybaseball.cache.enable()

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
    """Fetches daily max temperature and wind vectors via Open-Meteo free API."""
    # Added wind_speed and wind_direction to the API request
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,wind_speed_10m_max,wind_direction_10m_dominant&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto&forecast_days=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            daily = data.get('daily', {})
            
            # Extract the 3 metrics safely
            max_temp = float(daily.get('temperature_2m_max', [72.0])[0])
            wind_spd = float(daily.get('wind_speed_10m_max', [0.0])[0])
            wind_dir = float(daily.get('wind_direction_10m_dominant', [0.0])[0])
            
            return max_temp, wind_spd, wind_dir
    except Exception as e:
        print(f"Weather fetch failed: {e}")
    
    return 72.0, 0.0, 0.0 # League average defaults if API fails