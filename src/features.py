import duckdb
import pandas as pd
from pybaseball import playerid_reverse_lookup

def engineer_features(statcast_df):
    """Uses DuckDB to generate clean rolling averages using fuzzy SQL matching."""
    conn = duckdb.connect(':memory:')
    conn.register('statcast', statcast_df)
    
    query = """
    SELECT 
        batter,
        COUNT(*) as total_pitches,
        AVG(launch_speed) as avg_exit_velo,
        AVG(estimated_woba_using_speedangle) as xwoba,
        SUM(CASE WHEN events LIKE '%single%' OR events LIKE '%double%' OR events LIKE '%triple%' OR events LIKE '%home_run%' THEN 1.0 ELSE 0.0 END) / NULLIF(COUNT(DISTINCT game_pk), 0) as hits_per_game,
        SUM(CASE WHEN events LIKE '%home_run%' THEN 4.0 
                 WHEN events LIKE '%triple%' THEN 3.0 
                 WHEN events LIKE '%double%' THEN 2.0 
                 WHEN events LIKE '%single%' THEN 1.0 
                 ELSE 0.0 END) / NULLIF(COUNT(DISTINCT game_pk), 0) as tb_per_game
    FROM statcast
    WHERE events IS NOT NULL
    GROUP BY batter
    HAVING COUNT(*) > 2
    """
    gold_features = conn.execute(query).fetchdf()
    
    batter_ids = list(gold_features.get('batter', list()))
    if not batter_ids:
        return gold_features
        
    name_map = playerid_reverse_lookup(batter_ids, key_type='mlbam')
    
    first_names = name_map.get('name_first', pd.Series()).fillna("").astype(str).str.capitalize()
    last_names = name_map.get('name_last', pd.Series()).fillna("").astype(str).str.capitalize()
    name_map.insert(0, 'player_name', first_names + " " + last_names)
    
    gold_features = gold_features.merge(name_map, left_on='batter', right_on='key_mlbam', how='inner')
    return gold_features