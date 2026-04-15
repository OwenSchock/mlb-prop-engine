from apify_client import ApifyClient
from src.config import APIFY_TOKEN
import pandas as pd
import time

def scrape_sleeper_lines():
    """Scrapes the Sleeper Picks board using the Apify GraphQL Actor with retries."""
    if not APIFY_TOKEN:
        print("Warning: APIFY_TOKEN missing. Returning empty dataframe.")
        return pd.DataFrame()

    client = ApifyClient(APIFY_TOKEN)
    run_input = dict(
        leagues=list(("MLB",)),
        statTypes="hits,total_bases"
    )
    
    print("Connecting to Apify Sleeper Actor (this may take up to 60 seconds)...")
    
    run = None
    for attempt in range(3):
        try:
            run = client.actor("zen-studio/sleeper-player-props").call(
                run_input=run_input,
                memory_mbytes=4096,
                timeout_secs=180
            )
            if run and run.get('status') == 'SUCCEEDED':
                break
            print("Apify Actor failed. Retrying " + str(attempt+1) + "/3...")
            time.sleep(3)
        except Exception as e:
            print("Apify Error: " + str(e) + ". Retrying " + str(attempt+1) + "/3...")
            time.sleep(3)
            
    if not run or not run.get('defaultDatasetId'):
        return pd.DataFrame()

    dataset_id = run.get('defaultDatasetId')
    try:
        items = client.dataset(dataset_id).list_items().items
    except Exception:
        return pd.DataFrame()
    
    lines = list()
    for item in items:
        lines.append(dict(
            player_name=item.get('player_name', item.get('player')),
            team=item.get('team'),
            stat_type=item.get('stat_type', item.get('stat')),
            line=item.get('line', item.get('prop_line')),
            multiplier=item.get('payout_multiplier_over', item.get('over_multiplier', item.get('multiplier', 0))),
            pick_popularity=item.get('pick_popularity', 0)
        ))
        
    return pd.DataFrame(lines)