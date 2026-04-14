import os
import json
import pandas as pd
from src.ingestion import fetch_recent_statcast
from src.features import engineer_features
from src.model import generate_predictions, calculate_nbinom_prob
from src.scraper import scrape_sleeper_lines
from src.config import OUTPUT_JSON

def calculate_ev(true_prob, multiplier):
    """Calculates expected value based on Sleeper's dynamic multipliers."""
    ev = (float(true_prob) * float(multiplier)) - 1
    return round(ev, 4)

def normalize_name(name):
    """Removes all punctuation and suffixes so MLB names and Sleeper names lock together."""
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

def run_pipeline():
    print("1. Ingesting Data...")
    statcast_df = fetch_recent_statcast(days=365)
    
    print("2. Engineering Features...")
    features_df = engineer_features(statcast_df)
    
    print("3. Generating Probability Distributions...")
    preds_df = generate_predictions(features_df)
    
    print("4. Scraping Sleeper Market Lines...")
    sleeper_df = scrape_sleeper_lines()
    
    # Fill NaNs to prevent JSON crashes, but we must handle the 0s it creates!
    sleeper_df = sleeper_df.fillna(0)
    preds_df = preds_df.fillna(0)
    
    print("5. Calculating Expected Value (EV)...")
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
                true_prob = 0.0
                
                raw_stat = str(market.get('stat_type', '')).lower().replace(" ", "_")
                raw_line = market.get('line')
                if raw_line is None or raw_line == 0:
                    continue
                    
                line = float(raw_line)
                mean_hits = float(model_data.get('mean_hits', 0.0))
                mean_tb = float(model_data.get('mean_tb', 0.0))
                
                if 'hit' in raw_stat and 'allow' not in raw_stat:
                    true_prob = calculate_nbinom_prob(mean_hits, float(model_data.get('var_hits', 0.0)), line)
                elif 'base' in raw_stat and 'allow' not in raw_stat and 'steal' not in raw_stat:
                    true_prob = calculate_nbinom_prob(mean_tb, float(model_data.get('var_tb', 0.0)), line)
                
                if true_prob > 0:
                    raw_mult = market.get('multiplier')
                    
                    # Remove the 1.77x fallback; skip the prop if Sleeper pulled the multiplier
                    if pd.isna(raw_mult) or float(raw_mult) == 0.0:
                        continue 
                        
                    multiplier = float(raw_mult)
                    ev = calculate_ev(true_prob, multiplier)
                    
                    insight_text = "Standard variance play based on recent volume."
                    if float(model_data.get('xwoba', 0)) > 0.350:
                        insight_text = "High xwOBA (" + str(model_data.get('xwoba')) + ") confirms elite underlying metrics."
                        
                    final_opportunities.append(dict(
                        player_name=market.get('player_name'),
                        stat_type=raw_stat,
                        line=line,
                        sportsbook_multiplier=multiplier,
                        market_popularity=market.get('pick_popularity'),
                        true_probability=true_prob,
                        expected_value=ev,
                        insight=insight_text
                    ))
    
    if len(final_opportunities) == 0:
        debug_msg = "Fallback. "
        if sleeper_df.empty:
            debug_msg += "Sleeper API failed / returned 0 props. "
        else:
            debug_msg += "Sleeper API found " + str(len(sleeper_df)) + " props. "
            
        if preds_df.empty:
            debug_msg += "MLB DB returned 0 players. "
        else:
            debug_msg += "MLB DB found " + str(len(preds_df)) + " players. "
            
        debug_msg += "Matches found: " + str(matched_count)

        final_opportunities.append(dict(
            player_name="Debug Report", stat_type="system_status", line=0.0,
            sportsbook_multiplier=1.0, market_popularity=0.0, true_probability=0.0, 
            expected_value=0.0, insight=debug_msg
        ))
    
    final_opportunities = sorted(final_opportunities, key=lambda x: x.get('expected_value', 0), reverse=True)
    
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(final_opportunities, f, indent=4)
    print("Pipeline complete. Exported " + str(len(final_opportunities)) + " props to " + str(OUTPUT_JSON))

if __name__ == "__main__":
    run_pipeline()