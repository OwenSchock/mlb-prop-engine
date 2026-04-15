import os
import json
import requests
import statsapi
import pandas as pd
from datetime import datetime
from src.ingestion import fetch_recent_statcast
from src.features import engineer_features
from src.model import generate_predictions, calculate_nbinom_prob
from src.scraper import scrape_sleeper_lines
from src.config import OUTPUT_JSON, BALLDONTLIE_KEY

LEAGUE_AVG_HIT_RATE = 0.240
LEAGUE_AVG_SLG_RATE = 0.400

FULL_TEAM_MAP = dict(
    ARI="arizona diamondbacks", ATL="atlanta braves", BAL="baltimore orioles",
    BOS="boston red sox", CHC="chicago cubs", CWS="chicago white sox", CHW="chicago white sox",
    CIN="cincinnati reds", CLE="cleveland guardians", COL="colorado rockies",
    DET="detroit tigers", HOU="houston astros", KC="kansas city royals", KCR="kansas city royals",
    LAA="los angeles angels", LAD="los angeles dodgers", MIA="miami marlins",
    MIL="milwaukee brewers", MIN="minnesota twins", NYM="new york mets",
    NYY="new york yankees", OAK="oakland athletics", ATH="oakland athletics",
    PHI="philadelphia phillies", PIT="pittsburgh pirates", SD="san diego padres", SDP="san diego padres",
    SF="san francisco giants", SFG="san francisco giants", SEA="seattle mariners", STL="st louis cardinals",
    TB="tampa bay rays", TBR="tampa bay rays", TEX="texas rangers", TOR="toronto blue jays",
    WSH="washington nationals", WAS="washington nationals"
)

PA_EXPECTATIONS = dict()
PA_EXPECTATIONS[1] = 4.63
PA_EXPECTATIONS[2] = 4.52
PA_EXPECTATIONS[3] = 4.42
PA_EXPECTATIONS[4] = 4.32
PA_EXPECTATIONS[5] = 4.22
PA_EXPECTATIONS[6] = 4.11
PA_EXPECTATIONS[7] = 3.99
PA_EXPECTATIONS[8] = 3.88
PA_EXPECTATIONS[9] = 3.75

def calculate_ev(true_prob, multiplier):
    if multiplier is None:
        multiplier = 1.0
    ev = (float(true_prob) * float(multiplier)) - 1
    return round(ev, 4)

def normalize_name(name):
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
    print("Fetching today's probable pitchers via explicit hydration...")
    pitchers = dict()
    try:
        today = datetime.today().strftime('%Y-%m-%d')
        params = dict(sportId=1, date=today, hydrate='probablePitcher')
        schedule = statsapi.get('schedule', params)
        
        dates = schedule.get('dates', list())
        if len(dates) > 0:
            # BUG FIX: Access the first element of the dates list instead of using.get()
            games = dates.get('games', list()) 
            for game in games:
                teams = game.get('teams', dict())
                home = teams.get('home', dict())
                away = teams.get('away', dict())
                
                home_team = normalize_name(home.get('team', dict()).get('name', ''))
                away_team = normalize_name(away.get('team', dict()).get('name', ''))
                
                hp = normalize_name(home.get('probablePitcher', dict()).get('fullName', 'unknown'))
                ap = normalize_name(away.get('probablePitcher', dict()).get('fullName', 'unknown'))
                
                pitchers[home_team] = ap
                pitchers[away_team] = hp
    except Exception as e:
        print("Notice: Probable pitcher fetch failed - " + str(e))
    return pitchers

def fetch_batting_orders():
    print("Fetching daily lineups from BallDontLie API...")
    lineups = dict()
    player_teams = dict() # BUG FIX: Map players to their teams securely to ensure logos load
    try:
        today = datetime.today().strftime('%Y-%m-%d')
        url = "https://api.balldontlie.io/v1/lineups"
        headers = dict(Authorization=BALLDONTLIE_KEY)
        params = dict(dates=today)
        
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json().get('data', list())
            for game in data:
                home_team = game.get('home_team', dict()).get('abbreviation', '')
                away_team = game.get('visitor_team', dict()).get('abbreviation', '')
                
                for team_type, team_abbr in list((('home_team_lineup', home_team), ('visitor_team_lineup', away_team))):
                    team_lineup = game.get(team_type, list())
                    for player in team_lineup:
                        p_info = player.get('player', dict())
                        name = normalize_name(p_info.get('first_name', '') + " " + p_info.get('last_name', ''))
                        order = player.get('batting_order')
                        if name:
                            if team_abbr:
                                player_teams[name] = team_abbr
                            if order:
                                lineups[name] = int(order)
    except Exception as e:
        print("Notice: Lineup fetch failed - " + str(e))
    return lineups, player_teams

def calculate_log5_adjustment(pitcher_rate, league_rate):
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
    batting_orders, player_teams = fetch_batting_orders()
    
    try:
        from pybaseball import pitching_stats
        pitcher_df = pitching_stats(2026)
        if pitcher_df.empty:
            pitcher_df = pitching_stats(2025)
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
                
                # Securely fetch the team abbreviation
                scraped_team = str(market.get('team', '')).strip().upper()
                if scraped_team == 'NONE': 
                    scraped_team = ''
                    
                team_abbr = player_teams.get(market_player, scraped_team).upper()
                team_name = FULL_TEAM_MAP.get(team_abbr, "unknown")
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
                
                lineup_spot = batting_orders.get(market_player, 5)
                expected_pa = PA_EXPECTATIONS.get(lineup_spot, 4.22)
                volume_multiplier = expected_pa / 4.22 
                
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
                    
                    insight_text = "Projects for " + str(round(expected_pa, 2)) + " PA based on batting " + str(lineup_spot) + "th. "
                    if opponent_pitcher!= "unknown":
                        insight_text = "Log5 adjusted vs " + str(opponent_pitcher).title() + ". " + insight_text
                        
                    if float(model_data.get('xwoba', 0)) > 0.350:
                        insight_text = "Elite xwOBA (" + str(model_data.get('xwoba')) + ") + " + insight_text
                        
                    final_opportunities.append(dict(
                        player_name=market.get('player_name'),
                        team=team_abbr,
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
            player_name="Debug Report", team="MLB", opposing_pitcher="N/A", stat_type="system_status", line=0.0,
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