export interface DragPhysics {
    altitude: number;       // km (LEO: 160-2000 km)
    velocity: number;       // km/s (orbital velocity)
    density: number;        // kg/m^3 (atmospheric density)
    dragCoefficient: number;// Dimensionless
    surfaceArea: number;    // m^2
    heatFlux: number;       // kW/m^2
    orbitalDecayRate: number; // km/day
    status: DragStatus;
}

export enum DragStatus {
    NOMINAL = 'NOMINAL',       // Minimal drag
    WARNING = 'WARNING',       // Increased density
    CRITICAL = 'CRITICAL',     // Re-entry risk
    RE_ENTRY = 'RE_ENTRY'      // Structural failure imminent
}

// Standard Atmospheric Model (simplified)
export const ATMOSPHERE_LAYERS = [
    { alt: 600, density: 1e-13 },
    { alt: 500, density: 1e-12 },
    { alt: 400, density: 1e-11 }, // ISS typical
    { alt: 300, density: 1e-10 },
    { alt: 200, density: 1e-9 },
    { alt: 100, density: 1e-7 },  // Karman line
];
