import React, { useRef, useEffect } from 'react';
import { AnomalyEvent } from '../../types/dashboard';


interface Props {
  anomalies: AnomalyEvent[];
  onAcknowledge: (id: string) => void;
  onSelect: (anomaly: AnomalyEvent) => void;
  onInvestigate: (anomaly: AnomalyEvent) => void;
  selectedSat?: string | null;
}

import { useSoundEffects } from '../../hooks/useSoundEffects';
import { useDashboard } from '../../context/DashboardContext';

export const AnomalyFeed: React.FC<Props> = ({ anomalies, onAcknowledge, onSelect, onInvestigate, selectedSat }) => {
  const { playAlert } = useSoundEffects();
  const { unlockAchievement } = useDashboard();
  const prevCount = useRef(anomalies.length);

  useEffect(() => {
    if (anomalies.length > prevCount.current) {
      const newest = anomalies[anomalies.length - 1];
      playAlert(newest.severity === 'Critical' ? 'high' : 'low');
    }
    prevCount.current = anomalies.length;
  }, [anomalies, playAlert]);

  // ... (keep existing severityConfig and sort logic - omitting for brevity in tool call if possible, but replace_file_content needs context)
  // Actually, replace_file_content replaces a block. I should target the Props definition first, then the specific button area.
  // Let's do it in one go if possible, or two.
  // The tool docs say: "StartLine and EndLine should specify a range of lines containing precisely the instances of TargetContent".
  // I will replace the Props interface and the component signature first.

  // TODO: Add error handling for anomaly processing and acknowledgment failures
  // TODO: Implement caching mechanism for anomaly data to reduce API calls
  const severityConfig = {
    Critical: { icon: 'Alert', borderColor: 'border-red-500/50', bgColor: 'bg-red-500/10', textColor: 'text-red-400' },
    Warning: { icon: 'Warning', borderColor: 'border-yellow-500/50', bgColor: 'bg-yellow-500/10', textColor: 'text-yellow-400' },
    Info: { icon: 'Info', borderColor: 'border-blue-500/50', bgColor: 'bg-blue-500/10', textColor: 'text-blue-400' },
  };



  const sortedAnomalies = [...anomalies].sort((a, b) => {
    if (a.severity === 'Critical' && b.severity !== 'Critical') return -1;
    if (a.severity !== 'Critical' && b.severity === 'Critical') return 1;
    return b.timestamp.localeCompare(a.timestamp);
  });

  return (
    <div className="h-full flex flex-col panel-base border-none rounded-none shadow-none bg-transparent">
      {/* List */}
      <div className="flex-1 overflow-auto space-y-2 pr-1 scrollbar-thin">
        {sortedAnomalies.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center text-slate-500">
            <span className="mb-2 text-2xl">✓</span>
            <span className="text-xs uppercase tracking-wider">All Systems Nominal</span>
          </div>
        ) : (
          sortedAnomalies.slice(0, 10).map((anomaly) => {
            const config = severityConfig[anomaly.severity];
            const isSelected = selectedSat === anomaly.satellite;

            return (
              <div
                key={anomaly.id}
                className={`group p-3 rounded-sm border-l-2 cursor-pointer transition-colors ${anomaly.acknowledged
                  ? 'border-slate-800 bg-slate-900/50 opacity-40 hover:opacity-60'
                  : `${config.borderColor} ${config.bgColor} border-t border-r border-b border-transparent`
                  } ${isSelected ? 'ring-1 ring-white/20' : ''}`}
                onClick={() => !anomaly.acknowledged && onSelect(anomaly)}
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-xs text-slate-200 uppercase tracking-wide">
                        {anomaly.satellite}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">
                        {anomaly.timestamp.split('T')[1]?.substring(0, 8) || anomaly.timestamp}
                      </span>
                    </div>

                    <div className={`text-sm font-medium ${anomaly.acknowledged ? 'text-slate-500 line-through' : 'text-slate-100'
                      }`}>
                      {anomaly.metric}
                    </div>

                    <div className={`text-xs font-mono mt-1 ${config.textColor}`}>
                      {anomaly.value}
                    </div>
                  </div>

                  {!anomaly.acknowledged && (
                    <div className="flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        className="px-2 py-1 text-xs border border-blue-500/30 rounded text-blue-400 hover:bg-blue-500/20 uppercase tracking-wider flex items-center justify-center gap-1"
                        onClick={(e) => {
                          e.stopPropagation();
                          onInvestigate(anomaly);
                        }}
                        title=" AI Investigate"
                      >
                        <span>🔍</span>
                      </button>
                      <button
                        className="px-2 py-1 text-xs border border-slate-700 rounded text-slate-400 hover:bg-slate-800 hover:text-white uppercase tracking-wider"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAcknowledge(anomaly.id);
                          unlockAchievement('first-responder');
                        }}
                      >
                        ACK
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
