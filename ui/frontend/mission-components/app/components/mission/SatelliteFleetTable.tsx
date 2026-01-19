import React, { useState } from 'react';
import { Satellite, SatelliteStatus } from '../../types/dashboard';

interface Props {
    satellites: Satellite[];
}

export const SatelliteFleetTable: React.FC<Props> = ({ satellites }) => {
    const [sortField, setSortField] = useState<keyof Satellite | null>(null);
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

    const handleSort = (field: keyof Satellite) => {
        if (sortField === field) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('asc');
        }
    };

    const getStatusClass = (status: SatelliteStatus) => {
        switch (status) {
            case 'Nominal': return 'status-nominal';
            case 'Degraded': return 'status-degraded';
            case 'Critical': return 'status-critical';
            default: return 'text-slate-400 bg-slate-800';
        }
    };

    const sortedSatellites = [...satellites].sort((a, b) => {
        if (!sortField) return 0;
        if (a[sortField] < b[sortField]) return sortDirection === 'asc' ? -1 : 1;
        if (a[sortField] > b[sortField]) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    return (
        <div className="panel-base overflow-hidden">
            <div className="panel-header">
                <h3 className="panel-title">Satellite Fleet Status</h3>
                <span className="text-xs text-slate-400 font-mono">
                    {satellites.filter(s => s.status === 'Nominal').length} / {satellites.length} ONLINE
                </span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 border-b border-slate-800 text-xs uppercase text-slate-400">
                        <tr>
                            <th className="px-4 py-3 font-medium cursor-pointer hover:text-slate-200" onClick={() => handleSort('id')}>ID</th>
                            <th className="px-4 py-3 font-medium cursor-pointer hover:text-slate-200" onClick={() => handleSort('name')}>Name</th>
                            <th className="px-4 py-3 font-medium cursor-pointer hover:text-slate-200" onClick={() => handleSort('status')}>Status</th>
                            <th className="px-4 py-3 font-medium">Latency</th>
                            <th className="px-4 py-3 font-medium text-right">Signal</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                        {sortedSatellites.map((sat) => (
                            <tr key={sat.id} className="hover:bg-slate-800/50 transition-colors">
                                <td className="px-4 py-3 font-mono text-slate-400">{sat.id}</td>
                                <td className="px-4 py-3 font-medium text-slate-200">{sat.name}</td>
                                <td className="px-4 py-3">
                                    <span className={`status-chip ${getStatusClass(sat.status)}`}>
                                        {sat.status.toUpperCase()}
                                    </span>
                                </td>
                                <td className="px-4 py-3 font-mono text-slate-300">{sat.latency}ms</td>
                                <td className="px-4 py-3 text-right font-mono text-slate-300">{sat.signalStrength}%</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
