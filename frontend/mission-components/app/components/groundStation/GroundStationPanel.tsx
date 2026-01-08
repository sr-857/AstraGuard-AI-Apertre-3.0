import * as React from 'react';
import { motion } from 'framer-motion';
import { Radio, Activity, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { GroundStation, StationStatus } from '../../types/groundStation';

interface GroundStationPanelProps {
    groundStations: GroundStation[];
    activeStation: GroundStation | null;
    onSwitchStation: (stationId: string) => void;
}

export const GroundStationPanel: React.FC<GroundStationPanelProps> = ({
    groundStations,
    activeStation,
    onSwitchStation,
}) => {
    const getStatusColor = (status: StationStatus) => {
        switch (status) {
            case StationStatus.ACTIVE:
                return 'text-green-400 border-green-500/50';
            case StationStatus.SATURATED:
                return 'text-yellow-400 border-yellow-500/50';
            case StationStatus.SWITCHING:
                return 'text-cyan-400 border-cyan-500/50';
            case StationStatus.OFFLINE:
                return 'text-red-400 border-red-500/50';
        }
    };

    const getLatencyColor = (latency: number) => {
        if (latency < 60) return 'text-green-400';
        if (latency < 100) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getStatusIcon = (status: StationStatus) => {
        switch (status) {
            case StationStatus.ACTIVE:
                return <Wifi className="w-4 h-4" />;
            case StationStatus.SATURATED:
                return <Activity className="w-4 h-4" />;
            case StationStatus.SWITCHING:
                return <RefreshCw className="w-4 h-4 animate-spin" />;
            case StationStatus.OFFLINE:
                return <WifiOff className="w-4 h-4" />;
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="fixed left-6 bottom-24 z-50 w-80"
        >
            <div className="bg-black/80 backdrop-blur-xl border-2 border-white/10 rounded-xl overflow-hidden">
                {/* Header */}
                <div className="p-4 border-b border-white/10 bg-gradient-to-r from-cyan-500/10 to-blue-500/10">
                    <div className="flex items-center gap-2">
                        <Radio className="w-5 h-5 text-cyan-400" />
                        <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                            Ground Stations
                        </h3>
                    </div>
                </div>

                {/* Stations List */}
                <div className="max-h-96 overflow-y-auto p-3 space-y-2">
                    {groundStations.map((station) => (
                        <motion.div
                            key={station.id}
                            className={`p-3 rounded-lg border-2 ${station.isActive
                                    ? 'bg-cyan-500/10 border-cyan-500/50'
                                    : 'bg-white/5 border-white/10'
                                } transition-all`}
                            whileHover={{ scale: 1.02 }}
                        >
                            <div className="flex items-start justify-between mb-2">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h4 className="text-sm font-bold text-white">{station.name}</h4>
                                        {station.isActive && (
                                            <span className="px-2 py-0.5 bg-cyan-500/20 border border-cyan-500/50 rounded text-[10px] text-cyan-400 font-bold uppercase">
                                                Active
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-white/60">{station.location}</p>
                                </div>
                                <div className={`${getStatusColor(station.status)}`}>
                                    {getStatusIcon(station.status)}
                                </div>
                            </div>

                            {/* Metrics */}
                            <div className="grid grid-cols-2 gap-2 mb-2">
                                <div>
                                    <p className="text-[10px] text-white/60 uppercase tracking-widest">Bandwidth</p>
                                    <p className="text-sm font-bold text-white">{station.bandwidth} Mbps</p>
                                </div>
                                <div>
                                    <p className="text-[10px] text-white/60 uppercase tracking-widest">Latency</p>
                                    <p className={`text-sm font-bold ${getLatencyColor(station.latency)}`}>
                                        {station.latency}ms
                                    </p>
                                </div>
                            </div>

                            {/* Switch Button */}
                            {!station.isActive && station.status !== StationStatus.OFFLINE && (
                                <button
                                    onClick={() => onSwitchStation(station.id)}
                                    disabled={station.status === StationStatus.SWITCHING}
                                    className="w-full px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/50 rounded text-xs text-cyan-400 font-bold uppercase tracking-wider transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {station.status === StationStatus.SWITCHING ? 'Switching...' : 'Switch to This'}
                                </button>
                            )}
                        </motion.div>
                    ))}
                </div>
            </div>
        </motion.div>
    );
};
