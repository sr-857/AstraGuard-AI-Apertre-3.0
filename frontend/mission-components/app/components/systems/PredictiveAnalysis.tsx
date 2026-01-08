import React from 'react';

interface Props {
    systemId: string;
    label: string;
    trend: 'stable' | 'increasing' | 'decreasing' | 'critical';
    timeToFailure?: number; // Seconds
    confidence: number; // 0-1
}

export const PredictiveAnalysis: React.FC<Props> = ({ systemId, label, trend, timeToFailure, confidence }) => {
    // Only show if there's a negative trend or critical status
    if (trend === 'stable' || trend === 'increasing') return null;

    const formatTime = (seconds: number) => {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    };

    return (
        <div className="relative overflow-hidden rounded-xl bg-red-950/20 border border-red-500/50 backdrop-blur-md p-6 animate-pulse-slow">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-500 to-transparent opacity-50 animate-scan"></div>

            <div className="flex justify-between items-start mb-4">
                <div>
                    <h3 className="text-red-400 font-mono text-sm tracking-widest uppercase mb-1">AI FORECAST WARNING</h3>
                    <p className="text-xl font-bold text-white">{label} Critical Drop</p>
                </div>
                <div className="text-right">
                    <div className="text-xs text-red-300 uppercase tracking-wide opacity-70">Confidence</div>
                    <div className="text-lg font-mono text-red-400">{(confidence * 100).toFixed(0)}%</div>
                </div>
            </div>

            {timeToFailure !== undefined && (
                <div className="flex items-center justify-center py-4 bg-black/40 rounded-lg border border-red-900/30">
                    <div className="text-center">
                        <div className="text-xs text-red-500 uppercase tracking-[0.2em] mb-2">Estimated Time to Failure</div>
                        <div className="text-5xl font-mono font-bold text-red-500 tabular-nums tracking-tighter drop-shadow-[0_0_10px_rgba(239,68,68,0.5)]">
                            {formatTime(timeToFailure)}
                        </div>
                    </div>
                </div>
            )}

            <div className="mt-4 pt-3 border-t border-red-500/20 flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-red-500 animate-ping"></div>
                <p className="text-xs text-red-300 font-mono">
                    Analysis: Linear regression indicates zero-crossing event. immediate action required.
                </p>
            </div>
        </div>
    );
};
