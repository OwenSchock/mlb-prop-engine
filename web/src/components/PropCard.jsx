import React from 'react';
import { TrendingUp, Info, Swords } from 'lucide-react';

const getTeamLogo = (teamAbbr) => {
  if (!teamAbbr) return '';
  if (teamAbbr === 'MLB') return '';
  
  const teamMap = new Map();
  teamMap.set('ARI', 109); teamMap.set('ATL', 144); teamMap.set('BAL', 110);
  teamMap.set('BOS', 111); teamMap.set('CHC', 112); teamMap.set('CWS', 145);
  teamMap.set('CIN', 113); teamMap.set('CLE', 114); teamMap.set('COL', 115);
  teamMap.set('DET', 116); teamMap.set('HOU', 117); teamMap.set('KC', 118);
  teamMap.set('LAA', 108); teamMap.set('LAD', 119); teamMap.set('MIA', 146);
  teamMap.set('MIL', 158); teamMap.set('MIN', 142); teamMap.set('NYM', 121);
  teamMap.set('NYY', 147); teamMap.set('OAK', 133); teamMap.set('ATH', 133);
  teamMap.set('PHI', 143); teamMap.set('PIT', 134); teamMap.set('SD', 135);
  teamMap.set('SF', 137);  teamMap.set('SEA', 136); teamMap.set('STL', 138);
  teamMap.set('TB', 139);  teamMap.set('TEX', 140); teamMap.set('TOR', 141);
  teamMap.set('WSH', 120); teamMap.set('WAS', 120);

  const teamId = teamMap.get(teamAbbr);
  if (!teamId) return '';
  
  return 'https://www.mlbstatic.com/team-logos/' + teamId + '.svg';
};

export default function PropCard({ data }) {
  const evPercentage = (data.expected_value * 100).toFixed(2);
  let isPositiveEV = false;
  if (data.expected_value > 0) {
      isPositiveEV = true;
  }

  let logoElement = null;
  if (data.team) {
      if (data.team!== 'MLB') {
          const logoUrl = getTeamLogo(data.team);
          if (logoUrl!== '') {
              logoElement = <img src={logoUrl} alt={data.team} className="w-9 h-9 object-contain drop-shadow-md" />;
          }
      }
  }

  let matchupElement = null;
  if (data.opposing_pitcher) {
      if (data.opposing_pitcher!== 'N/A') {
          if (data.opposing_pitcher!== 'TBD') {
              matchupElement = (
                  <div className="flex items-center gap-2 mb-4 text-xs font-semibold bg-gray-900/50 w-max px-2 py-1 rounded border border-gray-700 text-indigo-300">
                      <Swords size={14} />
                      <span>vs. {data.opposing_pitcher}</span>
                  </div>
              );
          }
      }
  }

  let evColorClass = 'bg-red-500/20 text-red-400';
  if (isPositiveEV) {
      evColorClass = 'bg-emerald-500/20 text-emerald-400';
  }

  return (
    <div className="bg-gray-800 rounded-xl p-5 shadow-lg border border-gray-700 transition hover:border-emerald-500">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3">
          {logoElement}
          <div>
            <h2 className="text-xl font-bold text-white">{data.player_name}</h2>
            <p className="text-sm text-gray-400 capitalize">{data.stat_type.replace('_', ' ')} • Line: {data.line}</p>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1 ${evColorClass}`}>
          <TrendingUp size={16} />
          {evPercentage}% EV
        </div>
      </div>

      {matchupElement}

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