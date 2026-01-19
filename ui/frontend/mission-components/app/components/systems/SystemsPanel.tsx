import React from 'react';
import systemsData from '../../mocks/systems.json';
import { KPICard } from './KPICard';
import { BreakerMatrix } from './BreakerMatrix';
import { MetricsCharts } from './MetricsCharts';
import { HealthTable } from './HealthTable';
import { PredictiveAnalysis } from './PredictiveAnalysis';
import { useDashboard } from '../../context/DashboardContext';
import { usePredictiveData } from '../../hooks/usePredictiveData';

import { NeuralHealthMonitor } from './NeuralHealthMonitor';

export const SystemsPanel: React.FC = () => {
    const { state } = useDashboard();
    const { kpis, breakers, charts, health } = state.systems;
    const predictiveKpis = usePredictiveData(kpis);

    // Render logic remains similar, but data comes from context
    return (
        <div className="space-y-12 max-w-7xl mx-auto">
            {/* AI Health Overview - Neural Monitor */}
            <section className="animate-slide-up">
                <NeuralHealthMonitor />
            </section>

            {/* KPI Row */}
            <section className="panel-holo rounded-2xl p-6 animate-slide-up delay-100">
                <h2 className="text-2xl font-bold mb-8 text-magenta-400 glow-magenta flex items-center tracking-widest uppercase">
                    System Health Overview
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
                    {predictiveKpis.map(kpi => <KPICard key={kpi.id} {...kpi} />)}
                </div>
            </section>

            {/* Predictive Analysis (Only visible if critical) */}
            {(state.systems as any).prediction && (
                <section className="animate-slide-up delay-150">
                    <PredictiveAnalysis {...(state.systems as any).prediction} />
                </section>
            )}

            {/* Charts Grid */}
            <section className="panel-holo rounded-2xl p-6 animate-slide-up delay-200">
                <h2 className="text-2xl font-bold mb-8 text-teal-400 glow-teal tracking-widest uppercase">
                    Telemetry Trends (Last 1h)
                </h2>
                <MetricsCharts data={charts} />
            </section>

            {/* Health Table */}
            <section className="panel-holo rounded-2xl p-6 animate-slide-up delay-300">
                <h2 className="text-2xl font-bold mb-8 text-teal-400 glow-teal flex items-center tracking-widest uppercase">
                    Component Health <span className="ml-4 text-xs font-mono bg-teal-500/10 border border-teal-500/30 text-teal-300 px-3 py-1 rounded-sm">
                        {health.filter(h => h.status !== 'healthy').length} degraded
                    </span>
                </h2>
                <HealthTable data={health} />
            </section>

            {/* Breaker Matrix */}
            <BreakerMatrix breakers={breakers} services={systemsData.services} />
        </div>
    );
};
