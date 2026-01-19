import { WebSocketServer } from 'ws';
import express from 'express';
import http from 'http';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const dashboardData = require('../app/mocks/dashboard.json');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const systemsData = require('../app/mocks/systems.json');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const telemetryData = require('../app/mocks/telemetry.json');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

console.log('Loading mock data...');

// Initialize state from existing mocks
let currentState = {
    mission: {
        satellites: dashboardData.mission.satellites,
        phases: dashboardData.mission.phases,
        anomalies: dashboardData.mission.anomalies
    },
    systems: {
        kpis: systemsData.kpis,
        breakers: systemsData.breakers,
        charts: telemetryData.charts,
        health: telemetryData.health
    }
};

const generateTelemetryTick = () => {
    // Simulate Chart updates
    const updatedCharts = { ...currentState.systems.charts };
    Object.keys(updatedCharts).forEach(key => {
        // @ts-ignore
        const chart = updatedCharts[key];
        const lastVal = chart.data[chart.data.length - 1].value;
        const newVal = Math.max(0, Math.min(100, lastVal + (Math.random() - 0.5) * 5));
        // @ts-ignore
        chart.data = [...chart.data.slice(1), { timestamp: new Date().toLocaleTimeString(), value: newVal }];
    });

    // Simulate KPI drift
    const updatedKpis = currentState.systems.kpis.map((kpi: any) => ({
        ...kpi,
        value: kpi.id === 'latency' ? `${Math.floor(120 + Math.random() * 40)}ms` : kpi.value
    }));

    // Simulate Satellite Telemetry drift
    const updatedSatellites = currentState.mission.satellites.map((sat: any) => ({
        ...sat,
        latency: Math.max(10, sat.latency + (Math.random() - 0.5) * 10),
        signal: Math.max(0, Math.min(100, sat.signal + (Math.random() - 0.5) * 5))
    }));

    // Occasionally trigger anomaly
    if (Math.random() > 0.95) {
        // ... anomaly logic could go here
    }

    return {
        mission: {
            ...currentState.mission,
            satellites: updatedSatellites
        },
        systems: {
            ...currentState.systems,
            charts: updatedCharts,
            kpis: updatedKpis
        }
    };
};

wss.on('connection', (ws) => {
    console.log('Client connected');

    // Send initial snapshot
    ws.send(JSON.stringify({
        type: 'telemetry_snapshot',
        payload: currentState,
        timestamp: new Date().toISOString()
    }));

    // Stream updates
    const interval = setInterval(() => {
        const changes = generateTelemetryTick();
        // In a real optimized system we'd send delta, but here we can send 'telemetry' type with updated systems part
        // Sending full charts every 2s is heavy, but fine for local MVP
        ws.send(JSON.stringify({
            type: 'telemetry',
            payload: changes.systems
        }));
    }, 2000);

    ws.on('message', (message: string) => {
        try {
            const msg = JSON.parse(message);
            if (msg.type === 'ANOMALY_ACK') {
                console.log(`Ack anomaly: ${msg.payload.id}`);
                // Broadcast ACK to all clients (including sender) if needed, 
                // but sender usually handles it optimistically.
                // Let's broadcast connection status as a heartbeat or ack
            }
        } catch (e) {
            console.error(e);
        }
    });

    ws.on('close', () => {
        clearInterval(interval);
        console.log('Client disconnected');
    });
});

server.listen(8080, () => {
    console.log('🚀 WS Mock Server running on ws://localhost:8080/dashboard');
});
