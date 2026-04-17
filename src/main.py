import os
import json
import requests
import statsapi
import pandas as pd
from datetime import datetime
from src.ingestion import fetch_recent_statcast
from src.features import engineer_batter_splits, engineer_pitcher_profiles # UPDATED IMPORTS
from src.model import generate_predictions, calculate_nbinom_prob
from src.scraper import scrape_sleeper_lines
from src.config import OUTPUT_JSON, BALLDONTLIE_KEY
from src.grader import grade_previous_day

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

# Baseline Park Factors (100 = Neutral). 
# Format: "TEAM_ABBR": {"HIT": Hit_Factor, "TB": Total_Base_Factor}
PARK_FACTORS = {
    "COL": {"HIT": 1.15, "TB": 1.18}, # Coors Field
    "CIN": {"HIT": 1.02, "TB": 1.12}, # Great American Ball Park
    "BOS": {"HIT": 1.08, "TB": 1.06}, # Fenway Park
    "KC":  {"HIT": 1.04, "TB": 0.96}, # Kauffman Stadium (Lots of hits, few HRs)
    "MIA": {"HIT": 0.96, "TB": 0.92}, # loanDepot park
    "SEA": {"HIT": 0.94, "TB": 0.92}, # T-Mobile Park
    "TB":  {"HIT": 0.96, "TB": 0.95}, # Tropicana Field
    "OAK": {"HIT": 0.95, "TB": 0.93}, # Oakland Coliseum
    "ATH": {"HIT": 0.95, "TB": 0.93}, # Oakland (Alternate Abbr)
    "SD":  {"HIT": 0.97, "TB": 0.95}, # Petco Park
    "NYY": {"HIT": 0.98, "TB": 1.06}, # Yankee Stadium (Suppresses hits, boosts HRs)
    "BAL": {"HIT": 1.01, "TB": 0.97}, # Camden Yards (Left field wall moved back)
}

# Format: "TEAM_ABBR": (Latitude, Longitude, Is_Dome)
# Is_Dome = True means climate controlled (ignore outside weather)
STADIUM_COORDS = {
    "ARI": (33.445, -112.066, True),  "ATL": (33.890, -84.467, False), "BAL": (39.284, -76.621, False),
    "BOS": (42.346, -71.097, False),  "CHC": (41.948, -87.655, False), "CWS": (41.829, -87.633, False),
    "CHW": (41.829, -87.633, False),  "CIN": (39.097, -84.506, False), "CLE": (41.496, -81.685, False),
    "COL": (39.755, -104.994, False), "DET": (42.338, -83.048, False), "HOU": (29.757, -95.355, True),
    "KC":  (39.051, -94.480, False),  "KCR": (39.051, -94.480, False), "LAA": (33.800, -117.882, False),
    "LAD": (34.073, -118.239, False), "MIA": (25.778, -80.219, True),  "MIL": (43.027, -87.971, True),
    "MIN": (44.981, -93.277, False),  "NYM": (40.757, -73.845, False), "NYY": (40.829, -73.926, False),
    "OAK": (38.580, -121.512, False), "ATH": (38.580, -121.512, False), "PHI": (39.906, -75.166, False),
    "PIT": (40.446, -80.005, False),  "SD":  (32.707, -117.156, False), "SDP": (32.707, -117.156, False),
    "SF":  (37.778, -122.389, False), "SFG": (37.778, -122.389, False), "SEA": (47.591, -122.332, True),
    "STL": (38.622, -90.192, False),  "TB":  (27.768, -82.653, True),   "TBR": (27.768, -82.653, True),
    "TEX": (32.737, -97.084, True),   "TOR": (43.641, -79.389, True),   "WSH": (38.873, -77.007, False),
    "WAS": (38.873, -77.007, False)
}

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
            games = dates[0].get('games', list()) 
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
    print("Fetching projected lineups and venues via MLB Stats API...")
    lineups = dict()
    player_teams = dict()
    player_venues = dict() # NEW: Track where they are playing today
    
    try:
        today = pd.to_datetime('today')
        start = (today - pd.Timedelta(days=4)).strftime('%Y-%m-%d')
        end = today.strftime('%Y-%m-%d')
        
        schedule = statsapi.get('schedule', {'sportId': 1, 'startDate': start, 'endDate': end})
        
        for date_data in schedule.get('dates', []):
            for game in date_data.get('games', []):
                game_pk = game.get('gamePk')
                try:
                    box = statsapi.get('game_boxscore', {'gamePk': game_pk})
                    teams = box.get('teams', dict())
                    
                    # Identify the Home Team to set the Venue
                    home_team_name = normalize_name(teams.get('home', dict()).get('team', dict()).get('name', ''))
                    venue_abbr = ""
                    for abbr, full_name in FULL_TEAM_MAP.items():
                        if full_name == home_team_name:
                            venue_abbr = abbr
                            break

                    for team_type in list(('away', 'home')):
                        team_data = teams.get(team_type, dict())
                        
                        team_obj = team_data.get('team', dict())
                        team_name = normalize_name(team_obj.get('name', ''))
                        team_abbr = ""
                        for abbr, full_name in FULL_TEAM_MAP.items():
                            if full_name == team_name:
                                team_abbr = abbr
                                break
                                
                        batters = team_data.get('batters', list())
                        players = team_data.get('players', dict())
                        
                        for p_id in batters:
                            p_key = "ID" + str(p_id)
                            player_info = players.get(p_key, dict())
                            
                            b_order = player_info.get('battingOrder')
                            name = player_info.get('person', dict()).get('fullName')
                            
                            if name and b_order and len(str(b_order)) >= 3:
                                order_str = str(b_order)
                                if order_str.endswith('00'):
                                    spot = int(order_str[:-2])
                                    norm_name = normalize_name(name)
                                    lineups[norm_name] = spot
                                    if team_abbr:
                                        player_teams[norm_name] = team_abbr
                                    if venue_abbr:
                                        player_venues[norm_name] = venue_abbr # Assign the venue
                except:
                    continue
    except Exception as e:
        print("Notice: Lineup fetch failed - " + str(e))
        
    return lineups, player_teams, player_venues # Return the new dictionary

