import { useState, useEffect } from 'react';
import PropCard from './components/PropCard';
import { Info } from 'lucide-react';

// Defining this outside the component prevents the infinite loop!
const EMPTY_ARRAY = new Array();

export default function App() {
  const propsState = useState(new Array());
  const props = propsState.at(0);
  const setProps = propsState.at(1);

  const loadingState = useState(true);
  const loading = loadingState.at(0);
  const setLoading = loadingState.at(1);

  const showInfoState = useState(false);
  const showInfo = showInfoState.at(0);
  const setShowInfo = showInfoState.at(1);

  useEffect(() => {
    // The timestamp forces the browser to fetch the newest file, bypassing the cache
    fetch('./predictions.json?t=' + new Date().getTime())
   .then((res) => res.json())
   .then((data) => {
        setProps(data);
        setLoading(false);
      })
   .catch((err) => {
        console.error("Failed to load predictions", err);
        setLoading(false);
      });
  }, EMPTY_ARRAY);

  // Slice the array to get only the top 5 and bottom 5 props
  const topProps = props.slice(0, 5);
  const bottomProps = props.length > 5? props.slice(-5) : new Array();

  return (
    <div className="min-h-screen bg-gray-900 p-6">
      <header className="mb-8 border-b border-gray-700 pb-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-3xl font-bold text-emerald-400">MLB Prop Prediction Engine</h1>
            <p className="text-gray-400">Automated Expected Value against Sleeper Picks API</p>
            <p className="text-sm text-emerald-500 font-semibold mt-2">
              Data for: {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
          </div>
          <button
            onClick={() => setShowInfo(!showInfo)}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-blue-400 px-4 py-2 rounded-lg border border-gray-600 transition"
          >
            <Info size={20} />
            <span>Strategy Guide</span>
          </button>
        </div>

        {showInfo? (
          <div className="p-4 bg-blue-900/30 border border-blue-800 rounded-xl text-blue-200 text-sm mb-4">
            <h3 className="font-bold text-blue-400 mb-2 text-base">How to Spot Value</h3>
            <ul className="list-disc pl-5 space-y-2">
              <li><strong>What is EV?</strong> Expected Value (EV) represents your average mathematical profit per bet over time. It identifies situations where the true probability is better than the sportsbook's payout odds.</li>
              <li><strong>The Target (+EV):</strong> You should target the Top 5 props on the dashboard, ideally looking for anything above <strong>+3.00% EV</strong>. These provide enough of a mathematical edge to overcome variance.</li>
              <li><strong>The Avoid List (-EV):</strong> The Bottom 5 props represent the worst mathematical bets on the board. Avoid including these in any parlay or entry, as the sportsbook holds a massive edge over you.</li>
              <li><strong>Sleeper Multipliers:</strong> Because Sleeper requires multiple picks, pair 2 or 3 of the highest +EV props together to geometrically maximize your long-term returns.</li>
            </ul>
          </div>
        ) : null}
      </header>

      {loading? (
        <p className="text-gray-400">Running Monte Carlo Simulations...</p>
      ) : (
        <div className="space-y-10">
          <section>
            <h2 className="text-2xl font-bold text-white mb-4 border-l-4 border-emerald-500 pl-3">Top 5 Value Bets (Target)</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {topProps.map((prop, index) => (
                <PropCard key={'top-'+index} data={prop} />
              ))}
            </div>
          </section>

          {bottomProps.length > 0? (
            <section>
              <h2 className="text-2xl font-bold text-white mb-4 border-l-4 border-red-500 pl-3">Bottom 5 Plays (Avoid)</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 opacity-75">
                {bottomProps.map((prop, index) => (
                  <PropCard key={'bottom-'+index} data={prop} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}