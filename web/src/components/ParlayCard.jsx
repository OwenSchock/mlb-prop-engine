import React from 'react';
import { Zap, Link2 } from 'lucide-react';

export default function ParlayCard({ data }) {
  const evPercentage = (data.expected_value * 100).toFixed(2);
  const isPositiveEV = data.expected_value > 0;
  const evColorClass = isPositiveEV ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400';

  return (
    <div className="bg-gray-800 rounded-xl p-5 shadow-lg border border-gray-700 transition hover:border-purple-500">
      
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2 text-purple-400 font-bold uppercase text-sm tracking-wider">
          <Zap size={18} />
          <span>2-Leg Parlay</span>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1 ${evColorClass}`}>
          {evPercentage}% EV
        </div>
      </div>

      {/* The Legs */}
      <div className="space-y-3 mb-5 pl-2 border-l-2 border-gray-600">
        {data.legs.map((leg, index) => (
          <div key={index} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Link2 size={14} className="text-gray-500" />
              <h3 className="text-lg font-bold text-white">{leg}</h3>
              <span className="px-1.5 py-0.5 bg-gray-700 text-gray-300 text-[10px] font-bold rounded border border-gray-600 tracking-wider">
                {data.teams[index]}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Metrics Footer */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded-lg p-3 border border-gray-700/50">
          <p className="text-xs text-gray-500 uppercase mb-1">True Prob</p>
          <p className="text-lg font-mono text-blue-400">{(data.combined_true_prob * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-3 border border-gray-700/50">
          <p className="text-xs text-gray-500 uppercase mb-1">Combined Payout</p>
          <p className="text-lg font-mono text-purple-400">{data.combined_multiplier.toFixed(2)}x</p>
        </div>
      </div>
      
    </div>
  );
}