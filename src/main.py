import os
import json
import statsapi
import pandas as pd
from src.ingestion import fetch_recent_statcast
from src.features import engineer_features
from src.model import generate_predictions, calculate_nbinom_prob
from src.scraper import scrape_sleeper_lines
from src.config import OUTPUT_JSON

LEAGUE_AVG_HIT_RATE = 0.240
LEAGUE_AVG_SLG_RATE = 0.400

def calculate_ev(true_prob, multiplier):
    """Calculates expected value based on Sleeper's dynamic multipliers."""
    if multiplier is None:
        multiplier = 1.0
    ev = (float(true_prob) * float(multiplier)) - 1
    return round(ev, 4)

def normalize_name(name):
    """Removes all punctuation and suffixes for bulletproof matching."""
    if pd.isnull(name) or not name: 
        return "unknown"
    name = str(name).replace(".", "").replace("-", " ").replace("'", "").strip().lower()
    accents = dict(á='a', é='e', í='i', ó='o', ú='u', ñ='n', ã='a', ë='e', ü='u')
    for k, v in accents.items():
        name = name.replace(k, v)
    if "," in name:
        name = " ".join(name.split(", ")[::-1])
    for suffix in list((" jr", " sr", " ii", " iii")):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def fetch_probable_pitchers():
    """Uses MLB-StatsAPI to dynamically fetch today's probable starting pitchers."""
    print("Fetching today's probable pitchers from MLB StatsAPI...")
    pitchers = dict()
    try:
        schedule = statsapi.schedule() 
        for game in schedule:
            home_team = normalize_name(game.get('home_name', ''))
            away_team = normalize_name(game.get('away_name', ''))
            pitchers[home_team] = normalize_name(game.get('away_probable_pitcher', ''))
            pitchers[away_team] = normalize_name(game.get('home_probable_pitcher', ''))
        return pitchers
    except Exception as e:
        print("Notice: Probable pitcher fetch failed - " + str(e))
        return dict()

def fetch_batting_orders():
    """Uses MLB-StatsAPI to fetch today's confirmed batting orders."""
    print("Fetching daily lineups from MLB StatsAPI...")
    lineups = dict()
    try:
        schedule = statsapi.schedule()
        for game in schedule:
            game_id = game.get('game_id')
            if not game_id: continue
            
            box = statsapi.get('game_boxscore', dict(gamePk=game_id))
            for team_side in list(('away', 'home')):
                team_data = box.get('teams', dict()).get(team_side, dict())
                batting_order = team_data.get('battingOrder', list())
                players = team_data.get('players', dict())
                
                for i, p_id in enumerate(batting_order):
                    player_info = players.get('ID' + str(p_id), dict())
                    name = normalize_name(player_info.get('person', dict()).get('fullName', ''))
                    if name:
                        lineups[name] = i + 1  # Records their 1-9 lineup spot
    except Exception as e:
        print("Notice: Lineup fetch failed (games may be too far out) - " + str(e))
    return lineups

def calculate_log5_adjustment(pitcher_rate, league_rate):
    """Calculates a multiplier based on the Log5 ratio of the opposing pitcher."""
    if league_rate <= 0 or pitcher_rate <= 0:
        return 1.0
    return float(pitcher_rate) / float(league_rate)

