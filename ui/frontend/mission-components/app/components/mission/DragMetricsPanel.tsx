import * as React from 'react';
import { motion } from 'framer-motion';
import { Wind, Thermometer, ArrowUpCircle, AlertOctagon } from 'lucide-react';
import { DragPhysics, DragStatus } from '../../types/physics';

interface DragMetricsPanelProps {
    physics: DragPhysics;
    onReboost: () => void;
}

export const DragMetricsPanel: React.FC<DragMetricsPanelProps> = ({ physics, onReboost }) => {
    const getStatusColor = (status: DragStatus) => {
        switch (status) {
            case DragStatus.NOMINAL:
                return 'text-green-400 border-green-500/50';
            case DragStatus.WARNING:
                return 'text-yellow-400 border-yellow-500/50';
            case DragStatus.CRITICAL:
                return 'text-orange-400 border-orange-500/50';
            case DragStatus.RE_ENTRY:
                return 'text-red-500 border-red-500/50 blink'; // animated css
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className={`w-64 bg-black/80 backdrop-blur-xl border-2 rounded-xl overflow-hidden ${getStatusColor(physics.status)}`}
        >
            {/* Header */}
            <div className="p-3 border-b border-white/10 bg-gradient-to-r from-red-500/10 to-orange-500/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Wind className="w-5 h-5 text-orange-400" />
                    <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                        Atmospheric Drag
                    </h3>
                </div>
                {physics.status !== DragStatus.NOMINAL && (
                    <AlertOctagon className="w-5 h-5 text-red-500 animate-pulse" />
                )}
            </div>

            {/* Metrics */}
            <div className="p-4 space-y-4">
                {/* Altitude */}
                <div>
                    <div className="flex justify-between text-xs text-white/60 mb-1">
                        <span>ALTITUDE (LEO)</span>
                        <span>{physics.altitude.toFixed(1)} km</span>
                    </div>
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                            className={`h-full ${physics.altitude < 300 ? 'bg-red-500' : 'bg-green-400'
                                }`}
                            initial={{ width: '100%' }}
                            animate={{ width: `${(physics.altitude / 600) * 100}%` }}
                            transition={{ duration: 0.5 }}
                        />
                    </div>
                </div>

                {/* Density / Drag */}
                <div className="grid grid-cols-2 gap-2">
                    <div className="bg-white/5 p-2 rounded">
                        <p className="text-[10px] text-white/40 uppercase">Density</p>
                        <p className="text-xs font-mono text-white">
                            {physics.density.toExponential(1)}
                        </p>
                    </div>
                    <div className="bg-white/5 p-2 rounded">
                        <p className="text-[10px] text-white/40 uppercase">Decay Rate</p>
                        <p className="text-xs font-mono text-red-400">
                            -{physics.orbitalDecayRate.toFixed(3)} km/d
                        </p>
                    </div>
                </div>

                {/* Heat Flux */}
                <div className="flex items-center gap-3">
                    <Thermometer className="w-8 h-8 text-red-500" />
                    <div>
                        <p className="text-xs text-white/60 uppercase">Heat Flux</p>
                        <p className={`text-lg font-bold font-mono ${physics.heatFlux > 50 ? 'text-red-500' : 'text-orange-400'
                            }`}>
                            {physics.heatFlux.toFixed(2)} kW/m²
                        </p>
                    </div>
                </div>

                {/* Re-boost Button */}
                <button
                    onClick={onReboost}
                    disabled={physics.status === DragStatus.NOMINAL}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-500 text-white font-bold text-xs uppercase rounded transition-all"
                >
                    <ArrowUpCircle className="w-4 h-4" />
                    Initiate Re-boost
                </button>
            </div>
        </motion.div>
    );
};
