import { useState, useEffect, useCallback } from 'react';
import { GroundStation, StationStatus } from '../types/groundStation';

interface UseGroundStationsReturn {
    groundStations: GroundStation[];
    activeStation: GroundStation | null;
    switchStation: (stationId: string) => void;
}

const INITIAL_STATIONS: GroundStation[] = [
    {
        id: 'svalbard',
        name: 'Svalbard',
        location: 'Norway',
        coordinates: { lat: 78.2232, lon: 15.6267, alt: 0.5 },
        bandwidth: 150,
        latency: 45,
        status: StationStatus.ACTIVE,
        isActive: true,
    },
    {
        id: 'mumbai',
        name: 'Mumbai',
        location: 'India',
        coordinates: { lat: 19.0760, lon: 72.8777, alt: 0.01 },
        bandwidth: 80,
        latency: 120,
        status: StationStatus.SATURATED,
        isActive: false,
    },
    {
        id: 'alaska',
        name: 'Alaska',
        location: 'USA',
        coordinates: { lat: 64.2008, lon: -149.4937, alt: 0.3 },
        bandwidth: 120,
        latency: 60,
        status: StationStatus.ACTIVE,
        isActive: false,
    },
    {
        id: 'santiago',
        name: 'Santiago',
        location: 'Chile',
        coordinates: { lat: -33.4489, lon: -70.6693, alt: 0.5 },
        bandwidth: 100,
        latency: 85,
        status: StationStatus.ACTIVE,
        isActive: false,
    },
];

export const useGroundStations = (): UseGroundStationsReturn => {
    const [groundStations, setGroundStations] = useState<GroundStation[]>(INITIAL_STATIONS);
    const [activeStation, setActiveStation] = useState<GroundStation | null>(
        INITIAL_STATIONS.find((s) => s.isActive) || null
    );

    const switchStation = useCallback((stationId: string) => {
        setGroundStations((prev) =>
            prev.map((station) => ({
                ...station,
                isActive: station.id === stationId,
                status:
                    station.id === stationId
                        ? StationStatus.SWITCHING
                        : station.status === StationStatus.ACTIVE
                            ? StationStatus.ACTIVE
                            : station.status,
            }))
        );

        // Simulate switching delay
        setTimeout(() => {
            setGroundStations((prev) =>
                prev.map((station) => ({
                    ...station,
                    status:
                        station.id === stationId
                            ? StationStatus.ACTIVE
                            : station.status === StationStatus.SWITCHING
                                ? StationStatus.ACTIVE
                                : station.status,
                }))
            );

            const newActiveStation = groundStations.find((s) => s.id === stationId) || null;
            setActiveStation(newActiveStation);
        }, 2000);
    }, [groundStations]);

    // Simulate bandwidth and latency fluctuations
    useEffect(() => {
        const interval = setInterval(() => {
            setGroundStations((prev) =>
                prev.map((station) => {
                    // Random fluctuations
                    const bandwidthChange = (Math.random() - 0.5) * 20;
                    const latencyChange = (Math.random() - 0.5) * 10;

                    const newBandwidth = Math.max(50, Math.min(200, station.bandwidth + bandwidthChange));
                    const newLatency = Math.max(30, Math.min(150, station.latency + latencyChange));

                    // Determine status based on metrics
                    let newStatus = station.status;
                    if (station.status !== StationStatus.SWITCHING && station.status !== StationStatus.OFFLINE) {
                        if (newBandwidth < 70 || newLatency > 130) {
                            newStatus = StationStatus.SATURATED;
                        } else {
                            newStatus = StationStatus.ACTIVE;
                        }
                    }

                    return {
                        ...station,
                        bandwidth: Math.round(newBandwidth),
                        latency: Math.round(newLatency),
                        status: newStatus,
                        // Legacy Mappings
                        lat: station.coordinates.lat,
                        lng: station.coordinates.lon,
                        weather: newStatus === StationStatus.SATURATED ? 'Storm' : newStatus === StationStatus.OFFLINE ? 'Rain' : 'Clear',
                        signalQuality: Math.max(0, 1 - (newLatency / 150)),
                        connectedSatelliteId: station.isActive ? 'SAT-01' : undefined
                    };
                })
            );
        }, 2000); // Update every 2 seconds

        return () => clearInterval(interval);
    }, []);

    return {
        groundStations,
        activeStation,
        switchStation,
    };
};
