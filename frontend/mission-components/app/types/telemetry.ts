export interface ChartDataPoint {
    timestamp: string;    // "13:50"
    value: number;        // 47.2
}

export interface ChartSeries {
    id: string;           // "cpu"
    label: string;        // "CPU Load"
    data: ChartDataPoint[]; // 60pts
    forecast?: ChartDataPoint[]; // Predicted future points
    color: string;        // "#00f5ff"
}

export interface HealthRow {
    id: string;           // "db-primary"
    name: string;         // "PostgreSQL Primary"
    status: 'healthy' | 'warning' | 'critical';
    lastCheck: string;    // "13:49:32 IST"
    uptime: string;       // "47d 2h"
    logs: string[];       // Expandable
}
