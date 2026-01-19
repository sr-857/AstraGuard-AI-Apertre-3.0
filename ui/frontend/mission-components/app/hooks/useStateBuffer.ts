import { useState, useCallback, useRef } from 'react';
import { TelemetryState } from '../types/websocket';

interface StateSnapshot {
    timestamp: number;
    state: TelemetryState;
}

interface UseStateBufferReturn {
    addSnapshot: (state: TelemetryState) => void;
    getSnapshotAtTime: (timestamp: number) => TelemetryState | null;
    getTimeRange: () => { start: number; end: number } | null;
    getAllSnapshots: () => StateSnapshot[];
    clearBuffer: () => void;
    bufferSize: number;
}

const MAX_BUFFER_SIZE = 900; // 15 minutes at 1Hz
const BUFFER_INTERVAL_MS = 1000; // 1 second

export const useStateBuffer = (): UseStateBufferReturn => {
    const [buffer, setBuffer] = useState<StateSnapshot[]>([]);
    const lastCaptureTime = useRef<number>(0);

    const addSnapshot = useCallback((state: TelemetryState) => {
        const now = Date.now();

        // Throttle captures to 1 per second
        if (now - lastCaptureTime.current < BUFFER_INTERVAL_MS) {
            return;
        }

        lastCaptureTime.current = now;

        setBuffer((prev) => {
            const newSnapshot: StateSnapshot = {
                timestamp: now,
                state: JSON.parse(JSON.stringify(state)), // Deep clone to prevent mutations
            };

            const updated = [...prev, newSnapshot];

            // Circular buffer: remove oldest if exceeds max size
            if (updated.length > MAX_BUFFER_SIZE) {
                return updated.slice(updated.length - MAX_BUFFER_SIZE);
            }

            return updated;
        });
    }, []);

    const getSnapshotAtTime = useCallback((timestamp: number): TelemetryState | null => {
        if (buffer.length === 0) return null;

        // Find the snapshot closest to the requested timestamp
        let closest = buffer[0];
        let minDiff = Math.abs(buffer[0].timestamp - timestamp);

        for (const snapshot of buffer) {
            const diff = Math.abs(snapshot.timestamp - timestamp);
            if (diff < minDiff) {
                minDiff = diff;
                closest = snapshot;
            }
        }

        return closest.state;
    }, [buffer]);

    const getTimeRange = useCallback((): { start: number; end: number } | null => {
        if (buffer.length === 0) return null;
        return {
            start: buffer[0].timestamp,
            end: buffer[buffer.length - 1].timestamp,
        };
    }, [buffer]);

    const getAllSnapshots = useCallback((): StateSnapshot[] => {
        return buffer;
    }, [buffer]);

    const clearBuffer = useCallback(() => {
        setBuffer([]);
        lastCaptureTime.current = 0;
    }, []);

    return {
        addSnapshot,
        getSnapshotAtTime,
        getTimeRange,
        getAllSnapshots,
        clearBuffer,
        bufferSize: buffer.length,
    };
};
