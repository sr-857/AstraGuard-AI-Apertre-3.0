'use client';

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Activity, Brain, Zap, Cpu, ShieldCheck, Gauge } from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';

export const NeuralHealthMonitor: React.FC = () => {
    const { aiHealth } = useDashboard();

    // Generate pseudo-random neural nodes for the graph
    const nodes = useMemo(() => {
        return Array.from({ length: 15 }).map((_, i) => ({
            id: i,
            x: 20 + Math.random() * 60, // 20% to 80% range
            y: 20 + Math.random() * 60,
            size: 2 + Math.random() * 4
        }));
    }, []);

    // Generate connections between nearby nodes
    const connections = useMemo(() => {
        const lines = [];
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dist = Math.sqrt(
                    Math.pow(nodes[i].x - nodes[j].x, 2) +
                    Math.pow(nodes[i].y - nodes[j].y, 2)
                );
                if (dist < 25) {
                    lines.push({ n1: nodes[i], n2: nodes[j] });
                }
            }
        }
        return lines;
    }, [nodes]);

    return (
        <div className="bg-slate-950 border border-indigo-500/20 rounded-lg overflow-hidden flex flex-col h-full group">
            {/* Header */}
            <div className="p-4 border-b border-indigo-500/10 bg-indigo-500/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded bg-indigo-500/10 text-indigo-400 group-hover:animate-pulse">
                        <Brain size={20} />
                    </div>
                    <div>
                        <h3 className="text-xs font-black text-slate-100 uppercase tracking-widest">Neural Health Alpha</h3>
                        <p className="text-[10px] text-indigo-400 font-mono mt-0.5">SENTINEL_AI // COGNITIVE_THREAD_0</p>
                    </div>
                </div>
                <div className="px-2 py-1 rounded border border-emerald-500/20 bg-emerald-500/5 text-emerald-400 text-[9px] font-bold uppercase tracking-tighter">
                    STATUS: OPTIMAL
                </div>
            </div>

            <div className="flex-1 p-6 grid grid-cols-1 lg:grid-cols-2 gap-6 items-center">
                {/* Neural Visualization */}
                <div className="relative aspect-square max-h-[300px] bg-slate-900/40 rounded-full border border-indigo-500/10 p-4 overflow-hidden self-center mx-auto">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(99,102,241,0.1)_0%,transparent_70%)]" />

                    <svg viewBox="0 0 100 100" className="w-full h-full relative z-10">
                        {/* Synaptic Connections */}
                        {connections.map((line, idx) => (
                            <motion.line
                                key={`line-${idx}`}
                                x1={line.n1.x}
                                y1={line.n1.y}
                                x2={line.n2.x}
                                y2={line.n2.y}
                                stroke="rgba(99, 102, 241, 0.2)"
                                strokeWidth="0.5"
                                initial={{ opacity: 0.1 }}
                                animate={{
                                    opacity: [0.1, 0.4, 0.1],
                                    strokeWidth: [0.5, 1, 0.5]
                                }}
                                transition={{
                                    duration: 2 + Math.random() * 3,
                                    repeat: Infinity,
                                    delay: Math.random() * 2
                                }}
                            />
                        ))}

                        {/* Neural Nodes */}
                        {nodes.map((node) => (
                            <motion.circle
                                key={node.id}
                                cx={node.x}
                                cy={node.y}
                                r={node.size / 2}
                                fill="currentColor"
                                className="text-indigo-400"
                                initial={{ scale: 1 }}
                                animate={{
                                    scale: [1, 1.5, 1],
                                    opacity: [0.4, 1, 0.4],
                                    filter: ['blur(0px)', 'blur(1px)', 'blur(0px)']
                                }}
                                transition={{
                                    duration: 1.5 + (100 / aiHealth.load),
                                    repeat: Infinity,
                                    delay: node.id * 0.1
                                }}
                            />
                        ))}

                        {/* Firing Synapses */}
                        <motion.circle
                            r="1"
                            fill="#818cf8"
                            initial={{ cx: nodes[0].x, cy: nodes[0].y }}
                            animate={{
                                cx: nodes.map(n => n.x),
                                cy: nodes.map(n => n.y),
                            }}
                            transition={{
                                duration: 10,
                                repeat: Infinity,
                                ease: "linear"
                            }}
                            className="drop-shadow-[0_0_8px_rgba(129,140,248,0.8)]"
                        />
                    </svg>

                    {/* Central Load Gauge Overlay */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="text-center">
                            <motion.div
                                className="text-3xl font-black text-white"
                                animate={{ opacity: [0.8, 1, 0.8] }}
                                transition={{ duration: 1, repeat: Infinity }}
                            >
                                {Math.round(aiHealth.load)}%
                            </motion.div>
                            <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mt-1">Cognitive Load</div>
                        </div>
                    </div>
                </div>

                {/* Metrics Grid */}
                <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                            <div className="flex items-center gap-2 text-indigo-400 mb-1">
                                <Activity size={12} />
                                <span className="text-[9px] font-bold uppercase tracking-wider">Throughput</span>
                            </div>
                            <div className="text-lg font-mono text-slate-100">{aiHealth.synapticThroughput.toLocaleString()}</div>
                            <div className="text-[8px] text-slate-500 uppercase">nodes / second</div>
                        </div>
                        <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                            <div className="flex items-center gap-2 text-emerald-400 mb-1">
                                <ShieldCheck size={12} />
                                <span className="text-[9px] font-bold uppercase tracking-wider">Confidence</span>
                            </div>
                            <div className="text-lg font-mono text-slate-100">{(aiHealth.confidence * 100).toFixed(1)}%</div>
                            <div className="text-[8px] text-slate-500 uppercase">Validation Score</div>
                        </div>
                    </div>

                    <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 text-amber-400">
                                <Zap size={14} />
                                <span className="text-[10px] font-bold uppercase tracking-widest">Context Window Focus</span>
                            </div>
                            <span className="text-[10px] font-mono text-slate-500 text-right">{aiHealth.attentionFocus}</span>
                        </div>
                        <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                                initial={{ width: "0%" }}
                                animate={{ width: `${aiHealth.load}%` }}
                                transition={{ type: "spring", damping: 20 }}
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-3 p-3 bg-indigo-500/5 border border-indigo-500/10 rounded-lg">
                        <Cpu size={16} className="text-indigo-400" />
                        <div>
                            <div className="text-[10px] font-bold text-slate-300">Active Synthetic Neurons</div>
                            <div className="text-xs font-mono text-indigo-300">{aiHealth.activeNeurons.toLocaleString()} Units</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Terminal Feed */}
            <div className="bg-black/40 p-3 h-24 border-t border-indigo-500/10 font-mono text-[9px] text-indigo-400/60 overflow-hidden relative">
                <div className="animate-pulse absolute top-3 right-3 text-indigo-500">REC_LIVE</div>
                <div className="space-y-1">
                    <div>[SENTINEL_AI] ANALYZING TELEMETRY STREAM #A1-992...</div>
                    <div className="opacity-80">[PROCESSOR] CALCULATING ORBITAL DEVIANCE VECTORS...</div>
                    <div className="opacity-60">[NEURAL] SYNAPTIC MAPPING COMPLETE (0.002ms)</div>
                    <div className="opacity-40">[SENTINEL_AI] ALL SYSTEMS NOMINAL. CONTINUING MONITORING...</div>
                </div>
            </div>
        </div>
    );
};
