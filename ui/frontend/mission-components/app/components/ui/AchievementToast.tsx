'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trophy, X } from 'lucide-react';
import { Achievement } from '../../types/dashboard';
import { useDashboard } from '../../context/DashboardContext';

export const AchievementToast: React.FC = () => {
    const { achievements } = useDashboard();
    const [activeAchievement, setActiveAchievement] = useState<Achievement | null>(null);

    useEffect(() => {
        const newAchievement = achievements.find(a => a.isNew);
        if (newAchievement) {
            setActiveAchievement(newAchievement);
            const timer = setTimeout(() => setActiveAchievement(null), 5000);
            return () => clearTimeout(timer);
        }
        return undefined;
    }, [achievements]);

    return (
        <AnimatePresence>
            {activeAchievement && (
                <motion.div
                    initial={{ x: 100, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    exit={{ x: 100, opacity: 0 }}
                    className="fixed top-24 right-6 z-[100] w-80 bg-slate-950 border-2 border-indigo-500 rounded-xl shadow-[0_0_30px_rgba(99,102,241,0.4)] overflow-hidden"
                >
                    <div className="absolute inset-0 bg-indigo-500/5" />
                    <div className="p-4 flex gap-4 relative z-10">
                        <div className="p-3 bg-indigo-500 rounded-lg flex-shrink-0 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.6)]">
                            <Trophy size={24} className="text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-[10px] font-black text-indigo-400 uppercase tracking-widest mb-1">Tactical Unlock</div>
                            <h3 className="text-sm font-bold text-white truncate">{activeAchievement.title}</h3>
                            <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">{activeAchievement.description}</p>
                        </div>
                        <button
                            onClick={() => setActiveAchievement(null)}
                            className="text-slate-500 hover:text-white transition-colors"
                        >
                            <X size={16} />
                        </button>
                    </div>
                    {/* Progress Bar Timer */}
                    <motion.div
                        initial={{ width: "100%" }}
                        animate={{ width: "0%" }}
                        transition={{ duration: 5, ease: "linear" }}
                        className="h-1 bg-indigo-500"
                    />
                </motion.div>
            )}
        </AnimatePresence>
    );
};
