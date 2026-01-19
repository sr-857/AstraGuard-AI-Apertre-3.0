import React from 'react';
import { KPI } from '../../types/systems';

interface Props extends KPI { }

export const KPICard: React.FC<Props> = ({ label, value, trend, progress, unit, riskScore, riskHistory }) => {
    const trendIcon = trend >= 0 ? '↗' : '↘';
    const trendColor = trend >= 0 ? 'text-green-400' : 'text-red-400';

    return (
        <div className="group p-6 rounded-2xl bg-black/30 backdrop-blur-xl border border-magenta-500/30 hover:border-magenta-400/60 hover:glow-magenta hover:scale-[1.02] transition-all duration-300 cursor-pointer">
            {/* Label */}
            <div className="text-xs font-mono uppercase tracking-wider text-magenta-400 mb-3 opacity-80 group-hover:opacity-100">
                {label}
            </div>

            {/* Value + Unit */}
            <div className="flex items-baseline justify-between mb-4">
                <span className="text-3xl lg:text-2xl font-bold font-mono text-white tracking-tight">
                    {value}
                </span>
                <span className="text-sm font-mono text-gray-400">{unit}</span>
            </div>

            {/* Progress Ring */}
            <svg width="64" height="64" viewBox="0 0 64 64" className="mx-auto mb-4">
                <circle
                    cx="32" cy="32" r="28"
                    fill="none"
                    stroke="#1f2937"
                    strokeWidth="4"
                    strokeLinecap="round"
                />
                <circle
                    cx="32" cy="32" r="28"
                    fill="none"
                    stroke="url(#kpiGrad)"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${progress * 1.76}, 176`}
                    className="transition-all duration-1000 origin-center group-hover:animate-spin-slow"
                    strokeDashoffset="0"
                    transform="rotate(-90 32 32)"
                />
                <defs>
                    <linearGradient id="kpiGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#ff00ff" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#00f5ff" stopOpacity="0.8" />
                    </linearGradient>
                </defs>
            </svg>

            {/* Risk Indicator */}
            <div className="mt-4 pt-4 border-t border-slate-800/50">
                <div className="flex justify-between items-center mb-2">
                    <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">Predictive Risk</span>
                    <span className={`text-xs font-mono font-bold ${(riskScore || 0) > 70 ? 'text-red-400' : (riskScore || 0) > 40 ? 'text-amber-400' : 'text-emerald-400'
                        }`}>
                        {riskScore}%
                    </span>
                </div>
                {riskHistory && (
                    <div className="h-8 flex items-end gap-0.5">
                        {riskHistory.map((h, i) => (
                            <div
                                key={i}
                                className={`flex-1 rounded-sm transition-all duration-500 ${h > 70 ? 'bg-red-500/40' : h > 40 ? 'bg-amber-500/30' : 'bg-emerald-500/20'
                                    }`}
                                style={{ height: `${Math.max(10, h)}%` }}
                            ></div>
                        ))}
                    </div>
                )}
            </div>

            {/* Trend */}
            <div className={`mt-2 text-[10px] font-mono font-bold ${trendColor} flex items-center gap-1`}>
                <span>{trendIcon}</span>
                <span>{Math.abs(trend).toFixed(trend > 1 ? 0 : 2)}%</span>
                <span className="text-slate-600 font-normal ml-auto">VOLATILITY</span>
            </div>
        </div>
    );
};
