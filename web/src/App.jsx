import { useState, useEffect } from 'react';
import PropCard from './components/PropCard';
import ParlayCard from './components/ParlayCard';
import { Info, BarChart3, Target } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function App() {
  const [data, setData] = useState({ single_props: [], parlays: [] });
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInfo, setShowInfo] = useState(false);
  const [activeTab, setActiveTab] = useState('picks');
  const [wallet, setWallet] = useState([]); // Add this line with your other states

  useEffect(() => {
    fetch('./predictions.json?t=' + new Date().getTime())
      .then((res) => res.json())
      .then((fetchedData) => {
        setData(fetchedData);
        setLoading(false);
      });

    fetch('./history.json?t=' + new Date().getTime())
      .then((res) => res.json())
      .then((historyData) => setHistory(historyData))
      .catch(() => console.log("No history data found."));

    // NEW: Fetch Wallet Data
    fetch('./wallet.json?t=' + new Date().getTime())
      .then((res) => res.json())
      .then((walletData) => setWallet(walletData))
      .catch(() => console.log("No wallet data found."));
  }, []);

  // Calculate Wallet Metrics
  const currentBalance = wallet.length > 0 ? wallet[wallet.length - 1].balance : 1000;
  const totalProfit = currentBalance - 1000;
  const roiColor = totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400';

  const topProps = data.single_props ? data.single_props.slice(0, 5) : [];
  const bottomProps = data.single_props && data.single_props.length > 5 ? data.single_props.slice(-5) : [];
  const parlays = data.parlays || [];
  const freePicks = data.single_props ? data.single_props.filter(prop => prop.is_free_pick) : [];

  const calculateWinRate = (category) => {
    const validPicks = history.filter(p => p.category === category && p.result !== 'Void');
    if (validPicks.length === 0) return { rate: 0, w: 0, l: 0 };
    const wins = validPicks.filter(p => p.result === 'Win').length;
    const losses = validPicks.length - wins;
    return { rate: ((wins / validPicks.length) * 100).toFixed(1), w: wins, l: losses };
  };

  const topStats = calculateWinRate('Top 5 (Target)');
  const bottomStats = calculateWinRate('Bottom 5 (Avoid)');

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <header className="mb-6 border-b border-gray-700 pb-4">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-emerald-400">MLB Prop Prediction Engine</h1>
            <p className="text-gray-400">Automated Expected Value against Sleeper Picks API</p>
          </div>
          <button 
            onClick={() => setShowInfo(!showInfo)} 
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-blue-400 px-4 py-2 rounded-lg border border-gray-600 transition"
          >
            <Info size={20} /><span>Strategy Guide</span>
          </button>
        </div>

        {/* TAB NAVIGATION */}
        <div className="flex gap-4">
          <button 
            onClick={() => setActiveTab('picks')}
            className={`flex items-center gap-2 px-6 py-2 rounded-t-lg font-bold transition-all ${activeTab === 'picks' ? 'bg-gray-800 text-emerald-400 border-t border-x border-emerald-500/50' : 'text-gray-500 hover:text-gray-300'}`}
          >
            <Target size={18} /> Today's Board
          </button>
          <button 
            onClick={() => setActiveTab('tracking')}
            className={`flex items-center gap-2 px-6 py-2 rounded-t-lg font-bold transition-all ${activeTab === 'tracking' ? 'bg-gray-800 text-blue-400 border-t border-x border-blue-500/50' : 'text-gray-500 hover:text-gray-300'}`}
          >
            <BarChart3 size={18} /> Performance Tracking
          </button>
        </div>
      </header>

      {/* STRATEGY GUIDE BLOCK */}
      {showInfo && (
        <div className="p-4 bg-blue-900/30 border border-blue-800 rounded-xl text-blue-200 text-sm mb-6 transition-all">
          <h3 className="font-bold text-blue-400 mb-2 text-base">How to Spot Value</h3>
          <ul className="list-disc pl-5 space-y-2">
            <li><strong>What is EV?</strong> Expected Value (EV) represents your average mathematical profit per bet over time.</li>
            <li><strong>The Target (+EV):</strong> You should target the Top 5 props on the dashboard, ideally looking for anything above <strong>+3.00% EV</strong>.</li>
            <li><strong>The Parlays:</strong> The algorithm automatically combines the highest +EV props into 2-leg pairs, filtering out players from the same game.</li>
            <li><strong>The Avoid List (-EV):</strong> The Bottom 5 props represent the worst mathematical bets on the board. Avoid these.</li>
          </ul>
        </div>
      )}

      {/* RENDER PICKS TAB */}
      {activeTab === 'picks' && (
        <div>
          {freePicks.length > 0 && (
            <div className="mb-8 bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/50 rounded-xl p-4 shadow-[0_0_15px_rgba(234,179,8,0.2)]">
              <div className="flex items-center gap-3 mb-2">
                <span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500"></span></span>
                <h2 className="text-xl font-bold text-yellow-400 uppercase tracking-wider">Discount Line Detected</h2>
              </div>
              <div className="space-y-2">
                {freePicks.map((pick, index) => (
                  <div key={index} className="flex justify-between items-center bg-gray-900/50 p-3 rounded-lg border border-yellow-500/30">
                    <div><span className="text-lg font-bold text-white mr-2">{pick.player_name}</span><span className="text-sm text-gray-300 capitalize">Over {pick.line} {pick.stat_type.replace('_', ' ')}</span></div>
                    <div className="bg-yellow-500/20 text-yellow-300 px-3 py-1 rounded font-bold">Autoclick / Must Play</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {loading ? (
            <p className="text-gray-400">Running Monte Carlo Simulations...</p>
          ) : (
            <div className="space-y-10">
              <section>
                <h2 className="text-2xl font-bold text-white mb-4 border-l-4 border-emerald-500 pl-3">Top 5 Value Bets (Target)</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {topProps.map((prop, index) => <PropCard key={'top-'+index} data={prop} />)}
                </div>
              </section>

              {parlays.length > 0 && (
                <section>
                  <h2 className="text-2xl font-bold text-white mb-4 border-l-4 border-purple-500 pl-3">Top +EV Parlay Suggestions</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {parlays.map((parlay, index) => <ParlayCard key={'parlay-'+index} data={parlay} />)}
                  </div>
                </section>
              )}

              {bottomProps.length > 0 && (
                <section>
                  <h2 className="text-2xl font-bold text-white mb-4 border-l-4 border-red-500 pl-3">Bottom 5 Plays (Avoid)</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 opacity-75">
                    {bottomProps.map((prop, index) => <PropCard key={'bottom-'+index} data={prop} />)}
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      )}

      {/* RENDER TRACKING TAB */}
      {activeTab === 'tracking' && (
        <div className="space-y-8">
          
          {/* NEW: PAPER WALLET SIMULATION CHART */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="bg-gray-900/50 p-6 border-b border-gray-700 flex justify-between items-end">
              <div>
                <h3 className="text-gray-400 font-bold uppercase tracking-wider mb-1">Paper Wallet Simulation</h3>
                <p className="text-sm text-gray-500">Walk-forward simulation betting $10 per Top 3 Parlay</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400 mb-1">Current Bankroll</p>
                <p className={`text-4xl font-black ${roiColor}`}>
                  ${currentBalance.toFixed(2)}
                </p>
              </div>
            </div>
            
            <div className="p-6 h-80 w-full">
              {wallet.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={wallet} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                    <XAxis 
                      dataKey="date" 
                      stroke="#9CA3AF" 
                      tick={{ fill: '#9CA3AF', fontSize: 12 }} 
                      tickFormatter={(val) => val === "Start" ? "Start" : val.slice(5)} 
                    />
                    <YAxis 
                      domain={['auto', 'auto']} 
                      stroke="#9CA3AF" 
                      tick={{ fill: '#9CA3AF', fontSize: 12 }} 
                      tickFormatter={(val) => `$${val}`}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', color: '#F3F4F6' }}
                      itemStyle={{ color: '#34D399', fontWeight: 'bold' }}
                      formatter={(value) => [`$${value.toFixed(2)}`, 'Balance']}
                      labelStyle={{ color: '#9CA3AF', marginBottom: '4px' }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="balance" 
                      stroke="#10B981" 
                      strokeWidth={3} 
                      dot={{ r: 4, fill: '#10B981', strokeWidth: 0 }} 
                      activeDot={{ r: 6, fill: '#34D399', stroke: '#064E3B', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 italic">
                  Not enough data to graph yet. The simulation will begin after tonight's slate.
                </div>
              )}
            </div>
          </div>

          {/* ACCURACY CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-800 rounded-xl p-6 border border-emerald-500/30 text-center">
              <h3 className="text-gray-400 font-bold uppercase tracking-wider mb-2">Model "Target" Accuracy</h3>
              <p className="text-5xl font-black text-emerald-400 mb-2">{topStats.rate}%</p>
              <p className="text-gray-500 font-mono text-sm">Record: {topStats.w}W - {topStats.l}L</p>
            </div>
            <div className="bg-gray-800 rounded-xl p-6 border border-red-500/30 text-center">
              <h3 className="text-gray-400 font-bold uppercase tracking-wider mb-2">Model "Avoid" Accuracy</h3>
              <p className="text-5xl font-black text-red-400 mb-2">{bottomStats.rate}%</p>
              <p className="text-gray-500 font-mono text-sm">Record: {bottomStats.w}W - {bottomStats.l}L</p>
            </div>
          </div>

          {/* RECENT GRADED PROPS TABLE */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="bg-gray-900/50 p-4 border-b border-gray-700">
              <h3 className="text-white font-bold">Recent Graded Props</h3>
            </div>
            <div className="p-4 overflow-x-auto max-h-96 overflow-y-auto custom-scrollbar">
              <table className="w-full text-left text-sm text-gray-300">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-500">
                    <th className="pb-3 font-medium sticky top-0 bg-gray-800">Date</th>
                    <th className="pb-3 font-medium sticky top-0 bg-gray-800">Player</th>
                    <th className="pb-3 font-medium sticky top-0 bg-gray-800">Prop</th>
                    <th className="pb-3 font-medium sticky top-0 bg-gray-800">Line</th>
                    <th className="pb-3 font-medium text-center sticky top-0 bg-gray-800">Actual</th>
                    <th className="pb-3 font-medium text-right sticky top-0 bg-gray-800">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice().reverse().map((log, i) => (
                    <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/20">
                      <td className="py-3 font-mono">{log.date}</td>
                      <td className="py-3 font-bold text-white">{log.player_name}</td>
                      <td className="py-3 capitalize">{log.stat_type.replace('_', ' ')}</td>
                      <td className="py-3">{log.line}</td>
                      <td className="py-3 text-center font-mono text-blue-400">{log.actual}</td>
                      <td className="py-3 text-right">
                        <span className={`px-2 py-1 rounded text-xs font-bold ${log.result === 'Win' ? 'bg-emerald-500/20 text-emerald-400' : log.result === 'Loss' ? 'bg-red-500/20 text-red-400' : 'bg-gray-600 text-gray-300'}`}>
                          {log.result}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}