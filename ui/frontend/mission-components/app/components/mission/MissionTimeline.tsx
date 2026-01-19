import React from 'react';
import { MissionPhase } from '../../types/dashboard';

interface Props {
    phases: MissionPhase[];
}

export const MissionTimeline: React.FC<Props> = ({ phases }) => {
    return (
        <div className="panel-base p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="panel-title">Mission Timeline</h3>
                <span className="text-xs text-slate-400 font-mono">
                    T+02:30:15
                </span>
            </div>

            <div className="relative pt-6 pb-2">
                {/* Progress Bar Background */}
                <div className="h-2 bg-slate-800 rounded-full w-full overflow-hidden flex">
                    {phases.map((phase) => {
                        let colorClass = 'bg-slate-800';
                        if (phase.status === 'complete') colorClass = 'bg-blue-600';
                        if (phase.status === 'active') colorClass = 'bg-blue-500 animate-pulse';

                        return (
                            <div
                                key={phase.name}
                                className={`flex-1 h-full border-r border-slate-900 last:border-0 transition-all duration-500 ${colorClass}`}
                            />
                        );
                    })}
                </div>

                {/* Labels */}
                <div className="flex justify-between mt-3 px-[10%]">
                    {phases.map((phase) => (
                        <div
                            key={phase.name}
                            className={`flex flex-col items-center ${phase.status === 'pending' ? 'opacity-30' : 'opacity-100'
                                }`}
                        >
                            <span className={`text-[10px] font-bold uppercase tracking-wider mb-1 ${phase.status === 'active' ? 'text-blue-400' : 'text-slate-400'
                                }`}>
                                {phase.name}
                            </span>
                            {phase.status === 'active' && (
                                <span className="text-[10px] font-mono text-slate-500">
                                    {phase.progress}%
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
