import duckdb
import pandas as pd
from pybaseball import playerid_reverse_lookup

def engineer_batter_splits(statcast_df):
    """Generates batter rolling averages strictly split by Pitcher Handedness (L/R), utilizing a 45-day exponential decay."""
    conn = duckdb.connect(':memory:')
    conn.register('statcast', statcast_df)
    
    query = """
    WITH WeightedData AS (
        SELECT 
            *,
            -- 45-Day Half-Life: Weight drops by 50% every 45 days
            POW(0.5, DATE_DIFF('day', CAST(game_date AS DATE), CURRENT_DATE) / 45.0) AS weight
        FROM statcast
        WHERE events IS NOT NULL AND p_throws IS NOT NULL
    )
    SELECT 
        batter,
        p_throws as split_arm,
        COUNT(*) as total_pitches,
        
        -- Weighted Averages for exit velocity and expected metrics
        SUM(launch_speed * weight) / NULLIF(SUM(weight), 0) as avg_exit_velo,
        SUM(estimated_woba_using_speedangle * weight) / NULLIF(SUM(weight), 0) as xwoba,
        SUM(estimated_ba_using_speedangle * weight) / NULLIF(SUM(weight), 0) as xba,
        
        -- Weighted Per-Game Stats: (Weighted Stat / Weighted PA) * (Total PA / Total Games)
        (SUM(CASE WHEN events IN ('single', 'double', 'triple', 'home_run') THEN 1.0 ELSE 0.0 END * weight) / NULLIF(SUM(weight), 0)) 
        * (COUNT(*) / NULLIF(COUNT(DISTINCT game_pk), 0)) as hits_per_game,
        
        (SUM(CASE WHEN events = 'home_run' THEN 4.0 
                  WHEN events = 'triple' THEN 3.0 
                  WHEN events = 'double' THEN 2.0 
                  WHEN events = 'single' THEN 1.0 
                  ELSE 0.0 END * weight) / NULLIF(SUM(weight), 0)) 
        * (COUNT(*) / NULLIF(COUNT(DISTINCT game_pk), 0)) as tb_per_game

    FROM WeightedData
    GROUP BY batter, p_throws
    HAVING COUNT(*) > 2
    """
    gold_features = conn.execute(query).fetchdf()
    
    return _apply_name_mapping(gold_features, 'batter')


def engineer_pitcher_profiles(statcast_df):
    """Creates a pitcher profile using Expected Metrics from Statcast, utilizing a 45-day exponential decay."""
    conn = duckdb.connect(':memory:')
    conn.register('statcast', statcast_df)

    query = """
    WITH WeightedData AS (
        SELECT 
            *,
            -- 45-Day Half-Life
            POW(0.5, DATE_DIFF('day', CAST(game_date AS DATE), CURRENT_DATE) / 45.0) AS weight
        FROM statcast
        WHERE events IS NOT NULL
    )
    SELECT 
        pitcher,
        MAX(p_throws) as throw_arm,
        
        -- Weighted Averages for expected metrics
        SUM(estimated_ba_using_speedangle * weight) / NULLIF(SUM(weight), 0) as p_xba,
        SUM(estimated_slg_using_speedangle * weight) / NULLIF(SUM(weight), 0) as p_xslg,
        
        -- Weighted Per-Game Stats Allowed
        (SUM(CASE WHEN events IN ('single', 'double', 'triple', 'home_run') THEN 1.0 ELSE 0.0 END * weight) / NULLIF(SUM(weight), 0)) 
        * (COUNT(*) / NULLIF(COUNT(DISTINCT game_pk), 0)) as p_hits_allowed_per_game,
        
        (SUM(CASE WHEN events = 'home_run' THEN 4.0 
                  WHEN events = 'triple' THEN 3.0 
                  WHEN events = 'double' THEN 2.0 
                  WHEN events = 'single' THEN 1.0 
                  ELSE 0.0 END * weight) / NULLIF(SUM(weight), 0)) 
        * (COUNT(*) / NULLIF(COUNT(DISTINCT game_pk), 0)) as p_tb_allowed_per_game

    FROM WeightedData
    GROUP BY pitcher
    HAVING COUNT(*) > 10
    """
    pitcher_features = conn.execute(query).fetchdf()
    
    return _apply_name_mapping(pitcher_features, 'pitcher')


def _apply_name_mapping(df, id_column):
    """Helper function to map MLBAM IDs to full names."""
    player_ids = list(df.get(id_column, list()))
    if not player_ids:
        return df
        
    name_map = playerid_reverse_lookup(player_ids, key_type='mlbam')
    first_names = name_map.get('name_first', pd.Series()).fillna("").astype(str).str.capitalize()
    last_names = name_map.get('name_last', pd.Series()).fillna("").astype(str).str.capitalize()
    name_map.insert(0, 'player_name', first_names + " " + last_names)
    
    return df.merge(name_map, left_on=id_column, right_on='key_mlbam', how='inner')