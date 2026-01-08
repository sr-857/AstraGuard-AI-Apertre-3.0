'use client';

import { useState, useEffect } from 'react';
import { MissionState } from '../types/dashboard';
import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { MissionPanel } from '../components/mission/MissionPanel';
import { AnomalyInvestigator } from '../components/mission/AnomalyInvestigator';
import { AnomalyEvent } from '../types/dashboard';
import dashboardData from '../mocks/dashboard.json';

import { SystemsPanel } from '../components/systems/SystemsPanel';
import { ChaosPanel } from '../components/chaos/ChaosPanel';
import { CommandTerminal } from '../components/uplink/CommandTerminal';
import { ReplayControls } from '../components/replay/ReplayControls';

import { DashboardProvider, useDashboard } from '../context/DashboardContext';
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton';
import { TransitionWrapper } from '../components/ui/TransitionWrapper';
import { MobileNavHamburger } from '../components/ui/MobileNavHamburger';
import { DesktopTabNav } from '../components/dashboard/DesktopTabNav';
import { CommandPalette } from '../components/ui/CommandPalette';
import { BattleModeOverlay } from '../components/ui/BattleModeOverlay';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useSoundEffects } from '../hooks/useSoundEffects';

const DashboardContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mission' | 'systems' | 'chaos' | 'uplink'>('mission');
  const [selectedAnomalyForAnalysis, setSelectedAnomalyForAnalysis] = useState<AnomalyEvent | null>(null);
  const { isConnected, togglePlay, isReplayMode, isBattleMode, setBattleMode } = useDashboard();
  const mission = dashboardData.mission as MissionState;
  const [showPalette, setShowPalette] = useState(false);

  // Audio Engine Integration
  const [activeAudio, setActiveAudio] = useState(false);
  const { startDrone, stopDrone, updateDrone, playClick } = useSoundEffects();

  // Update drone based on system state
  useEffect(() => {
    if (activeAudio && mission) {
      // Calculate an aggregate load or use a specific metric
      // Here we use a mock CPU average from the mission data structure or mock it
      // Assuming mission might have telemetry attached, but for now we look at connected state
      // Let's use a mock fluctuation if actual telemetry isn't easily accessible in this scope:
      // Ideally: useDashboard would provide current telemetry frame.
      // For now, we'll map connected state to a stable hum and anomalies to tension.

      const anomalyCount = (mission.anomalies?.length || 0) + (selectedAnomalyForAnalysis ? 1 : 0);
      // Mock CPU load for ambient fluctuation effect
      const mockLoad = 40 + (Math.sin(Date.now() / 2000) * 10) + (anomalyCount * 10);

      updateDrone(mockLoad, anomalyCount);
    }
  }, [activeAudio, mission, selectedAnomalyForAnalysis, updateDrone]);

  // Clean up on unmount
  useEffect(() => {
    return () => stopDrone();
  }, [stopDrone]);

  const toggleAudio = () => {
    if (activeAudio) {
      stopDrone();
      setActiveAudio(false);
    } else {
      startDrone();
      setActiveAudio(true);
      playClick();
    }
  };

  // Keyboard Shortcuts
  useKeyboardShortcuts({
    onTabChange: setActiveTab,
    onTogglePlay: togglePlay,
    onOpenPalette: () => setShowPalette(true),
    onFocusTerminal: () => {
      setActiveTab('uplink');
      // Assuming Terminal takes focus on mount via autoFocus, which it does.
    },
    isReplayMode
  });

  return (
    <div className="dashboard-container min-h-screen text-white font-mono antialiased">
      <CommandPalette
        isOpen={showPalette}
        onClose={() => setShowPalette(false)}
        onNav={setActiveTab}
      />
      <DashboardHeader data={mission} />

      <div className="flex min-h-screen pt-[100px] lg:pt-[80px] flex-col">
        <nav className="sticky top-[100px] lg:top-[80px] z-20 bg-black/80 backdrop-blur-xl border-b border-teal-500/30 px-6 flex flex-col md:flex-row md:items-center justify-between flex-shrink-0 mb-4" role="tablist">

          {/* Mobile: Vertical Stack (only visible on mobile) */}
          <MobileNavHamburger activeTab={activeTab} onTabChange={setActiveTab} />

          {/* Desktop: Horizontal (hidden on mobile) */}
          <DesktopTabNav activeTab={activeTab} onTabChange={setActiveTab} />

          <div className="hidden md:block ml-auto flex items-center gap-4">
            <button
              onClick={toggleAudio}
              className={`flex items-center gap-2 px-3 py-1 rounded border transition-all text-xs uppercase tracking-wider ${activeAudio
                ? 'border-indigo-500 bg-indigo-500/20 text-indigo-300 shadow-[0_0_10px_rgba(99,102,241,0.3)]'
                : 'border-slate-700 bg-slate-900 text-slate-500 hover:text-slate-300'
                }`}
            >
              {activeAudio ? '🔊 Sonic' : '🔇 Mute'}
            </button>
            <button
              onClick={() => setBattleMode(!isBattleMode)}
              className={`flex items-center gap-2 px-3 py-1 rounded border transition-all text-xs uppercase tracking-wider ${isBattleMode
                ? 'border-red-500 bg-red-500/20 text-red-300 animate-pulse shadow-[0_0_15px_rgba(255,0,0,0.5)]'
                : 'border-slate-700 bg-slate-900 text-slate-500 hover:text-red-400'
                }`}
            >
              {isBattleMode ? '⚠️ BATTLE' : '🛡️ BATTLE'}
            </button>
            <ReplayControls />
          </div>
        </nav>

        <main className="flex-1 px-6 pb-8 relative">
          <BattleModeOverlay active={isBattleMode} />

          {!isConnected ? (
            <LoadingSkeleton type="chart" count={6} />
          ) : (
            <>
              {/* NORMAL MODE Layout */}
              {!isBattleMode && (
                <>
                  {activeTab === 'mission' && (
                    <TransitionWrapper isActive={activeTab === 'mission'}>
                      <MissionPanel onInvestigate={setSelectedAnomalyForAnalysis} />
                    </TransitionWrapper>
                  )}
                  {activeTab === 'systems' && (
                    <TransitionWrapper isActive={activeTab === 'systems'}>
                      <SystemsPanel />
                    </TransitionWrapper>
                  )}
                  {activeTab === 'chaos' && (
                    <TransitionWrapper isActive={activeTab === 'chaos'}>
                      <ChaosPanel className="max-w-4xl mx-auto mt-4" />
                    </TransitionWrapper>
                  )}
                  {activeTab === 'uplink' && (
                    <TransitionWrapper isActive={activeTab === 'uplink'}>
                      <CommandTerminal />
                    </TransitionWrapper>
                  )}
                </>
              )}

              {/* BATTLE MODE Layout */}
              {isBattleMode && (
                <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-140px)]">
                  {/* Priority 1: Anomaly Analysis (if selected) or Mission Overview */}
                  <div className="flex-1 lg:max-w-[40%] flex flex-col gap-4">
                    {selectedAnomalyForAnalysis ? (
                      <AnomalyInvestigator
                        anomaly={selectedAnomalyForAnalysis}
                        onClose={() => setSelectedAnomalyForAnalysis(null)}
                      />
                    ) : (
                      <MissionPanel onInvestigate={setSelectedAnomalyForAnalysis} />
                    )}
                  </div>

                  {/* Priority 2: Command Terminal (Maximized) */}
                  <div className="flex-1 border-2 border-red-500/50 shadow-[0_0_30px_rgba(255,0,0,0.2)] rounded-lg overflow-hidden">
                    <CommandTerminal />
                  </div>
                </div>
              )}

              {/* Anomaly Modal (Overlay for Normal Mode) */}
              {!isBattleMode && selectedAnomalyForAnalysis && (
                <AnomalyInvestigator
                  anomaly={selectedAnomalyForAnalysis}
                  onClose={() => setSelectedAnomalyForAnalysis(null)}
                />
              )}
            </>
          )}
        </main>

        <footer className="px-6 py-4 border-t border-slate-800 text-xs font-mono text-slate-500 uppercase tracking-widest flex justify-between items-center bg-slate-950">
          <span>AstraGuard Defense Systems v1.0</span>
          <span>Authorized Personnel Only • Class 1 Clearance</span>
        </footer>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  return (
    <DashboardProvider>
      <DashboardContent />
    </DashboardProvider>
  );
};

export default Dashboard;
