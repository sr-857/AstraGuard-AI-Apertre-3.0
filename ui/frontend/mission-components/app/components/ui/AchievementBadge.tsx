'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Zap,
    ShieldAlert,
    Library,
    CheckCircle2,
    Trophy,
    Star,
    Lock
} from 'lucide-react';
import { Achievement } from '../../types/dashboard';

const iconMap: Record<string, any> = {
    Zap,
    ShieldAlert,
    Library,
    CheckCircle2,
    Trophy,
    Star
};

interface Props {
    achievement: Achievement;
    size?: 'sm' | 'md' | 'lg';
}

export const AchievementBadge: React.FC<Props> = ({ achievement, size = 'md' }) => {
    const Icon = iconMap[achievement.icon] || Trophy;
    const isUnlocked = !!achievement.unlockedAt;

    const sizeClasses = {
        sm: 'w-10 h-10 p-2',
        md: 'w-16 h-16 p-4',
        lg: 'w-24 h-24 p-6'
    };

    return (
        <div className="relative group flex flex-col items-center">
            <motion.div
                initial={achievement.isNew ? { scale: 0, rotate: -180 } : false}
                animate={{ scale: 1, rotate: 0 }}
                className={`
                    ${sizeClasses[size]} 
                    rounded-full flex items-center justify-center relative 
                    transition-all duration-500
                    ${isUnlocked
                        ? 'bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border-2 border-indigo-500 shadow-[0_0_15px_rgba(99,102,241,0.3)]'
                        : 'bg-slate-900 border border-slate-800 opacity-40 grayscale'}
                `}
            >
                {/* Glow Effect for Unlocked */}
                {isUnlocked && (
                    <motion.div
                        className="absolute inset-0 rounded-full bg-indigo-500/10 blur-md"
                        animate={{
                            scale: [1, 1.2, 1],
                            opacity: [0.3, 0.6, 0.3]
                        }}
                        transition={{ duration: 3, repeat: Infinity }}
                    />
                )}

                {isUnlocked ? (
                    <Icon className="text-indigo-400 relative z-10" />
                ) : (
                    <Lock size={16} className="text-slate-600 relative z-10" />
                )}

                {/* New Tag */}
                <AnimatePresence>
                    {achievement.isNew && (
                        <motion.div
                            initial={{ y: 0, opacity: 0 }}
                            animate={{ y: -10, opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute -top-2 bg-emerald-500 text-[8px] font-black px-1.5 py-0.5 rounded-full text-white uppercase tracking-tighter shadow-lg z-20"
                        >
                            Unlocked
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>

            {/* Tooltip Content (Simple) */}
            <div className={`mt-2 text-center max-w-[120px]`}>
                <div className={`text-[10px] font-bold uppercase tracking-widest ${isUnlocked ? 'text-slate-100' : 'text-slate-600'}`}>
                    {achievement.title}
                </div>
                {size !== 'sm' && (
                    <div className="text-[9px] text-slate-500 mt-1 leading-tight opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                        {isUnlocked ? achievement.description : 'Locked Achievement'}
                    </div>
                )}
            </div>
        </div>
    );
};
