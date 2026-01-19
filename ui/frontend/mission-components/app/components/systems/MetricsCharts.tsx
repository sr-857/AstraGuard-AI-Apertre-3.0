import React from 'react';
import { LineChart, Line, AreaChart, Area, BarChart, Bar, ResponsiveContainer, Tooltip, CartesianGrid, XAxis, YAxis } from 'recharts';
import { ChartSeries } from '../../types/telemetry';

interface Props { data: Record<string, ChartSeries> }

export const MetricsCharts: React.FC<Props> = ({ data }) => {
    const charts = [
        { id: 'cpu', type: LineChart, Component: Line, stroke: '#00f5ff', label: 'CPU Load %' },
        { id: 'memory', type: AreaChart, Component: Area, stroke: '#ff00ff', label: 'Memory Usage' },
        { id: 'io', type: BarChart, Component: Bar, stroke: '#10b981', label: 'Network I/O MB/s' },
        { id: 'latency', type: LineChart, Component: Line, stroke: '#f59e0b', label: 'P95 Latency ms' },
        { id: 'errors', type: LineChart, Component: Line, stroke: '#ef4444', label: 'Error Rate %' },
        { id: 'bus', type: LineChart, Component: Line, stroke: '#8b5cf6', label: 'Bus Utilization' }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {charts.map(({ id, type: ChartType, Component, stroke, label }) => {
                const series = data[id];
                if (!series) return null;

                const ChartComponent = ChartType as any;
                const SeriesComponent = Component as any;

                return (
                    <div key={id} className="glow-magenta/30 bg-black/40 backdrop-blur-xl rounded-2xl p-4 border border-magenta-500/30 group hover:border-magenta-400/60 transition-all duration-300">
                        <h4 className="font-mono text-sm text-magenta-400 mb-4 font-bold uppercase tracking-wider">{series.label}</h4>
                        <div className="h-[200px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <ChartComponent data={series.data.slice(-60)}>
                                    <CartesianGrid vertical={false} stroke="#1f2937" strokeDasharray="3 3" />
                                    <XAxis dataKey="timestamp" hide />
                                    <YAxis hide domain={['auto', 'auto']} />
                                    <Tooltip
                                        contentStyle={{ background: 'rgba(0,0,0,0.9)', border: `1px solid ${stroke}`, borderRadius: '8px', color: '#fff' }}
                                        labelStyle={{ color: '#ccc', marginBottom: '5px' }}
                                        itemStyle={{ color: stroke }}
                                        labelFormatter={(label) => `Time: ${label}`}
                                        formatter={(value: number | undefined) => [value !== undefined ? value.toFixed(1) : '0.0', label]}
                                    />
                                    <SeriesComponent
                                        type="monotone"
                                        dataKey="value"
                                        stroke={stroke}
                                        fill={stroke}
                                        fillOpacity={0.2}
                                        strokeWidth={2}
                                        dot={false}
                                        isAnimationActive={false} // Performance optimization for frequent updates
                                    />
                                    {series.forecast && (
                                        <SeriesComponent
                                            type="monotone"
                                            data={series.forecast}
                                            dataKey="value"
                                            stroke={stroke}
                                            fill="none"
                                            strokeDasharray="5 5"
                                            strokeWidth={2}
                                            dot={false}
                                            isAnimationActive={false}
                                        />
                                    )}
                                </ChartComponent>
                            </ResponsiveContainer>
                        </div>
                    </div>
                );
            })}
        </div>
    );
};
