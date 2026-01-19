export enum GeomagneticStormLevel {
    NONE = 'NONE',
    G1 = 'G1', // Minor
    G2 = 'G2', // Moderate
    G3 = 'G3', // Strong
    G4 = 'G4', // Severe
    G5 = 'G5', // Extreme
}

export interface SpaceWeatherData {
    solarFlux: number; // 0-100, represents solar radio flux intensity
    geomagneticStorm: GeomagneticStormLevel;
    radiationLevel: number; // 0-100
    kpIndex: number; // 0-9, geomagnetic activity index
    lastUpdated: string;
    isActive: boolean; // True if currently experiencing storm conditions
}

export interface SpaceWeatherAlert {
    id: string;
    level: GeomagneticStormLevel;
    message: string;
    timestamp: string;
    duration?: number; // Expected duration in minutes
}
