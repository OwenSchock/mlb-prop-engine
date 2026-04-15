import React from 'react';
import { TrendingUp, Info, Swords } from 'lucide-react';

// Helper function to map Sleeper abbreviations to the ESPN logo network
const getTeamLogo = (teamAbbr) => {
  if (!teamAbbr |

| teamAbbr === 'MLB') return '';
  
  // Handle slight differences in abbreviations between Sleeper and ESPN
  const map = {
    'CWS': 'chw',
    'TB': 'tb',
    'ATH': 'oak',
    'WSH': 'wsh'
  };
  
  const queryAbbr = map[teamAbbr] |

| teamAbbr.toLowerCase();
  return `https://a.espncdn.com/i/teamlogos/mlb/500/scoreboard/${queryAbbr}.png`;
};

export default function PropCard({ data }) {
  const evPercentage = (data.expected_value * 100).toFixed(2);
  const isPositiveEV = data.expected_value > 0;

  return (
    <div className="bg-gray-800 rounded-xl p-5 shadow-lg border border-gray-700 transition hover:border-emerald-500">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3">
          {data.team && data.team!== 'MLB'? (
            <img src={getTeamLogo(data.team)} alt={data.team} className="w-9 h-9 object-contain drop-shadow-md" />
          ) : null}
          <div>
            <h2 className="text-xl font-bold text-white">{data.player_name}</h2>
            <p className="text-sm text-gray-400 capitalize">{data.stat_type.replace('_', ' ')} • Line: {data.line}</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1 ${isPositiveEV? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
          <TrendingUp size={16} />
          {evPercentage}% EV
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4 text-xs font-semibold bg-gray-900/50 w-max px-2 py-1 rounded border border-gray-700 text-indigo-300">
        <Swords size={14} />
        <span>vs. {data.opposing_pitcher}</span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-gray-900 rounded-lg p-3">
          <p className="text-xs text-gray-500 uppercase">True Prob</p>
          <p className="text-lg font-mono text-blue-400">{(data.true_probability * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-3">
          <p className="text-xs text-gray-500 uppercase">Sleeper Multiplier</p>
          <p className="text-lg font-mono text-purple-400">{data.sportsbook_multiplier}x</p>
        </div>
      </div>

      <div className="flex items-start gap-2 bg-gray-700/30 p-3 rounded-lg border border-gray-600/50">
        <Info size={16} className="text-gray-400 mt-0.5 shrink-0" />
        <p className="text-sm text-gray-300">{data.insight}</p>
      </div>
    </div>
  );
}