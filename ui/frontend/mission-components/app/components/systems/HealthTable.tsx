import React, { useState } from 'react';
import { ArrowDown, ChevronDown } from 'lucide-react';
import { HealthRow } from '../../types/telemetry';

interface Props { data: HealthRow[] }

export const HealthTable: React.FC<Props> = ({ data }) => {
    const [sortBy, setSortBy] = useState<'status' | 'lastCheck' | 'uptime'>('status');
    const [sortDesc, setSortDesc] = useState(true);
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    const toggleSort = (column: 'status' | 'lastCheck' | 'uptime') => {
        if (sortBy === column) {
            setSortDesc(!sortDesc);
        } else {
            setSortBy(column);
            setSortDesc(true);
        }
    };

    const sortedData = [...data].sort((a, b) => {
        if (sortBy === 'status') {
            const order = { critical: 3, warning: 2, healthy: 1 };
            return sortDesc ? order[b.status] - order[a.status] : order[a.status] - order[b.status];
        }
        if (sortBy === 'lastCheck' || sortBy === 'uptime') {
            return sortDesc ? b[sortBy].localeCompare(a[sortBy]) : a[sortBy].localeCompare(b[sortBy]);
        }
        return 0;
    });

    const getStatusConfig = (status: HealthRow['status']) => ({
        healthy: { color: 'green', icon: '🟢', border: 'border-green-400', bg: 'bg-green-500/20', text: 'text-green-300' },
        warning: { color: 'amber', icon: '🟡', border: 'border-amber-400', bg: 'bg-amber-500/20', text: 'text-amber-300' },
        critical: { color: 'red', icon: '🔴', border: 'border-red-400', bg: 'bg-red-500/20', text: 'text-red-300' }
    }[status]);

    return (
        <div className="glow-teal/50 overflow-hidden rounded-2xl border-2 border-teal-500/30 bg-black/50 backdrop-blur-xl">
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        <tr className="bg-gradient-to-r from-teal-500/10 to-magenta-500/10 border-b border-teal-500/30">
                            <th className="p-4 text-left font-mono text-sm font-bold text-teal-400 cursor-pointer hover:glow-teal whitespace-nowrap">
                                Component
                            </th>
                            <th className="p-4 text-center font-mono text-sm font-bold text-teal-400 cursor-pointer hover:glow-teal group whitespace-nowrap"
                                onClick={() => toggleSort('status')}>
                                Status {sortBy === 'status' && (sortDesc ? <ArrowDown className="inline ml-1 w-4 h-4" /> : '↑')}
                            </th>
                            <th className="p-4 text-center font-mono text-sm font-bold text-teal-400 cursor-pointer hover:glow-teal whitespace-nowrap"
                                onClick={() => toggleSort('lastCheck')}>
                                Last Check {sortBy === 'lastCheck' && (sortDesc ? <ArrowDown className="inline ml-1 w-4 h-4" /> : '↑')}
                            </th>
                            <th className="p-4 text-center font-mono text-sm font-bold text-teal-400 cursor-pointer hover:glow-teal whitespace-nowrap"
                                onClick={() => toggleSort('uptime')}>
                                Uptime {sortBy === 'uptime' && (sortDesc ? <ArrowDown className="inline ml-1 w-4 h-4" /> : '↑')}
                            </th>
                            <th className="p-4 w-10"></th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedData.map((row, index) => {
                            const config = getStatusConfig(row.status);
                            const isExpanded = expanded.has(row.id);

                            return (
                                <React.Fragment key={row.id}>
                                    <tr className={`border-b border-teal-500/20 hover:bg-teal-500/5 transition-all group ${(index % 2) ? 'bg-black/20' : ''}`}>
                                        <td className="p-4 font-mono text-sm font-medium text-white whitespace-nowrap">
                                            <div className="flex items-center space-x-3">
                                                <span className={`text-xl animate-pulse group-hover:scale-110`}>{config.icon}</span>
                                                <span>{row.name}</span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-center whitespace-nowrap">
                                            <span className={`px-2 py-1 rounded-full text-xs font-bold ${config.bg} ${config.border} border ${config.text}`}>
                                                {row.status.toUpperCase()}
                                            </span>
                                        </td>
                                        <td className="p-4 text-center font-mono text-sm text-gray-400 whitespace-nowrap">{row.lastCheck}</td>
                                        <td className="p-4 text-center font-mono text-sm text-gray-400 whitespace-nowrap">{row.uptime}</td>
                                        <td className="p-4 text-center whitespace-nowrap">
                                            <button
                                                className="p-2 rounded-lg hover:bg-teal-500/20 hover:text-teal-400 glow-teal transition-all"
                                                onClick={() => setExpanded(prev => {
                                                    const newSet = new Set(prev);
                                                    if (newSet.has(row.id)) newSet.delete(row.id);
                                                    else newSet.add(row.id);
                                                    return newSet;
                                                })}
                                            >
                                                <ChevronDown className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                                            </button>
                                        </td>
                                    </tr>

                                    {isExpanded && (
                                        <tr className="bg-teal-500/5 border-t border-teal-500/30">
                                            <td colSpan={5} className="p-6">
                                                <div className="space-y-2 text-sm text-gray-300 font-mono">
                                                    {row.logs.map((log, i) => (
                                                        <div key={i} className="flex items-start space-x-2 p-3 rounded-lg bg-black/50 border border-gray-700">
                                                            <span className="text-xs text-gray-500 w-20 whitespace-nowrap">13:49:{30 + i * 2}</span>
                                                            <span className="break-all">{log}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
