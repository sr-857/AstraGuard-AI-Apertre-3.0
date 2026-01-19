import { useState, useEffect, useCallback } from 'react';
import { SpaceWeatherData, GeomagneticStormLevel } from '../types/spaceWeather';

interface UseSpaceWeatherReturn {
    spaceWeather: SpaceWeatherData;
    distortionIntensity: number; // 0-1, calculated from solar flux
    isGeomagneticStorm: boolean;
    refreshWeather: () => void;
}

const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

export const useSpaceWeather = (): UseSpaceWeatherReturn => {
    const [spaceWeather, setSpaceWeather] = useState<SpaceWeatherData>({
        solarFlux: 45,
        geomagneticStorm: GeomagneticStormLevel.NONE,
        radiationLevel: 20,
        kpIndex: 2,
        lastUpdated: new Date().toISOString(),
        isActive: false,
    });

    const fetchSpaceWeather = useCallback(async () => {
        try {
            // In production, fetch from NOAA Space Weather API
            // For now, use mock data with simulation

            // Simulate space weather fluctuations
            const now = Date.now();
            const cycleTime = now / 10000; // Slow cycle for demo

            const baseSolarFlux = 40 + Math.sin(cycleTime) * 30;
            const randomSpike = Math.random() < 0.1 ? Math.random() * 40 : 0; // 10% chance of spike
            const solarFlux = Math.min(100, Math.max(0, baseSolarFlux + randomSpike));

            // Determine geomagnetic storm level based on flux
            let geomagneticStorm = GeomagneticStormLevel.NONE;
            let isActive = false;

            if (solarFlux > 90) {
                geomagneticStorm = GeomagneticStormLevel.G5;
                isActive = true;
            } else if (solarFlux > 80) {
                geomagneticStorm = GeomagneticStormLevel.G4;
                isActive = true;
            } else if (solarFlux > 70) {
                geomagneticStorm = GeomagneticStormLevel.G3;
                isActive = true;
            } else if (solarFlux > 60) {
                geomagneticStorm = GeomagneticStormLevel.G2;
                isActive = true;
            } else if (solarFlux > 50) {
                geomagneticStorm = GeomagneticStormLevel.G1;
                isActive = true;
            }

            const kpIndex = Math.min(9, Math.floor((solarFlux / 100) * 9));
            const radiationLevel = Math.min(100, solarFlux * 0.8 + Math.random() * 20);

            setSpaceWeather({
                solarFlux,
                geomagneticStorm,
                radiationLevel,
                kpIndex,
                lastUpdated: new Date().toISOString(),
                isActive,
            });
        } catch (error) {
            console.error('Failed to fetch space weather data:', error);
        }
    }, []);

    useEffect(() => {
        fetchSpaceWeather();
        const interval = setInterval(fetchSpaceWeather, POLL_INTERVAL);
        return () => clearInterval(interval);
    }, [fetchSpaceWeather]);

    const distortionIntensity = Math.min(1, Math.max(0, (spaceWeather.solarFlux - 50) / 50));
    const isGeomagneticStorm = spaceWeather.isActive;

    return {
        spaceWeather,
        distortionIntensity,
        isGeomagneticStorm,
        refreshWeather: fetchSpaceWeather,
    };
};
