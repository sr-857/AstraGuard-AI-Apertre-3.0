'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, GitBranch, Play, CheckCircle2, TrendingUp } from 'lucide-react';

interface Props {
    isOpen: boolean;
    onClose: () => void;
    historicalPoint: number;
}

export const SimulationModal: React.FC<Props> = ({ isOpen, onClose, historicalPoint }) => {
    const [isSimulating, setIsSimulating] = useState(false);
    const [showResult, setShowResult] = useState(false);

    // Mock comparison data
    const simulationData = useMemo(() => {
        const data = [];
        for (let i = 0; i < 20; i++) {
            const base = 40 + Math.random() * 20;
            data.push({
                time: i,
                historical: base + (i > 5 ? 30 : 0),
                simulated: base + (i > 5 ? Math.max(0, 30 - (i - 5) * 6) : 0)
            });
        }
        return data;
    }, []);

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                    className="absolute inset-0 bg-black/80 backdrop-blur-md"
                />

                <motion.div
                    initial={{ scale: 0.9, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.9, opacity: 0, y: 20 }}
                    className="relative w-full max-w-3xl bg-slate-950 border border-indigo-500/30 shadow-[0_0_50px_rgba(99,102,241,0.2)] rounded-sm overflow-hidden flex flex-col max-h-[90vh]"
                >
                    {/* Header */}
                    <div className="p-6 border-b border-slate-800 bg-indigo-500/5 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                                <GitBranch size={20} />
                            </div>
                            <div>
                                <h2 className="text-sm font-bold text-slate-100 uppercase tracking-[0.2em]">What-If Simulation</h2>
                                <p className="text-[10px] text-slate-400 font-mono mt-0.5">BRANCH_POINT // T-{historicalPoint}% // STATUS: STABLE</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
                            <X size={20} />
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-8 space-y-8">
                        <div className="bg-slate-900/50 border border-slate-800 rounded p-6 relative overflow-hidden">
                            <div className="absolute top-0 right-0 p-2 opacity-10">
                                <TrendingUp size={80} />
                            </div>
                            <h3 className="text-xs font-bold text-slate-300 uppercase mb-4 tracking-widest">Select Intervention Strategy</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <button className="p-4 bg-slate-800/50 border border-slate-700 rounded hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all text-left group">
                                    <div className="text-[10px] font-bold text-indigo-400 mb-1">STRATEGY_A</div>
                                    <div className="text-xs text-white mb-2">Automated Power Cycle</div>
                                    <div className="text-[9px] text-slate-500 font-mono">EST_RECOVERY: 45s</div>
                                </button>
                                <button className="p-4 bg-slate-800/50 border border-slate-700 rounded hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all text-left group">
                                    <div className="text-[10px] font-bold text-emerald-400 mb-1">STRATEGY_B</div>
                                    <div className="text-xs text-white mb-2">Frequency Shift & Rebind</div>
                                    <div className="text-[9px] text-slate-500 font-mono">EST_RECOVERY: 12s</div>
                                </button>
                            </div>
                        </div>

                        {showResult ? (
                            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-widest">Simulation Outcome Delta</h3>
                                    <div className="flex items-center gap-4 text-[10px] font-mono">
                                        <div className="flex items-center gap-1.5"><div className="w-2 h-2 bg-slate-600 rounded-full" /> HISTORICAL</div>
                                        <div className="flex items-center gap-1.5"><div className="w-2 h-2 bg-indigo-500 rounded-full" /> SIMULATED</div>
                                    </div>
                                </div>

                                <div className="h-40 flex items-end gap-1 px-2 border-l border-b border-slate-800 relative">
                                    {simulationData.map((d, i) => (
                                        <div key={i} className="flex-1 flex flex-col items-center justify-end h-full gap-0.5">
                                            <div className="w-full bg-indigo-500/40 rounded-t-[1px]" style={{ height: `${d.simulated}%` }} />
                                            <div className="w-full bg-slate-800 rounded-t-[1px]" style={{ height: `${d.historical}%` }} />
                                        </div>
                                    ))}
                                    <div className="absolute top-1/4 left-1/4 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded text-[10px] text-emerald-400 font-bold backdrop-blur">
                                        +72% FASTER RECOVERY
                                    </div>
                                </div>

                                <div className="grid grid-cols-3 gap-4">
                                    <div className="p-4 bg-slate-900 border border-slate-800 rounded">
                                        <div className="text-[10px] text-slate-500 uppercase mb-1">Time Saved</div>
                                        <div className="text-lg font-mono text-emerald-400">00:42.5</div>
                                    </div>
                                    <div className="p-4 bg-slate-900 border border-slate-800 rounded">
                                        <div className="text-[10px] text-slate-500 uppercase mb-1">Risk Profile</div>
                                        <div className="text-lg font-mono text-amber-400">LOW</div>
                                    </div>
                                    <div className="p-4 bg-slate-900 border border-slate-800 rounded">
                                        <div className="text-[10px] text-slate-500 uppercase mb-1">Success Prob</div>
                                        <div className="text-lg font-mono text-cyan-400">94.2%</div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center py-12 space-y-6">
                                <div className={`p-8 rounded-full border border-dashed border-slate-800 transition-all ${isSimulating ? 'animate-spin-slow' : ''}`}>
                                    <div className="w-16 h-16 rounded-full bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400">
                                        <Play fill="currentColor" size={32} className={isSimulating ? 'animate-pulse' : ''} />
                                    </div>
                                </div>
                                <div className="text-center space-y-2">
                                    <div className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em]">Ready for Prediction Engine</div>
                                    <p className="text-[10px] text-slate-600 max-w-sm font-mono uppercase">Analyzing historical anomaly state... Branched outcome will be computed using Sentinel-V3 Simulation.</p>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="p-6 border-t border-slate-800 bg-slate-900/50 flex gap-4">
                        <button
                            onClick={onClose}
                            className="px-6 py-2 border border-slate-800 rounded text-[10px] font-bold text-slate-400 hover:text-white uppercase transition-all"
                        >
                            Close Engine
                        </button>
                        {!showResult && (
                            <button
                                onClick={() => {
                                    setIsSimulating(true);
                                    setTimeout(() => {
                                        setIsSimulating(false);
                                        setShowResult(true);
                                    }, 2000);
                                }}
                                disabled={isSimulating}
                                className="flex-1 px-6 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded text-[10px] font-bold text-white uppercase transition-all flex items-center justify-center gap-2 tracking-[0.2em]"
                            >
                                {isSimulating ? 'RUNNING_BRANCH_SIM...' : 'RUN_PROACTIVE_SIMULATION'}
                            </button>
                        )}
                        {showResult && (
                            <button className="flex-1 px-6 py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-[10px] font-bold text-white uppercase transition-all flex items-center justify-center gap-2 tracking-[0.2em]">
                                <CheckCircle2 size={14} /> ADOPT_SIMULATED_PATH
                            </button>
                        )}
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    );
};
