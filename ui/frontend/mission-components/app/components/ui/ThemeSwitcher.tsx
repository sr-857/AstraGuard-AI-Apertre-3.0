'use client';

import React, { useState, useEffect } from 'react';
import { useTheme } from 'next-themes';
import { Monitor, Moon, Ghost, Zap } from 'lucide-react';

export const ThemeSwitcher: React.FC = () => {
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    // Prevent hydration mismatch by only rendering after mount
    useEffect(() => {
        setMounted(true);
    }, []);

    const themes = [
        { id: 'dark', label: 'DEFAULT', icon: Moon },
        { id: 'stealth', label: 'STEALTH', icon: Ghost },
        { id: 'clean', label: 'CLEAN', icon: Monitor },
        { id: 'high-visibility', label: 'TACTICAL', icon: Zap },
    ];

    if (!mounted) {
        return (
            <div className="flex items-center gap-1 bg-slate-900/50 backdrop-blur-sm border border-slate-800 p-1 rounded-sm">
                {themes.map((t) => (
                    <button
                        key={t.id}
                        className="flex items-center gap-2 px-2 py-1 rounded-sm text-slate-400"
                        disabled
                    >
                        <t.icon size={14} />
                        <span className="text-[10px] font-bold tracking-tighter uppercase">{t.label}</span>
                    </button>
                ))}
            </div>
        );
    }

    return (
        <div className="flex items-center gap-1 bg-slate-900/50 backdrop-blur-sm border border-slate-800 p-1 rounded-sm">
            {themes.map((t) => {
                const Icon = t.icon;
                const isActive = theme === t.id;
                return (
                    <button
                        key={t.id}
                        onClick={() => setTheme(t.id)}
                        className={`
              flex items-center gap-2 px-2 py-1 rounded-sm transition-all duration-200
              ${isActive
                                ? 'bg-slate-700 text-cyan-400 border border-cyan-500/50'
                                : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'}
            `}
                        title={t.label}
                    >
                        <Icon size={14} className={isActive ? 'animate-pulse' : ''} />
                        <span className="text-[10px] font-bold tracking-tighter uppercase">{t.label}</span>
                    </button>
                );
            })}
        </div>
    );
};
