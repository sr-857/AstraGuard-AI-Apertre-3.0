import { useState, useEffect, useCallback } from 'react';
import { DragPhysics, DragStatus, ATMOSPHERE_LAYERS } from '../types/physics';

const INITIAL_PHYSICS: DragPhysics = {
    altitude: 420,          // ISS typical altitude
    velocity: 7.66,         // km/s
    density: 1e-11,
    dragCoefficient: 2.2,
    surfaceArea: 10,        // m^2
    heatFlux: 0,
    orbitalDecayRate: 0.05,
    status: DragStatus.NOMINAL
};

export const useAtmosphericDrag = () => {
    const [physics, setPhysics] = useState<DragPhysics>(INITIAL_PHYSICS);

    // Interpolate density based on altitude
    const getDensity = (alt: number) => {
        const layer = ATMOSPHERE_LAYERS.find(l => alt >= l.alt) || ATMOSPHERE_LAYERS[ATMOSPHERE_LAYERS.length - 1];
        return layer.density;
    };

    // Calculate heat flux (q = 0.5 * density * velocity^3)
    const calculateHeatFlux = (density: number, velocity: number) => {
        // v in m/s (km/s * 1000)
        const v = velocity * 1000;
        // q in W/m^2 -> converted to kW/m^2 for readability
        return (0.5 * density * Math.pow(v, 3)) / 1000;
    };

    // Simulate orbital fluctuations
    useEffect(() => {
        const interval = setInterval(() => {
            setPhysics(prev => {
                // Determine drag status
                let status = DragStatus.NOMINAL;
                if (prev.altitude < 350) status = DragStatus.WARNING;
                if (prev.altitude < 300) status = DragStatus.CRITICAL;
                if (prev.altitude < 200) status = DragStatus.RE_ENTRY;

                // Simulate "Perigee Dip" - occasional altitude drops simulating elliptical orbit or drag spikes
                const randomDrop = Math.random() > 0.95 ? 5 : 0;
                // Natural decay
                const decay = prev.orbitalDecayRate / (24 * 60 * 60) * 100; // Scaled for demo speed

                let newAlt = prev.altitude - decay - randomDrop;

                // Auto-Station Keeping (Simulated Thrusters to prevent crash in demo)
                if (newAlt < 280) newAlt += 20;

                const newDensity = getDensity(newAlt);
                const newHeat = calculateHeatFlux(newDensity, prev.velocity);

                return {
                    ...prev,
                    altitude: newAlt,
                    density: newDensity,
                    heatFlux: newHeat,
                    status
                };
            });
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    // Manual Re-boost maneuver
    const executeReboost = useCallback(() => {
        setPhysics(prev => ({
            ...prev,
            altitude: prev.altitude + 50,
            status: DragStatus.NOMINAL
        }));
    }, []);

    return { physics, executeReboost };
};
