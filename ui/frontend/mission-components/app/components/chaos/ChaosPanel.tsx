"use client";

import React, { useState, useEffect } from 'react';
import { Bot, WifiOff, ServerCrash, Activity, Layers, Settings2 } from 'lucide-react';
import { ScenarioDesigner } from './ScenarioDesigner';
import { useDashboard } from '../../context/DashboardContext';

interface ChaosPanelProps {
    className?: string;
}

export const ChaosPanel: React.FC<ChaosPanelProps> = ({ className = "" }) => {
    const [activeFaults, setActiveFaults] = useState<Record<string, number>>({});
    const [isAdvancedMode, setIsAdvancedMode] = useState(false);
    const { registerChaosRun } = useDashboard();

    const fetchStatus = async () => {
        try {
            const res = await fetch('http://localhost:8002/api/v1/chaos/status');
            if (res.ok) {
                const data = await res.json();
                setActiveFaults(data.details || {});
            }
        } catch (e) {
            console.error("Failed to fetch chaos status", e);
        }
    };

    useEffect(() => {
        fetchStatus();
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    const injectFault = async (faultType: string, duration: number) => {
        try {
            await fetch('http://localhost:8002/api/v1/chaos/inject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fault_type: faultType, duration_seconds: duration })
            });
            registerChaosRun();
            await fetchStatus();
        } catch (e) {
            console.error("Failed to inject fault", e);
        }
    };

    const executeScenario = async (sequence: any[]) => {
        console.log("Executing Chaos Scenario:", sequence);
        for (const event of sequence) {
            await injectFault(event.type, event.duration);
            if (event.delay > 0) {
                await new Promise(r => setTimeout(r, event.delay * 1000));
            }
        }
    };

    return (
        <div className={`backdrop-blur-md bg-slate-900/40 border border-slate-700/50 rounded-xl p-6 flex flex-col gap-4 ${className}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                        <Bot className="w-5 h-5 text-red-400" />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-white tracking-tight">Chaos Engineering</h2>
                        <p className="text-[10px] text-slate-400 uppercase tracking-widest font-mono">Resilience Testing & Fault Injection</p>
                    </div>
                </div>

                <button
                    onClick={() => setIsAdvancedMode(!isAdvancedMode)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all text-[10px] font-bold uppercase
                        ${isAdvancedMode
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-500'
                            : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'}`}
                >
                    {isAdvancedMode ? <Layers size={12} /> : <Settings2 size={12} />}
                    {isAdvancedMode ? 'Scenario Mode' : 'Direct Inject'}
                </button>
            </div>

            {isAdvancedMode ? (
                <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                    <ScenarioDesigner onExecute={executeScenario} />
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-in fade-in slide-in-from-left-4 duration-300">
                    {/* Network Latency */}
                    <button
                        onClick={() => injectFault('network_latency', 10)}
                        disabled={!!activeFaults['network_latency']}
                        className={`relative group p-4 rounded-lg border transition-all duration-300 flex flex-col items-center gap-2
                ${activeFaults['network_latency']
                                ? 'bg-amber-500/10 border-amber-500/30 cursor-not-allowed'
                                : 'bg-slate-800/50 border-slate-700 hover:border-amber-500/50 hover:bg-slate-800'}`}
                    >
                        <WifiOff className={`w-6 h-6 ${activeFaults['network_latency'] ? 'text-amber-400 animate-pulse' : 'text-slate-400 group-hover:text-amber-400'}`} />
                        <span className="text-xs font-bold text-slate-200 uppercase tracking-tighter">Inject Latency</span>
                        <span className="text-[10px] text-slate-500 font-mono">10S_BURST</span>
                    </button>

                    {/* Model Failure */}
                    <button
                        onClick={() => injectFault('model_loader', 15)}
                        disabled={!!activeFaults['model_loader']}
                        className={`relative group p-4 rounded-lg border transition-all duration-300 flex flex-col items-center gap-2
                ${activeFaults['model_loader']
                                ? 'bg-red-500/10 border-red-500/30 cursor-not-allowed'
                                : 'bg-slate-800/50 border-slate-700 hover:border-red-500/50 hover:bg-slate-800'}`}
                    >
                        <Activity className={`w-6 h-6 ${activeFaults['model_loader'] ? 'text-red-400 animate-bounce' : 'text-slate-400 group-hover:text-red-400'}`} />
                        <span className="text-xs font-bold text-slate-200 uppercase tracking-tighter">Fail AI Model</span>
                        <span className="text-[10px] text-slate-500 font-mono">15S_SIG_DROP</span>
                    </button>

                    {/* Redis Failure */}
                    <button
                        onClick={() => injectFault('redis_failure', 20)}
                        disabled={!!activeFaults['redis_failure']}
                        className={`relative group p-4 rounded-lg border transition-all duration-300 flex flex-col items-center gap-2
                ${activeFaults['redis_failure']
                                ? 'bg-purple-500/10 border-purple-500/30 cursor-not-allowed'
                                : 'bg-slate-800/50 border-slate-700 hover:border-purple-500/50 hover:bg-slate-800'}`}
                    >
                        <ServerCrash className={`w-6 h-6 ${activeFaults['redis_failure'] ? 'text-purple-400 animate-pulse' : 'text-slate-400 group-hover:text-purple-400'}`} />
                        <span className="text-xs font-bold text-slate-200 uppercase tracking-tighter">Kill Redis</span>
                        <span className="text-[10px] text-slate-500 font-mono">20S_DB_ERR</span>
                    </button>
                </div>
            )}

            {/* Resilience Metrics Visualization */}
            <div className="mt-2 bg-slate-950/50 rounded-lg p-3 border border-slate-800 relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                <div className="flex justify-between items-center mb-2">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-[0.2em] flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                        SYSTEM_RECOVERY_TIME (REALTIME)
                    </span>
                    <span className="text-[10px] text-cyan-400 font-mono font-bold tracking-tighter">145MS_AVG</span>
                </div>
                <div className="h-10 flex items-end gap-1 px-1">
                    {[40, 65, 30, 80, 45, 60, 20, 90, 55, 35, 70, 50, 25, 65, 40, 55, 30, 75, 45, 60].map((h, i) => (
                        <div
                            key={i}
                            className={`flex-1 rounded-t-[1px] transition-all duration-500 ${h > 75 ? 'bg-red-500/40' : 'bg-cyan-500/20 group-hover:bg-cyan-500/40'}`}
                            style={{ height: `${h}%` }}
                        ></div>
                    ))}
                </div>
            </div>
        </div>
    );
};
