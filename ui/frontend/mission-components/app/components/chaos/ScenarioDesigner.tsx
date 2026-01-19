'use client';

import React, { useState } from 'react';
import { motion, Reorder } from 'framer-motion';
import { Play, Plus, Trash2, Clock, MoveVertical, Zap } from 'lucide-react';

interface ChaosEvent {
    id: string;
    type: 'network_latency' | 'model_loader' | 'redis_failure' | 'cpu_spike';
    duration: number;
    delay: number;
}

interface Props {
    onExecute: (sequence: ChaosEvent[]) => void;
}

export const ScenarioDesigner: React.FC<Props> = ({ onExecute }) => {
    const [sequence, setSequence] = useState<ChaosEvent[]>([]);
    const [isExecuting, setIsExecuting] = useState(false);

    const addEvent = () => {
        const newEvent: ChaosEvent = {
            id: Math.random().toString(36).substr(2, 9),
            type: 'network_latency',
            duration: 10,
            delay: 2
        };
        setSequence([...sequence, newEvent]);
    };

    const removeEvent = (id: string) => {
        setSequence(sequence.filter(e => e.id !== id));
    };

    const updateEvent = (id: string, updates: Partial<ChaosEvent>) => {
        setSequence(sequence.map(e => e.id === id ? { ...e, ...updates } : e));
    };

    const handleRun = async () => {
        setIsExecuting(true);
        onExecute(sequence);
        // Simulation of execution progress
        setTimeout(() => setIsExecuting(false), 3000);
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                    <Zap size={12} className="text-amber-400" />
                    Scenario Designer
                </h3>
                <button
                    onClick={addEvent}
                    className="flex items-center gap-1.5 px-2 py-1 bg-slate-800 border border-slate-700 rounded-sm text-[10px] font-bold text-slate-300 hover:text-white hover:border-slate-600 transition-all"
                >
                    <Plus size={12} /> ADD STEP
                </button>
            </div>

            <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-2 min-h-[120px]">
                {sequence.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center py-8 text-slate-600 space-y-2">
                        <div className="w-10 h-10 rounded-full border border-dashed border-slate-800 flex items-center justify-center text-[20px]">
                            ⛓️
                        </div>
                        <p className="text-[10px] uppercase font-mono italic">No events in sequence</p>
                    </div>
                ) : (
                    <Reorder.Group axis="y" values={sequence} onReorder={setSequence} className="space-y-2">
                        {sequence.map((event) => (
                            <Reorder.Item key={event.id} value={event}>
                                <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-2 rounded-sm group">
                                    <div className="cursor-grab active:cursor-grabbing text-slate-700">
                                        <MoveVertical size={14} />
                                    </div>

                                    <select
                                        value={event.type}
                                        onChange={(e) => updateEvent(event.id, { type: e.target.value as any })}
                                        className="bg-slate-800 border-none text-[10px] font-mono text-amber-400 focus:ring-0 p-1 rounded-sm"
                                    >
                                        <option value="network_latency">NETWORK_LATENCY</option>
                                        <option value="model_loader">AI_MODEL_FAILURE</option>
                                        <option value="redis_failure">DB_CONNECTION_DROP</option>
                                        <option value="cpu_spike">CPU_V3_RELOAD</option>
                                    </select>

                                    <div className="flex items-center gap-2 flex-1">
                                        <div className="flex items-center gap-1 text-[9px] text-slate-500 font-mono">
                                            <Clock size={10} />
                                            <input
                                                type="number"
                                                value={event.duration}
                                                onChange={(e) => updateEvent(event.id, { duration: parseInt(e.target.value) })}
                                                className="w-8 bg-transparent border-b border-slate-800 focus:border-amber-500/50 text-slate-300 outline-none text-center"
                                            />s
                                        </div>
                                        <div className="text-[9px] text-slate-700 px-1">DELAY:</div>
                                        <div className="flex items-center gap-1 text-[9px] text-slate-500 font-mono">
                                            <input
                                                type="number"
                                                value={event.delay}
                                                onChange={(e) => updateEvent(event.id, { delay: parseInt(e.target.value) })}
                                                className="w-8 bg-transparent border-b border-slate-800 focus:border-cyan-500/50 text-slate-300 outline-none text-center"
                                            />s
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => removeEvent(event.id)}
                                        className="p-1 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <Trash2 size={12} />
                                    </button>
                                </div>
                            </Reorder.Item>
                        ))}
                    </Reorder.Group>
                )}
            </div>

            <button
                onClick={handleRun}
                disabled={sequence.length === 0 || isExecuting}
                className={`w-full py-2 rounded-sm text-[10px] font-black uppercase tracking-[0.3em] flex items-center justify-center gap-2 transition-all
          ${isExecuting
                        ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse cursor-wait'
                        : 'bg-red-600 hover:bg-red-500 text-white shadow-[0_0_15px_rgba(220,38,38,0.2)]'}`}
            >
                {isExecuting ? 'SEQUENCING_OUTPUT...' : <>
                    <Play size={14} fill="currentColor" /> EXECUTE_CHAOS_STORM
                </>}
            </button>
        </div>
    );
};
