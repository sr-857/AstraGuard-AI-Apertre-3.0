'use client';

import React, { useState } from 'react';
import { Bell, Info, AlertTriangle, CheckCircle, Shield, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface SystemEvent {
    id: string;
    type: 'INFO' | 'SUCCESS' | 'WARNING' | 'SECURITY';
    title: string;
    message: string;
    timestamp: string;
}

const MOCK_EVENTS: SystemEvent[] = [
    { id: '1', type: 'SUCCESS', title: 'Deployment successful', message: 'Satellite AG-42 orbital insertion confirmed.', timestamp: '12:45:01' },
    { id: '2', type: 'SECURITY', title: 'New clearance granted', message: 'Operator SIGMA granted Level 2 access.', timestamp: '12:48:22' },
    { id: '3', type: 'INFO', title: 'Uplink established', message: 'Ground station HOUSTON signal strength nominal.', timestamp: '12:50:05' },
    { id: '4', type: 'WARNING', title: 'Solar flare detected', message: 'Expected radiation spike in North sector.', timestamp: '13:02:15' },
];

export const NotificationCenter: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [events] = useState<SystemEvent[]>(MOCK_EVENTS);
    const [hasNew, setHasNew] = useState(true);

    const getIcon = (type: string) => {
        switch (type) {
            case 'SUCCESS': return <CheckCircle className="text-green-400" size={16} />;
            case 'WARNING': return <AlertTriangle className="text-yellow-400" size={16} />;
            case 'SECURITY': return <Shield className="text-cyan-400" size={16} />;
            default: return <Info className="text-blue-400" size={16} />;
        }
    };

    return (
        <div className="relative z-50">
            <button
                onClick={() => { setIsOpen(!isOpen); setHasNew(false); }}
                className={`p-2 rounded-full border transition-all ${hasNew
                    ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400 animate-pulse animate-glow'
                    : 'border-slate-800 bg-slate-900/50 text-slate-400 hover:text-slate-100 hover:border-slate-700'
                    }`}
            >
                <Bell size={20} />
            </button>

            <AnimatePresence>
                {isOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsOpen(false)}
                            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
                        />
                        <motion.div
                            initial={{ x: '100%' }}
                            animate={{ x: 0 }}
                            exit={{ x: '100%' }}
                            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                            className="fixed top-0 right-0 h-screen w-80 bg-slate-950/95 backdrop-blur-2xl border-l border-slate-800 shadow-2xl z-50 flex flex-col"
                        >
                            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                                <div className="flex items-center gap-3">
                                    <div className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                                    <h2 className="text-sm font-bold tracking-[0.2em] text-cyan-400 uppercase">System Log v2.0</h2>
                                </div>
                                <button onClick={() => setIsOpen(false)} className="text-slate-500 hover:text-white transition-colors">
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-slate-800">
                                {events.map((event) => (
                                    <motion.div
                                        key={event.id}
                                        layout
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="p-4 rounded-sm bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all group"
                                    >
                                        <div className="flex items-start gap-4">
                                            <div className="mt-1">{getIcon(event.type)}</div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex justify-between items-center mb-1">
                                                    <span className="text-[10px] font-mono text-slate-500">{event.timestamp}</span>
                                                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border ${event.type === 'SUCCESS' ? 'border-green-500/20 text-green-500' :
                                                        event.type === 'WARNING' ? 'border-yellow-500/20 text-yellow-500' :
                                                            event.type === 'SECURITY' ? 'border-cyan-500/20 text-cyan-500' :
                                                                'border-blue-500/20 text-blue-500'
                                                        }`}>
                                                        {event.type}
                                                    </span>
                                                </div>
                                                <h3 className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors uppercase tracking-wider">{event.title}</h3>
                                                <p className="text-[11px] text-slate-400 leading-relaxed mt-1">{event.message}</p>
                                            </div>
                                        </div>
                                    </motion.div>
                                ))}
                            </div>

                            <div className="p-4 border-t border-slate-800 bg-slate-900/30">
                                <button className="w-full py-2 text-[10px] font-bold text-slate-500 hover:text-cyan-400 transition-all uppercase tracking-widest text-center border border-dashed border-slate-800 rounded-sm hover:border-cyan-500/50">
                                    Archive All Log Entries
                                </button>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};