def calculate_log5_adjustment(pitcher_rate, league_rate):
    if league_rate <= 0 or pitcher_rate <= 0:
        return 1.0
    return float(pitcher_rate) / float(league_rate)

# Create a dictionary to store temperatures so we only call the API once per stadium
WEATHER_CACHE = dict()

def get_weather_multiplier(venue_abbr):
    """Returns a multiplier based on local temperature, ignoring domed stadiums (with caching)."""
    coords = STADIUM_COORDS.get(venue_abbr)
    if not coords:
        return 1.0, 72.0 # Default neutral
        
    lat, lon, is_dome = coords
    
    # If the stadium has a roof, weather doesn't affect the ball
    if is_dome:
        return 1.0, 72.0
        
    # --- CACHE CHECK ---
    # If we already looked up this stadium's weather today, use the saved value!
    if venue_abbr in WEATHER_CACHE:
        temp_f = WEATHER_CACHE[venue_abbr]
    else:
        # Otherwise, fetch it from the API and save it to the cache
        from src.ingestion import fetch_weather_forecast
        temp_f = fetch_weather_forecast(lat, lon)
        WEATHER_CACHE[venue_abbr] = temp_f
    
    # Calculate difference from baseline (72 degrees)
    temp_diff = temp_f - 72.0
    multiplier = 1.0 + (temp_diff * 0.0025)
    
    # Cap the extreme weather impacts just in case of data spikes
    multiplier = max(0.90, min(1.10, multiplier))
    
    return round(multiplier, 3), temp_f

