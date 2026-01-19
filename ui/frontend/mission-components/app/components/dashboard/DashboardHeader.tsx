'use client';

import { useState, useEffect } from 'react';
import { MissionState } from '../../types/dashboard';
import { useDashboard } from '../../context/DashboardContext';
import { NotificationCenter } from '../ui/NotificationCenter';
import { HandoverModal } from '../ui/HandoverModal';
import { RefreshCcw } from 'lucide-react';

interface Props {
  data: MissionState;
}



import { PresenceBar } from '../ui/PresenceBar';

export const DashboardHeader: React.FC<Props> = ({ data }) => {
  const { isConnected } = useDashboard();
  const [isHandoverOpen, setIsHandoverOpen] = useState(false);
  const [time, setTime] = useState(new Date().toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }));

  useEffect(() => {
    const iv = setInterval(
      () =>
        setTime(
          new Date().toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
          })
        ),
      1000 * 30
    );
    return () => clearInterval(iv);
  }, []);

  return (
    <header className="sticky top-0 z-50 bg-slate-950/95 backdrop-blur-sm border-b border-slate-800">
      <HandoverModal isOpen={isHandoverOpen} onClose={() => setIsHandoverOpen(false)} />
      <div className="flex items-center justify-between px-6 py-3">
        {/* Left: Branding & Mission */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center">
              <span className="font-bold text-white">AG</span>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-100 uppercase tracking-wider">AstraGuard AI</h1>
              <div className="text-xs text-slate-500 uppercase tracking-widest">Mission Control</div>
            </div>
          </div>

          <div className="h-8 w-px bg-slate-800 hidden md:block" />

          <PresenceBar />

          <div className="h-8 w-px bg-slate-800 hidden md:block" />

          <div className="hidden md:block">
            <div className="text-xs text-slate-400 uppercase">Current Mission</div>
            <div className="text-sm font-mono font-medium text-blue-400">{data.name}</div>
          </div>
        </div>

        {/* Right: Metrics Strip */}
        <div className="flex items-center gap-6">
          <button
            onClick={() => setIsHandoverOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 border border-slate-700 hover:border-cyan-500/50 hover:bg-slate-800 rounded-sm transition-all group"
          >
            <RefreshCcw size={14} className="text-slate-400 group-hover:text-cyan-400" />
            <span className="text-[10px] font-bold text-slate-400 group-hover:text-slate-100 uppercase tracking-widest hidden lg:inline">Shift Handover</span>
          </button>
          <NotificationCenter />
          <div className="flex items-center gap-4 text-right">
            <div>
              <div className="text-xs text-slate-500 uppercase">Phase</div>
              <div className="text-sm font-bold text-slate-200">{data.phase}</div>
            </div>
            <div className="h-8 w-px bg-slate-800" />
            <div>
              <div className="text-xs text-slate-500 uppercase">System Time</div>
              <div className="text-sm font-mono text-slate-300">{time}</div>
            </div>
          </div>

          <div className={`px-3 py-1 rounded border text-xs font-bold uppercase tracking-wider ${isConnected
            ? 'bg-green-500/10 text-green-400 border-green-500/20'
            : 'bg-red-500/10 text-red-400 border-red-500/20'
            }`}>
            {isConnected ? 'Connected' : 'Offline'}
          </div>
        </div>
      </div>
    </header>
  );
};
