'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Trophy, Award, Target, History, Zap } from 'lucide-react';
import { AchievementBadge } from '../ui/AchievementBadge';
import { useDashboard } from '../../context/DashboardContext';

export const AchievementPanel: React.FC = () => {
    const { achievements } = useDashboard();

    const categories = [
        { name: 'Tactical', icon: Target, color: 'text-indigo-400' },
        { name: 'Safety', icon: Award, color: 'text-emerald-400' },
        { name: 'Historical', icon: History, color: 'text-amber-400' },
        { name: 'Chaos', icon: Zap, color: 'text-red-400' }
    ];

    const unlockedCount = achievements.filter(a => !!a.unlockedAt).length;
    const totalCount = achievements.length;
    const progressPercent = (unlockedCount / totalCount) * 100;

    return (
        <div className="panel-holo bg-slate-950/80 border border-indigo-500/20 rounded-2xl p-8 overflow-hidden relative">
            {/* Background Texture */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 blur-[100px] rounded-full pointer-events-none" />

            <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12 relative z-10">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-indigo-500/10 rounded-xl">
                        <Trophy className="text-indigo-400" size={28} />
                    </div>
                    <div>
                        <h2 className="text-2xl font-black text-white uppercase tracking-tighter">Tactical Achievement Vault</h2>
                        <p className="text-xs text-indigo-400/60 font-mono mt-1 uppercase tracking-widest">Operator Career Highlights // Clear Level 4</p>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                        Completion Progress
                        <span className="text-indigo-400">{unlockedCount} / {totalCount}</span>
                    </div>
                    <div className="w-48 h-1.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${progressPercent}%` }}
                            className="h-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                        />
                    </div>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 relative z-10">
                {categories.map(cat => {
                    const catAchievements = achievements.filter(a => a.category === cat.name);
                    const Icon = cat.icon;

                    return (
                        <div key={cat.name} className="space-y-6">
                            <div className="flex items-center gap-3 pb-2 border-b border-slate-800">
                                <Icon className={cat.color} size={16} />
                                <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{cat.name} Ops</h3>
                            </div>

                            <div className="flex flex-wrap gap-6 justify-center lg:justify-start">
                                {catAchievements.map(a => (
                                    <AchievementBadge key={a.id} achievement={a} />
                                ))}
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* Footer Tip */}
            <div className="mt-12 pt-8 border-t border-slate-900 flex items-center justify-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[9px] text-slate-600 font-bold uppercase tracking-widest">
                    Performance stats are synced with AstraGuard Central Command.
                </span>
            </div>
        </div>
    );
};
