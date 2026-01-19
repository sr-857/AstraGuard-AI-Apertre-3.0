import React from 'react';
import { BreakerState } from '../../types/systems';

interface Props {
    breakers: BreakerState[];
    services: string[];
}

export const BreakerMatrix: React.FC<Props> = ({ breakers, services }) => {
    const getState = (from: string, to: string) => {
        const breaker = breakers.find(b => b.from === from && b.to === to);
        return breaker?.state || 'Open';
    };

    const stateConfig = {
        Open: { color: 'green', icon: '🟢', label: 'Open' },
        Half: { color: 'amber', icon: '🟡', label: 'Half-Open' },
        Tripped: { color: 'red', icon: '🔴', label: 'Tripped' }
    };

    return (
        <div className="glow-magenta/50">
            <h3 className="text-xl font-bold mb-6 text-magenta-400 flex items-center">
                Circuit Breaker Matrix
                <span className="ml-3 text-sm bg-magenta-500/20 px-3 py-1 rounded-full font-mono">
                    {breakers.filter(b => b.state === 'Tripped').length} Tripped
                </span>
            </h3>

            <div className="overflow-x-auto rounded-2xl border-2 border-magenta-500/30 bg-black/50 backdrop-blur-xl">
                <table className="w-full table-auto border-separate border-spacing-1">
                    <thead>
                        <tr>
                            <th className="p-4 text-left font-mono text-sm text-magenta-300 bg-magenta-500/10 border border-magenta-500/30 rounded-l-xl">
                                Service →
                            </th>
                            {services.map(service => (
                                <th key={service} className="p-4 text-center font-mono text-xs uppercase text-gray-300 bg-magenta-500/5 border border-magenta-500/20">
                                    {service}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {services.map(fromService => (
                            <tr key={fromService}>
                                <td className="p-4 font-mono text-sm font-bold text-magenta-400 bg-magenta-500/10 border border-magenta-500/30 rounded-l-xl">
                                    {fromService}
                                </td>
                                {services.map(toService => {
                                    const state = getState(fromService, toService);
                                    const config = stateConfig[state];

                                    return (
                                        <td
                                            key={toService}
                                            className={`relative p-3 text-center cursor-pointer group hover:scale-110 transition-all border border-${config.color}-500/30 bg-${config.color}-500/10 hover:bg-${config.color}-500/20 glow-${config.color}`}
                                            title={`${fromService}→${toService}: ${config.label}${state !== 'Open' ? ` (${breakers.find(b => b.from === fromService && b.to === toService)?.duration})` : ''}`}
                                        >
                                            <div className="flex items-center justify-center space-x-1">
                                                <span className={`text-xl ${config.color === 'green' ? '' : 'animate-pulse'}`}>
                                                    {config.icon}
                                                </span>
                                                <span className="text-xs font-mono hidden group-hover:block whitespace-nowrap px-2 py-1 bg-black/90 rounded text-gray-200 absolute z-10 bottom-full left-1/2 transform -translate-x-1/2 mb-2 pointer-events-none">
                                                    {config.label}
                                                </span>
                                            </div>
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
