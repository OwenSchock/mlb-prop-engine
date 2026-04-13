import numpy as np
import pandas as pd
from scipy.stats import nbinom

def calculate_nbinom_prob(mean, variance, line):
    """Calculates the probability of hitting the OVER using the Negative Binomial Distribution."""
    if mean <= 0: return 0.0
    if variance <= mean: 
        variance = mean + 0.01 
    
    p = mean / variance
    n = (mean**2) / (variance - mean)
    
    prob_over = 1 - nbinom.cdf(line, n, p)
    return round(float(prob_over), 4)

def generate_predictions(features_df):
    """Simulates expected means and checks for NaN values to prevent math crashes."""
    predictions = list()
    
    for _, row in features_df.iterrows():
        mean_hits = float(row['hits_per_game']) if pd.notnull(row['hits_per_game']) else 0.0
        mean_tb = float(row['tb_per_game']) if pd.notnull(row['tb_per_game']) else 0.0
        
        predictions.append(dict(
            player_name=row['player_name'],
            mean_hits=mean_hits,
            var_hits=mean_hits * 1.35,
            mean_tb=mean_tb,
            var_tb=mean_tb * 1.55,
            xwoba=round(float(row['xwoba']), 3) if pd.notnull(row['xwoba']) else 0.300
        ))
        
    return pd.DataFrame(predictions)