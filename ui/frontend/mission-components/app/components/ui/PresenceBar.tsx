'use client';

import React from 'react';
import { useDashboard } from '../../context/DashboardContext';
import { motion, AnimatePresence } from 'framer-motion';

export const PresenceBar: React.FC = () => {
    const { presence } = useDashboard();

    return (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900/40 border border-slate-800 rounded-full backdrop-blur-md">
            <div className="flex -space-x-2 overflow-hidden">
                <AnimatePresence>
                    {presence.map((operator, i) => (
                        <motion.div
                            key={operator.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="relative group"
                        >
                            <div
                                className="inline-flex items-center justify-center w-7 h-7 rounded-full border-2 border-slate-950 bg-slate-800 text-[10px] font-bold text-cyan-400 cursor-help transition-transform hover:scale-110 hover:z-10"
                                title={`${operator.name} | View: ${operator.activePanel}`}
                            >
                                {operator.avatar}
                            </div>
                            {/* Tooltip on hover */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max px-2 py-1 bg-slate-900 border border-slate-700 rounded text-[9px] text-slate-300 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                                <span className="font-bold text-white uppercase">{operator.name}</span>
                                <span className="mx-1 text-slate-600">|</span>
                                <span className="italic">{operator.activePanel}</span>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>
            <div className="h-4 w-px bg-slate-700 mx-1" />
            <div className="flex items-center gap-1.5 pr-1">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
                <span className="text-[10px] font-mono text-slate-400 uppercase tracking-tighter">
                    {presence.length} OP_ACTIVE
                </span>
            </div>
        </div>
    );
};
