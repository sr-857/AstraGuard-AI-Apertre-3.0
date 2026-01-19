import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Zap, X } from 'lucide-react';
import { GeomagneticStormLevel } from '../../types/spaceWeather';

interface SpaceWeatherAlertProps {
    level: GeomagneticStormLevel;
    solarFlux: number;
    onDismiss: () => void;
}

export const SpaceWeatherAlert: React.FC<SpaceWeatherAlertProps> = ({
    level,
    solarFlux,
    onDismiss,
}) => {
    const getStormMessage = () => {
        switch (level) {
            case GeomagneticStormLevel.G5:
                return 'Extreme geomagnetic storm detected - expect severe signal degradation';
            case GeomagneticStormLevel.G4:
                return 'Severe geomagnetic storm detected - widespread signal interference likely';
            case GeomagneticStormLevel.G3:
                return 'Strong geomagnetic storm detected - intermittent signal loss possible';
            case GeomagneticStormLevel.G2:
                return 'Moderate geomagnetic storm detected - minor signal degradation expected';
            case GeomagneticStormLevel.G1:
                return 'Minor geomagnetic storm detected - nominal operations may be affected';
            default:
                return 'Space weather conditions nominal';
        }
    };

    const getStormColor = () => {
        switch (level) {
            case GeomagneticStormLevel.G5:
            case GeomagneticStormLevel.G4:
                return 'border-red-500/50 bg-red-500/10 text-red-400';
            case GeomagneticStormLevel.G3:
                return 'border-orange-500/50 bg-orange-500/10 text-orange-400';
            case GeomagneticStormLevel.G2:
            case GeomagneticStormLevel.G1:
                return 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400';
            default:
                return 'border-cyan-500/50 bg-cyan-500/10 text-cyan-400';
        }
    };

    if (level === GeomagneticStormLevel.NONE) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ y: -100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -100, opacity: 0 }}
                className="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 max-w-2xl w-full px-4"
            >
                <div className={`border-2 rounded-xl p-4 backdrop-blur-xl shadow-2xl ${getStormColor()}`}>
                    <div className="flex items-start gap-4">
                        <div className="p-2 bg-current/10 rounded-lg">
                            <Zap className="w-6 h-6" />
                        </div>

                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <AlertTriangle className="w-4 h-4" />
                                <h3 className="font-bold uppercase text-sm tracking-wider">
                                    Solar Activity Alert
                                </h3>
                                <span className="ml-auto px-2 py-0.5 bg-current/20 rounded text-xs font-mono font-bold">
                                    {level}
                                </span>
                            </div>

                            <p className="text-sm opacity-90 mb-2">{getStormMessage()}</p>

                            <div className="flex items-center gap-4 text-xs opacity-70">
                                <span>Solar Flux: {solarFlux.toFixed(1)}%</span>
                                <span>•</span>
                                <span>High error rates may be environmental, not hardware</span>
                            </div>
                        </div>

                        <button
                            onClick={onDismiss}
                            className="p-1 hover:bg-white/10 rounded transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
