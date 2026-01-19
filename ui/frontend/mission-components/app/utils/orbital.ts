import { Satellite } from "../types/dashboard";

export interface SatellitePoint {
    lat: number;
    lng: number;
    alt: number;
    color: string;
    name: string;
    id: string;
    status: string;
}

// Deterministic pseudo-random based on string seed
const seededRandom = (seed: string) => {
    let h = 0x811c9dc5;
    for (let i = 0; i < seed.length; i++) {
        h ^= seed.charCodeAt(i);
        h = Math.imul(h, 0x01000193);
    }
    return function () {
        h = Math.imul(h ^ h >>> 13, 0xc2b2ae35);
        h = Math.imul(h ^ h >>> 17, 0x1100d1a3);
        return ((h >>> 0) / 4294967296);
    }
};

export const getSatellitePosition = (sat: Satellite): SatellitePoint => {
    const rng = seededRandom(sat.id);
    const now = Date.now();

    // Base parameters based on Orbit types (Mock logic)
    let altitude = 0.3; // Default (LEO-ish relative to earth radius=1 in global viz)
    let speed = 0.0001;
    const inclination = (rng() * 180) - 90;

    if (sat.orbit === 'GEO') {
        altitude = 1.5; // Higher
        speed = 0.00001; // Slower
    } else if (sat.orbit === 'MEO') {
        altitude = 0.8;
        speed = 0.00005;
    }

    // Calculate moving position
    // Simple orbital mechanics simulation for visual flair
    const timeOffset = now * speed + (rng() * 100);
    const lat = Math.sin(timeOffset) * (inclination / 2); // Oscillate latitude
    const lng = (timeOffset * 100) % 360 - 180; // Rotate longitude

    // Color mapping
    let color = '#94a3b8'; // Slate 400
    if (sat.status === 'Nominal') color = '#4ade80'; // Green 400
    if (sat.status === 'Degraded') color = '#facc15'; // Yellow 400
    if (sat.status === 'Critical') color = '#f87171'; // Red 400

    return {
        lat,
        lng,
        alt: altitude,
        color,
        name: sat.name,
        id: sat.id,
        status: sat.status
    };
};
