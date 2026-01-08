'use client';

import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ShieldAlert, Fingerprint, CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import { useDashboard } from '../../context/DashboardContext';

export const RemediationDrawer: React.FC = () => {
    const { activeRemediation, authorizeRemediation, cancelRemediation } = useDashboard();
    const [holdProgress, setHoldProgress] = useState(0);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    const isExecuting = activeRemediation?.status === 'authorized' || activeRemediation?.status === 'executing';
    const isCompleted = activeRemediation?.status === 'completed';

    const handleMouseDown = () => {
        if (isExecuting || isCompleted) return;

        const startTime = Date.now();
        const duration = 2000; // 2 seconds hold

        timerRef.current = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min((elapsed / duration) * 100, 100);
            setHoldProgress(progress);

            if (progress >= 100) {
                if (timerRef.current) clearInterval(timerRef.current);
                handleAuthorize();
            }
        }, 50);
    };

    const handleMouseUp = () => {
        if (timerRef.current) clearInterval(timerRef.current);
        if (holdProgress < 100) {
            setHoldProgress(0);
        }
    };

    const handleAuthorize = () => {
        if (!activeRemediation) return;
        authorizeRemediation(activeRemediation.id);
    };

    if (!activeRemediation) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ x: '100%' }}
                animate={{ x: 0 }}
                exit={{ x: '100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                className="fixed inset-y-0 right-0 w-[400px] bg-slate-950 border-l border-red-500/30 shadow-[-20px_0_50px_rgba(239,68,68,0.15)] z-[100] flex flex-col overflow-hidden"
            >
                {/* Tactical Header */}
                <div className="p-6 border-b border-red-500/20 bg-red-500/5 flex items-center justify-between relative">
                    <div className="absolute top-0 left-0 w-full h-1 overflow-hidden">
                        <motion.div
                            className="h-full bg-red-500"
                            initial={{ width: 0 }}
                            animate={{ width: isExecuting ? '100%' : 0 }}
                            transition={{ duration: 1, repeat: isExecuting ? Infinity : 0 }}
                        />
                    </div>

                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-500 animate-pulse">
                            <ShieldAlert size={24} />
                        </div>
                        <div>
                            <h2 className="text-sm font-black text-slate-100 uppercase tracking-[0.2em]">Remediation Alpha-1</h2>
                            <p className="text-[10px] text-red-400 font-mono mt-0.5 animate-pulse">SECURE_CHANNEL_ACTIVE // AUTH_REQUIRED</p>
                        </div>
                    </div>
                    <button
                        onClick={cancelRemediation}
                        className="text-slate-500 hover:text-white transition-colors p-1"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Script Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-red-500/20">
                    <div className="space-y-2">
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Target Anomaly</label>
                        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded-sm flex items-center justify-between">
                            <span className="text-xs font-mono text-slate-300">{activeRemediation.anomalyId}</span>
                            <span className="text-[9px] px-1.5 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded-sm font-bold">CRITICAL_FAULT</span>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Execution Sequence</label>
                            <span className="text-[9px] font-mono text-slate-600">STEPS: {activeRemediation.steps.length}</span>
                        </div>

                        <div className="space-y-3">
                            {activeRemediation.steps.map((step, idx) => (
                                <motion.div
                                    key={step.id}
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx * 0.1 }}
                                    className={`p-3 border rounded-sm transition-all duration-300 ${step.status === 'completed' ? 'bg-emerald-500/5 border-emerald-500/20 opacity-60' :
                                        step.status === 'executing' ? 'bg-red-500/10 border-red-500/40 shadow-[0_0_15px_rgba(239,68,68,0.1)] translate-x-1' :
                                            'bg-slate-900 border-slate-800'
                                        }`}
                                >
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2">
                                            <div className={`w-1.5 h-1.5 rounded-full ${step.status === 'completed' ? 'bg-emerald-500' :
                                                step.status === 'executing' ? 'bg-red-500 animate-pulse' :
                                                    'bg-slate-700'
                                                }`} />
                                            <span className={`text-[10px] font-bold font-mono ${step.status === 'completed' ? 'text-emerald-400' :
                                                step.status === 'executing' ? 'text-red-400' :
                                                    'text-slate-400'
                                                }`}>{step.command}</span>
                                        </div>
                                        {step.status === 'completed' && <CheckCircle2 size={12} className="text-emerald-500" />}
                                        {step.status === 'executing' && <Loader2 size={12} className="text-red-500 animate-spin" />}
                                    </div>
                                    <p className="text-[11px] text-slate-500 leading-relaxed italic">"{step.description}"</p>
                                </motion.div>
                            ))}
                        </div>
                    </div>

                    <div className="p-4 bg-amber-500/5 border border-amber-500/10 rounded-sm space-y-2">
                        <div className="flex items-center gap-2 text-amber-500">
                            <AlertTriangle size={14} />
                            <span className="text-[10px] font-bold uppercase tracking-wider">Mission Impact Warning</span>
                        </div>
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                            This script involves a hardware reset of the primary transceiver loop. Temporary data loss of up to 400ms is expected during execution phase 1.
                        </p>
                    </div>
                </div>

                {/* Authorization Action */}
                <div className="p-8 border-t border-slate-800 bg-slate-900/50 flex flex-col items-center gap-6">
                    <div className="text-center space-y-1">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.3em]">Operator Authentication</div>
                        <div className="text-[9px] font-mono text-slate-600 uppercase italic">Hold to authorize system command override</div>
                    </div>

                    <div className="relative group">
                        {/* Progress Ring */}
                        <svg className="w-24 h-24 transform -rotate-90">
                            <circle
                                cx="48"
                                cy="48"
                                r="40"
                                stroke="currentColor"
                                strokeWidth="4"
                                fill="transparent"
                                className="text-slate-800"
                            />
                            <motion.circle
                                cx="48"
                                cy="48"
                                r="40"
                                stroke="currentColor"
                                strokeWidth="4"
                                fill="transparent"
                                strokeDasharray="251.2"
                                strokeDashoffset={251.2 - (251.2 * holdProgress) / 100}
                                className={`${holdProgress === 100 ? 'text-emerald-500' : 'text-red-500'}`}
                            />
                        </svg>

                        <button
                            onMouseDown={handleMouseDown}
                            onMouseUp={handleMouseUp}
                            onMouseLeave={handleMouseUp}
                            disabled={isExecuting || isCompleted}
                            className={`absolute inset-0 m-4 rounded-full flex items-center justify-center transition-all duration-300 ${isCompleted ? 'bg-emerald-500 text-white' :
                                isExecuting ? 'bg-red-500/10 text-red-500 animate-pulse' :
                                    holdProgress > 0 ? 'bg-red-500 text-white scale-95 shadow-[0_0_20px_rgba(239,68,68,0.5)]' :
                                        'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white group-active:scale-95'
                                }`}
                        >
                            {isCompleted ? <CheckCircle2 size={32} /> :
                                isExecuting ? <Loader2 size={32} className="animate-spin" /> :
                                    <Fingerprint size={40} className={holdProgress > 0 ? 'animate-pulse' : ''} />}
                        </button>
                    </div>

                    <div className="flex items-center gap-4 w-full">
                        <div className="flex-1 h-px bg-slate-800" />
                        <span className="text-[10px] font-mono text-slate-500 uppercase">Status: {activeRemediation.status}</span>
                        <div className="flex-1 h-px bg-slate-800" />
                    </div>

                    {isCompleted && (
                        <motion.button
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            onClick={cancelRemediation}
                            className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 rounded text-white text-[10px] font-bold uppercase tracking-[0.2em] transition-all"
                        >
                            Review & Dismiss Logs
                        </motion.button>
                    )}
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
