export enum StationStatus {
    ACTIVE = 'ACTIVE',           // Currently in use
    SATURATED = 'SATURATED',     // High traffic, degraded performance
    OFFLINE = 'OFFLINE',         // Not available
    SWITCHING = 'SWITCHING',     // Transitioning to this station
}

export interface GroundStation {
    id: string;
    name: string;
    location: string;
    coordinates: {
        lat: number;
        lon: number;
        alt: number; // Altitude in km
    };
    bandwidth: number;      // Mbps
    latency: number;        // Milliseconds
    status: StationStatus;
    isActive: boolean;
    // Legacy Support for OrbitMap
    lat?: number;
    lng?: number;
    weather?: 'Clear' | 'Rain' | 'Storm';
    connectedSatelliteId?: string;
    signalQuality?: number;
}

export interface UplinkBeam {
    stationId: string;
    pulseSpeed: number;     // Speed multiplier based on bandwidth
    color: string;          // Hex color based on latency
    isActive: boolean;
}