def run_pipeline():

    grade_previous_day()

    print("1. Ingesting Data...")
    statcast_df = fetch_recent_statcast(days=365)
    
    print("2. Engineering Matchup Features (Splits & Expected Metrics)...")
    batter_df = engineer_batter_splits(statcast_df)
    pitcher_df = engineer_pitcher_profiles(statcast_df)
    
    if not pitcher_df.empty:
        pitcher_df.insert(0, 'join_name', pitcher_df.get('player_name').apply(normalize_name))
    
    print("3. Generating Probability Distributions...")
    preds_df = generate_predictions(batter_df)
    if not preds_df.empty:
        preds_df.insert(0, 'join_name', preds_df.get('player_name').apply(normalize_name))
    
    print("4. Scraping Sleeper Market Lines...")
    sleeper_df = scrape_sleeper_lines()
    
    sleeper_df = sleeper_df.fillna(0)
    preds_df = preds_df.fillna(0)
    
    print("5. Applying Matchups, Volume, Park Factors & Weather...")
    probable_pitchers = fetch_probable_pitchers()
    batting_orders, player_teams, player_venues = fetch_batting_orders()
    
    final_opportunities = list()
    matched_count = 0
    
    if not sleeper_df.empty and not preds_df.empty:
        for _, market in sleeper_df.iterrows():
            market_player = normalize_name(market.get('player_name'))
            
            # --- 1. Identify Team, Venue & Opposing Pitcher ---
            scraped_team = str(market.get('team', '')).strip().upper()
            if scraped_team == 'NONE': 
                scraped_team = ''
                
            team_abbr = player_teams.get(market_player, scraped_team).upper()
            team_name = FULL_TEAM_MAP.get(team_abbr, "unknown")
            opponent_pitcher = probable_pitchers.get(team_name, "unknown")
            venue = player_venues.get(market_player, team_abbr) # Default to home stadium if unknown
            
            # Default Pitcher Profile (League Average RHP)
            pitcher_arm = 'R'
            pitcher_hit_allowed = LEAGUE_AVG_HIT_RATE
            pitcher_tb_allowed = LEAGUE_AVG_SLG_RATE
            
            # Match Pitcher & Get Expected Metrics
            if not pitcher_df.empty and opponent_pitcher != "unknown":
                p_match_df = pitcher_df[pitcher_df['join_name'] == opponent_pitcher]
                if not p_match_df.empty:
                    p_match = p_match_df.iloc[0].to_dict()
                    pitcher_arm = p_match.get('throw_arm', 'R')
                    pitcher_hit_allowed = float(p_match.get('p_xba', LEAGUE_AVG_HIT_RATE))
                    pitcher_tb_allowed = float(p_match.get('p_xslg', LEAGUE_AVG_SLG_RATE))

            # --- 2. Match Batter against Specific Arm Split ---
            model_data = None
            player_splits = preds_df[(preds_df['join_name'] == market_player) & (preds_df['split_arm'] == pitcher_arm)]
            
            if not player_splits.empty:
                model_data = player_splits.iloc[0].to_dict()
            elif not preds_df[preds_df['join_name'] == market_player].empty:
                model_data = preds_df[preds_df['join_name'] == market_player].iloc[0].to_dict()

            # --- 3. Process the Data if Match Found ---
            if model_data is not None:
                matched_count += 1
                
                # Baseline Matchup Math
                hit_adj = calculate_log5_adjustment(pitcher_hit_allowed, LEAGUE_AVG_HIT_RATE)
                tb_adj = calculate_log5_adjustment(pitcher_tb_allowed, LEAGUE_AVG_SLG_RATE)
                
                # Volume Math
                lineup_spot = batting_orders.get(market_player, 5)
                expected_pa = PA_EXPECTATIONS.get(lineup_spot, 4.22)
                volume_multiplier = expected_pa / 4.22 
                
                # Environmental Math
                park_hit_factor = PARK_FACTORS.get(venue, {}).get("HIT", 1.0)
                park_tb_factor = PARK_FACTORS.get(venue, {}).get("TB", 1.0)
                
                weather_multi, game_temp = get_weather_multiplier(venue)
                tb_weather_adj = weather_multi
                hit_weather_adj = 1.0 + ((weather_multi - 1.0) * 0.5) 
                
                # --- NEW: MATHEMATICAL GOVERNOR ---
                # 1. Calculate Deltas
                hit_delta = hit_adj - 1.0
                tb_delta = tb_adj - 1.0
                park_hit_delta = park_hit_factor - 1.0
                park_tb_delta = park_tb_factor - 1.0
                weather_hit_delta = hit_weather_adj - 1.0
                weather_tb_delta = tb_weather_adj - 1.0

                # 2. Prevent Double Counting Home Parks
                if player_teams.get(market_player) == venue:
                    park_hit_delta *= 0.25 
                    park_tb_delta *= 0.25

                # 3. Sum Deltas
                combined_hit_modifier = 1.0 + hit_delta + park_hit_delta + weather_hit_delta
                combined_tb_modifier = 1.0 + tb_delta + park_tb_delta + weather_tb_delta

                # 4. Cap Extremes (+/- 25%)
                combined_hit_modifier = max(0.75, min(1.25, combined_hit_modifier))
                combined_tb_modifier = max(0.75, min(1.25, combined_tb_modifier))

                # Apply final modifiers to the mean (Volume multiplier remains absolute)
                adj_mean_hits = float(model_data.get('mean_hits', 0.0)) * combined_hit_modifier * volume_multiplier
                adj_mean_tb = float(model_data.get('mean_tb', 0.0)) * combined_tb_modifier * volume_multiplier
                
                true_prob = 0.0
                raw_stat = str(market.get('stat_type', '')).lower().replace(" ", "_")
                raw_line = market.get('line')
                if raw_line is None or raw_line == 0:
                    continue
                    
                line = float(raw_line)
                
                # Negative Binomial Distribution
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
                    
                    # Build Insight Text
                    insight_text = "Projects for " + str(round(expected_pa, 2)) + " PA based on batting " + str(lineup_spot) + "th. "
                    if opponent_pitcher != "unknown":
                        insight_text = "Log5 adjusted vs " + str(pitcher_arm) + "HP " + str(opponent_pitcher).title() + ". " + insight_text
                        
                    if float(model_data.get('xwoba', 0)) > 0.350:
                        insight_text = "Elite xwOBA (" + str(model_data.get('xwoba')) + ") vs " + str(pitcher_arm) + "HP + " + insight_text
                        
                    # Append Weather Insight
                    if STADIUM_COORDS.get(venue, (0,0,True))[2] == False:
                        insight_text += f" Forecast: {round(game_temp)}°F."
                    else:
                        insight_text += " Playing in a controlled dome."
                        
                    final_opportunities.append(dict(
                        player_name=market.get('player_name'),
                        team=team_abbr,
                        opposing_pitcher=str(opponent_pitcher).title() if opponent_pitcher != "unknown" else "TBD",
                        stat_type=raw_stat,
                        line=line,
                        sportsbook_multiplier=multiplier,
                        market_popularity=market.get('pick_popularity'),
                        true_probability=true_prob,
                        expected_value=ev,
                        insight=insight_text,
                        is_free_pick=bool(market.get('is_free_pick', False))
                    ))
    
    if len(final_opportunities) == 0:
        final_opportunities.append(dict(
            player_name="Debug Report", team="MLB", opposing_pitcher="N/A", stat_type="system_status", line=0.0,
            sportsbook_multiplier=1.0, market_popularity=0.0, true_probability=0.0, 
            expected_value=0.0, insight="Matches found: " + str(matched_count)
        ))
    
    final_opportunities = sorted(final_opportunities, key=lambda x: x.get('expected_value', 0), reverse=True)
    
    # ==========================================
    # FEATURE 3: PARLAY GENERATOR
    # ==========================================
    import itertools
    
    parlay_suggestions = list()
    top_picks = final_opportunities[:7] # Grab top 7 to ensure we have enough valid combos
    
    # Generate all possible 2-leg combinations
    for leg1, leg2 in itertools.combinations(top_picks, 2):
        
        # Rule 1: Exclude same team
        if leg1['team'] == leg2['team']:
            continue
            
        # Rule 2: Exclude same game (proxy check: are they facing the same pitcher?)
        if leg1['opposing_pitcher'] == leg2['opposing_pitcher'] and leg1['opposing_pitcher'] != "TBD":
            continue
            
        # Calculate Combined Metrics (Assuming independent events since we filtered same game)
        combined_prob = leg1['true_probability'] * leg2['true_probability']
        combined_multiplier = leg1['sportsbook_multiplier'] * leg2['sportsbook_multiplier']
        combined_ev = calculate_ev(combined_prob, combined_multiplier)
        
        parlay_suggestions.append(dict(
            legs=[leg1['player_name'], leg2['player_name']],
            teams=[leg1['team'], leg2['team']],
            combined_true_prob=round(combined_prob, 4),
            combined_multiplier=round(combined_multiplier, 2),
            expected_value=combined_ev
        ))

    # Sort parlays by EV and grab the Top 3
    parlay_suggestions = sorted(parlay_suggestions, key=lambda x: x['expected_value'], reverse=True)[:3]
    
    # Bundle everything into a final payload
    final_payload = {
        "single_props": final_opportunities,
        "parlays": parlay_suggestions
    }

    # Export to JSON (This is the ONLY export)
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(final_payload, f, indent=4)
        
    print("Pipeline complete. Exported props and parlays to " + str(OUTPUT_JSON))
    
if __name__ == "__main__":
    run_pipeline()