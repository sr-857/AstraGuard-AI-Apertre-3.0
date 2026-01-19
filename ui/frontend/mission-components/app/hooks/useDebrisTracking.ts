import { useState, useEffect, useCallback } from 'react';
import { DebrisObject, ProximityLevel } from '../types/debris';

interface UseDebrisTrackingReturn {
    debrisObjects: DebrisObject[];
    closestDebris: DebrisObject | null;
    proximityLevel: ProximityLevel;
    criticalDebrisCount: number;
}

const EARTH_RADIUS_KM = 6371;

// Haversine formula for distance calculation
const calculateDistance = (
    lat1: number,
    lon1: number,
    alt1: number,
    lat2: number,
    lon2: number,
    alt2: number
): number => {
    const toRad = (deg: number) => (deg * Math.PI) / 180;

    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);

    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const surfaceDistance = EARTH_RADIUS_KM * c;

    // Include altitude difference
    const altDiff = alt2 - alt1;
    return Math.sqrt(surfaceDistance * surfaceDistance + altDiff * altDiff);
};

const getProximityLevel = (distance: number): ProximityLevel => {
    if (distance < 5) return ProximityLevel.CRITICAL;
    if (distance < 50) return ProximityLevel.WARNING;
    return ProximityLevel.SAFE;
};

export const useDebrisTracking = (): UseDebrisTrackingReturn => {
    const [debrisObjects, setDebrisObjects] = useState<DebrisObject[]>([]);

    // Satellite position (mock - in production, get from telemetry)
    const satellitePosition = {
        lat: 45.0,
        lon: -75.0,
        alt: 550, // km
    };

    // Initialize debris objects
    useEffect(() => {
        const initialDebris: DebrisObject[] = [
            {
                id: 'debris-001',
                name: 'COSMOS 2251 Fragment',
                position: { lat: 45.5, lon: -74.5, alt: 555 },
                velocity: { x: 7.5, y: 0.2, z: 0.1 },
                size: 0.5,
                distance: 0,
                proximityLevel: ProximityLevel.SAFE,
            },
            {
                id: 'debris-002',
                name: 'Iridium 33 Debris',
                position: { lat: 44.8, lon: -75.3, alt: 548 },
                velocity: { x: 7.6, y: -0.1, z: 0.05 },
                size: 0.3,
                distance: 0,
                proximityLevel: ProximityLevel.SAFE,
            },
            {
                id: 'debris-003',
                name: 'Fengyun-1C Fragment',
                position: { lat: 46.0, lon: -76.0, alt: 560 },
                velocity: { x: 7.4, y: 0.3, z: -0.1 },
                size: 0.8,
                distance: 0,
                proximityLevel: ProximityLevel.SAFE,
            },
            {
                id: 'debris-004',
                name: 'Unknown Object',
                position: { lat: 45.1, lon: -75.1, alt: 551 },
                velocity: { x: 7.5, y: 0.05, z: 0.02 },
                size: 0.2,
                distance: 0,
                proximityLevel: ProximityLevel.SAFE,
            },
        ];

        setDebrisObjects(initialDebris);
    }, []);

    // Update debris positions and calculate distances
    const updateDebris = useCallback(() => {
        setDebrisObjects((prev) =>
            prev.map((debris) => {
                // Simulate orbital motion (simplified)
                const deltaTime = 0.1; // seconds
                const newLon = debris.position.lon + (debris.velocity.x / EARTH_RADIUS_KM) * (180 / Math.PI) * deltaTime;
                const newLat = debris.position.lat + (debris.velocity.y / EARTH_RADIUS_KM) * (180 / Math.PI) * deltaTime;
                const newAlt = debris.position.alt + debris.velocity.z * deltaTime;

                const newPosition = {
                    lat: newLat,
                    lon: newLon % 360, // Wrap longitude
                    alt: newAlt,
                };

                const distance = calculateDistance(
                    satellitePosition.lat,
                    satellitePosition.lon,
                    satellitePosition.alt,
                    newPosition.lat,
                    newPosition.lon,
                    newPosition.alt
                );

                return {
                    ...debris,
                    position: newPosition,
                    distance,
                    proximityLevel: getProximityLevel(distance),
                };
            })
        );
    }, [satellitePosition]);

    // Update debris positions every 100ms
    useEffect(() => {
        const interval = setInterval(updateDebris, 100);
        return () => clearInterval(interval);
    }, [updateDebris]);

    const closestDebris = debrisObjects.reduce<DebrisObject | null>((closest, debris) => {
        if (!closest || debris.distance < closest.distance) {
            return debris;
        }
        return closest;
    }, null);

    const proximityLevel = closestDebris?.proximityLevel || ProximityLevel.SAFE;
    const criticalDebrisCount = debrisObjects.filter((d) => d.proximityLevel === ProximityLevel.CRITICAL).length;

    return {
        debrisObjects,
        closestDebris,
        proximityLevel,
        criticalDebrisCount,
    };
};
