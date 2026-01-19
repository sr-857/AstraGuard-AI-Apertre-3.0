export enum ProximityLevel {
    SAFE = 'SAFE',           // > 50km
    WARNING = 'WARNING',     // 5-50km
    CRITICAL = 'CRITICAL',   // < 5km
}

export interface DebrisObject {
    id: string;
    name: string;
    position: {
        lat: number;  // Latitude in degrees
        lon: number;  // Longitude in degrees
        alt: number;  // Altitude in km
    };
    velocity: {
        x: number;    // km/s
        y: number;
        z: number;
    };
    size: number;     // Diameter in meters
    distance: number; // Distance from satellite in km
    proximityLevel: ProximityLevel;
    timeToClosestApproach?: number; // Seconds until closest approach
}

export interface ProximityAlert {
    id: string;
    debrisId: string;
    level: ProximityLevel;
    distance: number;
    timestamp: string;
    message: string;
}
