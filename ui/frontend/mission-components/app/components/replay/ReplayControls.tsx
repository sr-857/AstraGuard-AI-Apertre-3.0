import React, { useState, useEffect } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { SimulationModal } from './SimulationModal';
import { GitBranch } from 'lucide-react';

export const ReplayControls: React.FC = () => {
    const { isReplayMode, toggleReplayMode, replayProgress, setReplayProgress, isPlaying, togglePlay } = useDashboard();
    const [isSimulationOpen, setIsSimulationOpen] = useState(false);

    // Auto-play effect
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isReplayMode && isPlaying) {
            interval = setInterval(() => {
                setReplayProgress((prev: number) => {
                    if (prev >= 100) return 0; // Loop
                    return prev + 1; // Advance 1% (~0.6s of real data)
                });
            }, 600); // Update speed
        }
        return () => clearInterval(interval);
    }, [isReplayMode, isPlaying, setReplayProgress]);

    if (!isReplayMode) {
        return null;
    }

    return (
        <div className="flex items-center gap-3 bg-slate-900 border border-indigo-500/50 p-1.5 px-3 rounded shadow-[0_0_15px_rgba(99,102,241,0.3)] animate-in fade-in slide-in-from-top-2">
            <SimulationModal
                isOpen={isSimulationOpen}
                onClose={() => setIsSimulationOpen(false)}
                historicalPoint={replayProgress}
            />

            <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest animate-pulse mr-1">R E P L A Y</span>

            <button
                onClick={togglePlay}
                className="w-6 h-6 flex items-center justify-center rounded bg-indigo-500/20 hover:bg-indigo-500 hover:text-white text-indigo-400 transition-colors"
                title={isPlaying ? "Pause" : "Play"}
            >
                {isPlaying ? '⏸' : '▶'}
            </button>

            <input
                type="range"
                min="0"
                max="100"
                value={replayProgress}
                onChange={(e) => setReplayProgress(Number(e.target.value))}
                className="w-32 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />

            <span className="font-mono text-xs text-indigo-300 w-8 text-right">
                {replayProgress}%
            </span>

            <div className="h-4 w-px bg-slate-800 mx-1" />

            <button
                onClick={() => setIsSimulationOpen(true)}
                className="flex items-center gap-2 px-2 py-1 bg-indigo-500/10 border border-indigo-500/30 hover:bg-indigo-500 hover:text-white rounded-sm text-[10px] font-bold text-indigo-400 transition-all uppercase tracking-tighter"
                title="Branch & Simulate"
            >
                <GitBranch size={12} />
                <span className="hidden lg:inline">Simulation</span>
            </button>

            <button
                onClick={toggleReplayMode}
                className="ml-1 w-5 h-5 flex items-center justify-center text-slate-500 hover:text-red-400 transition-colors"
                title="Exit Replay"
            >
                ✕
            </button>
        </div>
    );
};