def run_pipeline():
    print("1. Ingesting Data...")
    statcast_df = fetch_recent_statcast(days=365)
    
    print("2. Engineering Features...")
    features_df = engineer_features(statcast_df)
    
    print("3. Generating Probability Distributions...")
    preds_df = generate_predictions(features_df)
    
    print("4. Scraping Sleeper Market Lines...")
    sleeper_df = scrape_sleeper_lines()
    
    sleeper_df = sleeper_df.fillna(0)
    preds_df = preds_df.fillna(0)
    
    print("5. Applying Phase 2 Matchups & Lineup Volume...")
    probable_pitchers = fetch_probable_pitchers()
    batting_orders = fetch_batting_orders()
    
    try:
        from pybaseball import pitching_stats
        pitcher_df = pitching_stats(2026)
        pitcher_df.insert(0, 'join_name', pitcher_df.get('Name').apply(normalize_name))
    except Exception:
        pitcher_df = pd.DataFrame()
        
    final_opportunities = list()
    matched_count = 0
    
    if not sleeper_df.empty and not preds_df.empty:
        preds_df.insert(0, 'join_name', preds_df.get('player_name').apply(normalize_name))
        
        for _, market in sleeper_df.iterrows():
            market_player = normalize_name(market.get('player_name'))
            
            model_data = None
            for _, row in preds_df.iterrows():
                if row.get('join_name') == market_player:
                    model_data = row.to_dict()
                    break
            
            if model_data is not None:
                matched_count += 1
                
                team_name = normalize_name(market.get('team', ''))
                opponent_pitcher = probable_pitchers.get(team_name, "unknown")
                
                pitcher_hit_allowed = LEAGUE_AVG_HIT_RATE
                pitcher_tb_allowed = LEAGUE_AVG_SLG_RATE
                
                if not pitcher_df.empty and opponent_pitcher!= "unknown":
                    p_match = None
                    for _, prow in pitcher_df.iterrows():
                        if prow.get('join_name') == opponent_pitcher:
                            p_match = prow.to_dict()
                            break
                    
                    if p_match is not None:
                        pitcher_hit_allowed = float(p_match.get('AVG', LEAGUE_AVG_HIT_RATE))
                        pitcher_tb_allowed = float(p_match.get('SLG', LEAGUE_AVG_SLG_RATE))

                hit_adj = calculate_log5_adjustment(pitcher_hit_allowed, LEAGUE_AVG_HIT_RATE)
                tb_adj = calculate_log5_adjustment(pitcher_tb_allowed, LEAGUE_AVG_SLG_RATE)
                
                # Dynamic Lineup Volume Adjuster (Leadoff = +10% PA, 9th = -11% PA)
                lineup_spot = batting_orders.get(market_player, 5)
                expected_pa = 4.63 - ((lineup_spot - 1) * 0.11)
                volume_multiplier = expected_pa / 4.20
                
                adj_mean_hits = float(model_data.get('mean_hits', 0.0)) * hit_adj * volume_multiplier
                adj_mean_tb = float(model_data.get('mean_tb', 0.0)) * tb_adj * volume_multiplier
                
                true_prob = 0.0
                raw_stat = str(market.get('stat_type', '')).lower().replace(" ", "_")
                raw_line = market.get('line')
                if raw_line is None or raw_line == 0:
                    continue
                    
                line = float(raw_line)
                
                if 'hit' in raw_stat and 'allow' not in raw_stat:
                    true_prob = calculate_nbinom_prob(adj_mean_hits, adj_mean_hits * 1.35, line)
                elif 'base' in raw_stat and 'allow' not in raw_stat and 'steal' not in raw_stat:
                    true_prob = calculate_nbinom_prob(adj_mean_tb, adj_mean_tb * 1.55, line)
                
                if true_prob > 0:
                    raw_mult = market.get('multiplier')
                    if pd.isna(raw_mult) or float(raw_mult) == 0.0:
                        continue 
                        
                    multiplier = float(raw_mult)
                    ev = calculate_ev(true_prob, multiplier)
                    
                    insight_text = "Projects for " + str(round(expected_pa, 1)) + " PA based on batting " + str(lineup_spot) + "th."
                    if opponent_pitcher!= "unknown":
                        insight_text = "Log5 adjusted vs " + str(opponent_pitcher).title() + ". " + insight_text
                        
                    final_opportunities.append(dict(
                        player_name=market.get('player_name'),
                        opposing_pitcher=str(opponent_pitcher).title() if opponent_pitcher!= "unknown" else "TBD",
                        stat_type=raw_stat,
                        line=line,
                        sportsbook_multiplier=multiplier,
                        market_popularity=market.get('pick_popularity'),
                        true_probability=true_prob,
                        expected_value=ev,
                        insight=insight_text
                    ))
    
    if len(final_opportunities) == 0:
        final_opportunities.append(dict(
            player_name="Debug Report", opposing_pitcher="N/A", stat_type="system_status", line=0.0,
            sportsbook_multiplier=1.0, market_popularity=0.0, true_probability=0.0, 
            expected_value=0.0, insight="Matches found: " + str(matched_count)
        ))
    
    final_opportunities = sorted(final_opportunities, key=lambda x: x.get('expected_value', 0), reverse=True)
    
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(final_opportunities, f, indent=4)
    print("Pipeline complete. Exported " + str(len(final_opportunities)) + " props to " + str(OUTPUT_JSON))

if __name__ == "__main__":
    run_pipeline()