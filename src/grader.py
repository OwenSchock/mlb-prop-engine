import os
import json
import statsapi
import pandas as pd
from datetime import datetime, timedelta
from src.config import OUTPUT_JSON

HISTORY_JSON = os.path.join(os.path.dirname(OUTPUT_JSON), "history.json")

def normalize_name(name):
    if pd.isnull(name) or not name: return "unknown"
    name = str(name).replace(".", "").replace("-", " ").replace("'", "").strip().lower()
    accents = dict(á='a', é='e', í='i', ó='o', ú='u', ñ='n', ã='a', ë='e', ü='u')
    for k, v in accents.items(): name = name.replace(k, v)
    if "," in name: name = " ".join(name.split(", ")[::-1])
    for suffix in (" jr", " sr", " ii", " iii"):
        if name.endswith(suffix): name = name[:-len(suffix)]
    return name.strip()

def fetch_yesterdays_stats():
    """Pulls all batter stats from yesterday's MLB games."""
    yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    player_stats = dict()
    
    try:
        schedule = statsapi.get('schedule', {'sportId': 1, 'date': yesterday})
        for date_data in schedule.get('dates', []):
            for game in date_data.get('games', []):
                # Only check completed games
                if game.get('status', {}).get('statusCode') not in ['F', 'O']: 
                    continue
                    
                box = statsapi.get('game_boxscore', {'gamePk': game.get('gamePk')})
                teams = box.get('teams', {})
                
                for team_type in ('away', 'home'):
                    players = teams.get(team_type, {}).get('players', {})
                    for p_key, p_data in players.items():
                        name = normalize_name(p_data.get('person', {}).get('fullName'))
                        stats = p_data.get('stats', {}).get('batting', {})
                        
                        if name and stats:
                            # Formula for Total Bases from box score stats
                            hits = stats.get('hits', 0)
                            doubles = stats.get('doubles', 0)
                            triples = stats.get('triples', 0)
                            hrs = stats.get('homeRuns', 0)
                            
                            total_bases = hits + doubles + (2 * triples) + (3 * hrs)
                            pa = stats.get('plateAppearances', 0)
                            
                            player_stats[name] = {
                                "hits": hits,
                                "total_bases": total_bases,
                                "pa": pa
                            }
    except Exception as e:
        print(f"Notice: Grader failed to fetch box scores - {e}")
        
    return player_stats, yesterday

def grade_previous_day():
    print("0. Running Automated Grader on Yesterday's Picks...")
    
    if not os.path.exists(OUTPUT_JSON):
        print("No previous predictions found to grade.")
        return

    with open(OUTPUT_JSON, 'r') as f:
        try:
            prev_data = json.load(f)
        except:
            return

    single_props = prev_data.get('single_props', [])
    
    # FIX 1: Remove the < 10 check. Just ensure there is at least something to grade.
    if not single_props: 
        return 

    # Safely slice the top and bottom depending on how many props exist today
    top_count = min(5, len(single_props))
    top_5 = single_props[:top_count]
    
    # Ensure we don't overlap if there are fewer than 10 total props
    bottom_count = min(5, len(single_props) - top_count)
    bottom_5 = single_props[-bottom_count:] if bottom_count > 0 else []
    
    # Tag them for the history file
    for p in top_5: p['category'] = 'Top 5 (Target)'
    for p in bottom_5: p['category'] = 'Bottom 5 (Avoid)'
    picks_to_grade = top_5 + bottom_5

    actual_stats, game_date = fetch_yesterdays_stats()
    
    # Load existing history
    history = []
    if os.path.exists(HISTORY_JSON):
        with open(HISTORY_JSON, 'r') as f:
            history = json.load(f)

    # Check if we already graded this date to prevent duplicates
    if any(h.get('date') == game_date for h in history):
        print(f"Already graded picks for {game_date}. Skipping.")
        return

    graded_count = 0
    for pick in picks_to_grade:
        p_name = normalize_name(pick['player_name'])
        stats = actual_stats.get(p_name)

        if not stats or stats['pa'] == 0:
            pick['result'] = 'Void'
            pick['actual'] = 0
        else:
            stat_key = pick['stat_type'].lower()
            actual_val = stats.get(stat_key, 0)
            pick['actual'] = actual_val
            
            # FIX 2: Account for exact ties (Pushes)
            if actual_val == pick['line']:
                pick['result'] = 'Void'
            elif pick['category'] == 'Top 5 (Target)':
                pick['result'] = 'Win' if actual_val > pick['line'] else 'Loss'
            else:
                # For avoid plays, we want them to go under
                pick['result'] = 'Win' if actual_val < pick['line'] else 'Loss'
                
        pick['date'] = game_date
        history.append(pick)
        graded_count += 1

    # Keep only the last 30 days of picks (roughly 300 props) to keep the file lightweight
    history = history[-300:]

    os.makedirs(os.path.dirname(HISTORY_JSON), exist_ok=True)
    with open(HISTORY_JSON, 'w') as f:
        json.dump(history, f, indent=4)
        
    print(f"Grader complete. Logged {graded_count} resolved props to history.json.")