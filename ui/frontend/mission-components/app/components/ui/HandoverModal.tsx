'use client';

import React, { useMemo } from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { X, Clipboard, ArrowRight, Shield, AlertCircle, FileText } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

export const HandoverModal: React.FC<Props> = ({ isOpen, onClose }) => {
    const { state, annotations } = useDashboard();

    const handoverData = useMemo(() => {
        const criticalAnomalies = state.mission?.anomalies?.filter(a => a.severity === 'Critical') || [];
        const recentNotes = annotations.slice(0, 5);
        const activePhase = state.mission?.phases?.find(p => p.isActive);
        const missionName = (state.mission as any)?.name || activePhase?.name || 'ASTRA_GUARD_MISSION';
        const timestamp = new Date().toLocaleString();

        return {
            missionName,
            timestamp,
            criticalAnomalies,
            recentNotes,
            uptime: '99.98%',
            operator: 'SIGMA'
        };
    }, [state.mission, annotations]);

    if (!isOpen) return null;

    return (
        <AnimatePresence>
            <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={onClose}
                    className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                />

                <motion.div
                    initial={{ scale: 0.9, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.9, opacity: 0, y: 20 }}
                    className="relative w-full max-w-2xl bg-slate-950 border border-slate-800 shadow-2xl rounded-sm overflow-hidden flex flex-col max-h-[80vh]"
                >
                    {/* Header */}
                    <div className="p-6 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                                <Clipboard size={20} />
                            </div>
                            <div>
                                <h2 className="text-sm font-bold text-slate-100 uppercase tracking-[0.2em]">Operational Handover</h2>
                                <p className="text-[10px] text-slate-400 font-mono mt-0.5">TRANSITION_LOG // {handoverData.timestamp}</p>
                            </div>
                        </div>
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
                            <X size={20} />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-800">
                        {/* Quick Stats */}
                        <div className="grid grid-cols-3 gap-4">
                            <div className="p-3 bg-slate-900/30 border border-slate-800 rounded-sm">
                                <div className="text-[10px] text-slate-500 uppercase mb-1 font-bold">Mission</div>
                                <div className="text-xs font-mono text-cyan-400 truncate">{handoverData.missionName}</div>
                            </div>
                            <div className="p-3 bg-slate-900/30 border border-slate-800 rounded-sm">
                                <div className="text-[10px] text-slate-500 uppercase mb-1 font-bold">Sys Availability</div>
                                <div className="text-xs font-mono text-green-400">{handoverData.uptime}</div>
                            </div>
                            <div className="p-3 bg-slate-900/30 border border-slate-800 rounded-sm">
                                <div className="text-[10px] text-slate-500 uppercase mb-1 font-bold">Outbound Op</div>
                                <div className="text-xs font-mono text-slate-300">{handoverData.operator}</div>
                            </div>
                        </div>

                        {/* Critical Anomalies */}
                        <section className="space-y-3">
                            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <Shield size={12} className="text-red-500" />
                                Open Critical Items ({handoverData.criticalAnomalies.length})
                            </h3>
                            <div className="space-y-2">
                                {handoverData.criticalAnomalies.length > 0 ? (
                                    handoverData.criticalAnomalies.map((an, i) => (
                                        <div key={i} className="p-3 bg-red-500/5 border border-red-500/10 rounded-sm flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <AlertCircle size={14} className="text-red-400" />
                                                <div>
                                                    <div className="text-xs font-bold text-slate-200 uppercase">{an.satellite}</div>
                                                    <div className="text-[10px] text-red-400 font-mono">{an.metric} // {an.value}</div>
                                                </div>
                                            </div>
                                            <span className="text-[9px] text-slate-600 font-mono uppercase">Unresolved</span>
                                        </div>
                                    ))
                                ) : (
                                    <div className="p-4 border border-dashed border-slate-800 rounded-sm text-center text-[10px] text-slate-500">
                                        No critical open items reported.
                                    </div>
                                )}
                            </div>
                        </section>

                        {/* Recent Handover Notes */}
                        <section className="space-y-3">
                            <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <FileText size={12} className="text-yellow-500" />
                                Operator Notes Summary
                            </h3>
                            <div className="space-y-2">
                                {handoverData.recentNotes.length > 0 ? (
                                    handoverData.recentNotes.map((note, i) => (
                                        <div key={i} className="p-3 bg-slate-900 border border-slate-800 rounded-sm">
                                            <div className="flex justify-between items-center mb-1">
                                                <span className="text-[9px] font-bold text-yellow-500 uppercase">{note.author}</span>
                                                <span className="text-[9px] font-mono text-slate-600">{note.timestamp}</span>
                                            </div>
                                            <p className="text-[11px] text-slate-300 leading-relaxed italic">"{note.text}"</p>
                                        </div>
                                    ))
                                ) : (
                                    <div className="p-4 border border-dashed border-slate-800 rounded-sm text-center text-[10px] text-slate-500">
                                        No operational notes left for this shift.
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>

                    {/* Footer */}
                    <div className="p-6 border-t border-slate-800 bg-slate-900/50 flex gap-4">
                        <button
                            onClick={onClose}
                            className="px-4 py-2 border border-slate-800 rounded-sm text-[10px] font-bold text-slate-400 hover:text-white hover:border-slate-700 transition-all uppercase"
                        >
                            Cancel
                        </button>
                        <button className="flex-1 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-sm text-[10px] font-bold text-white transition-all uppercase flex items-center justify-center gap-2">
                            Confirm Transition & Copy to Clipboard
                            <ArrowRight size={14} />
                        </button>
                    </div>
                </motion.div>
            </div>
        </AnimatePresence>
    );
};
