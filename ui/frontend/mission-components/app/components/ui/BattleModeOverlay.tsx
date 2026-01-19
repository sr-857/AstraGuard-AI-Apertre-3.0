import React from 'react';

interface BattleModeOverlayProps {
    active: boolean;
}

export const BattleModeOverlay: React.FC<BattleModeOverlayProps> = ({ active }) => {
    if (!active) return null;

    return (
        <div className="fixed inset-0 z-50 pointer-events-none overflow-hidden">
            {/* Pulsing Red Vignette */}
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_50%,rgba(255,0,0,0.4)_100%)] animate-pulse-slow"></div>

            {/* Scan Lines specifically red-tinted */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(255,0,0,0.1)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(255,0,0,0.02),rgba(255,0,0,0.06))] bg-[length:100%_4px,6px_100%] opacity-40"></div>

            {/* Warning Text */}
            <div className="absolute top-8 left-1/2 -translate-x-1/2 flex flex-col items-center">
                <div className="text-red-600 font-bold text-4xl tracking-widest animate-pulse border-4 border-red-600 px-8 py-2 bg-black/60 backdrop-blur">
                    CRITICAL ALERT
                </div>
                <div className="text-red-500 font-mono text-sm mt-2 tracking-[0.5em] uppercase">
                    Battle Mode Engaged
                </div>
            </div>

            {/* Corner Accents */}
            <div className="absolute top-0 left-0 w-32 h-32 border-t-8 border-l-8 border-red-600 rounded-tl-3xl opacity-80"></div>
            <div className="absolute top-0 right-0 w-32 h-32 border-t-8 border-r-8 border-red-600 rounded-tr-3xl opacity-80"></div>
            <div className="absolute bottom-0 left-0 w-32 h-32 border-b-8 border-l-8 border-red-600 rounded-bl-3xl opacity-80"></div>
            <div className="absolute bottom-0 right-0 w-32 h-32 border-b-8 border-r-8 border-red-600 rounded-br-3xl opacity-80"></div>
        </div>
    );
};
