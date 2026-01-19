import * as React from 'react';

interface LayerControlProps {
    showGroundStations: boolean;
    onToggleGroundStations: () => void;
    showDragMetrics: boolean;
    onToggleDragMetrics: () => void;
    showBiometrics: boolean;
    onToggleBiometrics: () => void;
    showProximityAlert: boolean;
    onToggleProximityAlert: () => void;
    isReplayMode: boolean;
    onToggleReplayMode: () => void;
    showSolarAlert: boolean;
    onToggleSolarAlert: () => void;
    isSolarActivityActive: boolean;
}

export const LayerControl: React.FC<LayerControlProps> = ({
    showGroundStations,
    onToggleGroundStations,
    showDragMetrics,
    onToggleDragMetrics,
    showBiometrics,
    onToggleBiometrics,
    showProximityAlert,
    onToggleProximityAlert,
    isReplayMode,
    onToggleReplayMode,
    showSolarAlert,
    onToggleSolarAlert,
    isSolarActivityActive
}) => {
    return (
        <div className="fixed top-24 right-24 z-40 flex items-center gap-4">
            {/* Replay Toggle */}
            {!isReplayMode && (
                <button
                    onClick={onToggleReplayMode}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30"
                >
                    <span className="text-lg">↺</span>
                    <span className="text-xs font-bold uppercase tracking-wider">Replay Mode</span>
                </button>
            )}

            {/* Solar Activity Toggle */}
            <button
                onClick={onToggleSolarAlert}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all ${showSolarAlert
                    ? 'bg-amber-500/20 border-amber-500 text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.3)]'
                    : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30'
                    } ${!showSolarAlert && isSolarActivityActive ? 'animate-pulse border-amber-500/50 text-amber-500/80 shadow-[0_0_10px_rgba(245,158,11,0.2)]' : ''}`}
            >
                <div className={`w-2 h-2 rounded-full ${showSolarAlert ? 'bg-amber-400 animate-pulse' : isSolarActivityActive ? 'bg-amber-500 animate-ping' : 'bg-slate-600'}`} />
                <span className="text-xs font-bold uppercase tracking-wider">Solar</span>
            </button>

            {/* Ground Stations Toggle */}
            <button
                onClick={onToggleGroundStations}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all ${showGroundStations
                    ? 'bg-cyan-500/20 border-cyan-500 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]'
                    : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30'
                    }`}
            >
                <div className={`w-2 h-2 rounded-full ${showGroundStations ? 'bg-cyan-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-xs font-bold uppercase tracking-wider">Ground Stn</span>
            </button>

            {/* Drag Metrics Toggle */}
            <button
                onClick={onToggleDragMetrics}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all ${showDragMetrics
                    ? 'bg-orange-500/20 border-orange-500 text-orange-400 shadow-[0_0_15px_rgba(249,115,22,0.3)]'
                    : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30'
                    }`}
            >
                <div className={`w-2 h-2 rounded-full ${showDragMetrics ? 'bg-orange-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-xs font-bold uppercase tracking-wider">Atmosphere</span>
            </button>

            {/* Biometrics Toggle */}
            <button
                onClick={onToggleBiometrics}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all ${showBiometrics
                    ? 'bg-blue-500/20 border-blue-500 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)]'
                    : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30'
                    }`}
            >
                <div className={`w-2 h-2 rounded-full ${showBiometrics ? 'bg-blue-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-xs font-bold uppercase tracking-wider">Biometrics</span>
            </button>

            {/* Proximity Toggle */}
            <button
                onClick={onToggleProximityAlert}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border backdrop-blur-md transition-all ${showProximityAlert
                    ? 'bg-red-500/20 border-red-500 text-red-400 shadow-[0_0_15px_rgba(239,68,68,0.3)]'
                    : 'bg-black/40 border-white/10 text-slate-400 hover:text-white hover:border-white/30'
                    }`}
            >
                <div className={`w-2 h-2 rounded-full ${showProximityAlert ? 'bg-red-400 animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-xs font-bold uppercase tracking-wider">Proximity</span>
            </button>
        </div>
    );
};
