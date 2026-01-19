import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Navigation, X } from 'lucide-react';
import { DebrisObject, ProximityLevel } from '../../types/debris';

interface ProximityAlertPanelProps {
    debrisObjects: DebrisObject[];
    closestDebris: DebrisObject | null;
    onDismiss?: () => void;
}

export const ProximityAlertPanel: React.FC<ProximityAlertPanelProps> = ({
    debrisObjects,
    closestDebris,
    onDismiss,
}) => {
    const getProximityColor = (level: ProximityLevel) => {
        switch (level) {
            case ProximityLevel.CRITICAL:
                return 'border-red-500/50 bg-red-500/10 text-red-400';
            case ProximityLevel.WARNING:
                return 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400';
            default:
                return 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400';
        }
    };

    const getProximityIcon = (level: ProximityLevel) => {
        switch (level) {
            case ProximityLevel.CRITICAL:
                return '🔴';
            case ProximityLevel.WARNING:
                return '🟡';
            default:
                return '🟢';
        }
    };

    const nearbyDebris = debrisObjects.filter((d) => d.proximityLevel !== ProximityLevel.SAFE);

    if (nearbyDebris.length === 0) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ x: -300, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -300, opacity: 0 }}
                className="fixed left-6 top-24 w-80 z-40 max-h-[60vh] overflow-hidden"
            >
                <div className="bg-black/80 backdrop-blur-xl border-2 border-yellow-500/50 rounded-xl shadow-2xl">
                    {/* Header */}
                    <div className="p-4 border-b border-yellow-500/30 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-yellow-500/20 rounded-lg">
                                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                                    Proximity Alert
                                </h3>
                                <p className="text-[10px] text-yellow-400/60 uppercase tracking-widest">
                                    {nearbyDebris.length} Object{nearbyDebris.length !== 1 ? 's' : ''} Detected
                                </p>
                            </div>
                        </div>
                        {onDismiss && (
                            <button
                                onClick={onDismiss}
                                className="p-1 hover:bg-white/10 rounded transition-colors"
                            >
                                <X className="w-4 h-4 text-white/60" />
                            </button>
                        )}
                    </div>

                    {/* Closest Debris Highlight */}
                    {closestDebris && closestDebris.proximityLevel !== ProximityLevel.SAFE && (
                        <div className={`p-4 border-b border-white/10 ${getProximityColor(closestDebris.proximityLevel)}`}>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-lg">{getProximityIcon(closestDebris.proximityLevel)}</span>
                                <span className="text-xs font-bold uppercase tracking-wider">Closest Threat</span>
                            </div>
                            <p className="text-sm font-bold mb-1">{closestDebris.name}</p>
                            <div className="flex items-center gap-4 text-xs">
                                <div>
                                    <span className="text-white/60">Distance: </span>
                                    <span className="font-mono font-bold">{closestDebris.distance.toFixed(2)} km</span>
                                </div>
                                <div>
                                    <span className="text-white/60">Size: </span>
                                    <span className="font-mono">{closestDebris.size}m</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Debris List */}
                    <div className="max-h-80 overflow-y-auto">
                        {nearbyDebris.map((debris) => (
                            <motion.div
                                key={debris.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={`p-3 border-b border-white/5 hover:bg-white/5 transition-colors ${debris.id === closestDebris?.id ? 'bg-white/5' : ''
                                    }`}
                            >
                                <div className="flex items-start justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                        <span>{getProximityIcon(debris.proximityLevel)}</span>
                                        <span className="text-xs font-bold text-white">{debris.name}</span>
                                    </div>
                                    <Navigation className="w-3 h-3 text-white/40" />
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-[10px]">
                                    <div>
                                        <span className="text-white/40">Distance:</span>
                                        <p className="font-mono text-white font-bold">{debris.distance.toFixed(2)} km</p>
                                    </div>
                                    <div>
                                        <span className="text-white/40">Velocity:</span>
                                        <p className="font-mono text-white">
                                            {Math.sqrt(
                                                debris.velocity.x ** 2 + debris.velocity.y ** 2 + debris.velocity.z ** 2
                                            ).toFixed(2)}{' '}
                                            km/s
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
