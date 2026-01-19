'use client';

import React, { useState, useEffect } from 'react';
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
import { useSoundscape } from '../hooks/useSoundscape';
import { CopilotChat } from '../components/dashboard/CopilotChat';
import { ThemeSwitcher } from '../components/ui/ThemeSwitcher';
import { CommandHUD } from '../components/ui/CommandHUD';
import { RemediationDrawer } from '../components/mission/RemediationDrawer';
import { AchievementToast } from '../components/ui/AchievementToast';
import { AchievementPanel } from '../components/dashboard/AchievementPanel';
import { DiagnosticsPanel } from '../components/dashboard/DiagnosticsPanel';
import { TimelineScrubber } from '../components/replay/TimelineScrubber';
import { ReplayOverlay } from '../components/replay/ReplayOverlay';
import { EncryptionSpectrogram } from '../components/security/EncryptionSpectrogram';
import { GlitchOverlay } from '../components/effects/GlitchOverlay';
import { SpaceWeatherAlert } from '../components/effects/SpaceWeatherAlert';
import { RedPhoneReset } from '../components/controls/RedPhoneReset';
import { DashboardDimOverlay } from '../components/effects/DashboardDimOverlay';
import { ProximityAlertPanel } from '../components/radar/ProximityAlertPanel';
import { IncidentPlaybook } from '../components/playbook/IncidentPlaybook';
import { PanelHighlight } from '../components/playbook/PanelHighlight';
import { BiometricPulse } from '../components/biometric/BiometricPulse';
import { BiometricHUD } from '../components/biometric/BiometricHUD';
import { HighContrastOverlay } from '../components/biometric/HighContrastOverlay';
import { AutoPilotProposal } from '../components/biometric/AutoPilotProposal';
import { GroundStationPanel } from '../components/groundStation/GroundStationPanel';
import { DragMetricsPanel } from '../components/mission/DragMetricsPanel';
import { LayerControl } from '../components/mission/LayerControl';

const DashboardContent: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'mission' | 'systems' | 'chaos' | 'uplink' | 'vault' | 'diagnostics'>('mission');
  const [selectedAnomalyForAnalysis, setSelectedAnomalyForAnalysis] = useState<AnomalyEvent | null>(null);
  const { isConnected, togglePlay, isReplayMode, toggleReplayMode, isBattleMode, setBattleMode, spaceWeather, distortionIntensity, isGeomagneticStorm, executeSystemReset, debrisObjects, closestDebris, proximityLevel, activePlaybook, setActivePlaybook, biometricData, incrementMissedAlerts, resetMissedAlerts, isAutoPilotActive, enableAutoPilot, disableAutoPilot, groundStations, activeStation, switchStation, dragPhysics, executeReboost } = useDashboard();
  const [showSpaceWeatherAlert, setShowSpaceWeatherAlert] = useState(false);
  const [isRedPhoneCoverOpen, setIsRedPhoneCoverOpen] = useState(false);
  const [showProximityAlert, setShowProximityAlert] = useState(false);
  const [highlightedPanel, setHighlightedPanel] = useState<string | null>(null);
  const [showAutoPilotProposal, setShowAutoPilotProposal] = useState(false);
  const mission = { ...dashboardData.mission, aiHealth: (dashboardData as any).aiHealth, achievements: (dashboardData as any).achievements } as MissionState;
  const [showPalette, setShowPalette] = useState(false);

  // Layer Visibility State
  const [showGroundStations, setShowGroundStations] = useState(false);
  const [showDragMetrics, setShowDragMetrics] = useState(false);
  const [showBiometrics, setShowBiometrics] = useState(false);

  // Audio Engine Integration
  const [activeAudio, setActiveAudio] = useState(false);
  const { startDrone, stopDrone, updateDrone, playClick, playProximityBeep } = useSoundEffects();
  const { startHum, startWhoosh, playGeigerClick, stopAll: stopSoundscape } = useSoundscape();

  // Proximity Beeping
  React.useEffect(() => {
    if (!closestDebris || proximityLevel === 'SAFE') return;

    const interval = playProximityBeep(closestDebris.distance);
    const beepInterval = setInterval(() => {
      playProximityBeep(closestDebris.distance);
    }, interval);

    return () => clearInterval(beepInterval);
  }, [closestDebris, proximityLevel, playProximityBeep]);

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
    return () => {
      stopDrone();
      stopSoundscape();
    };
  }, [stopDrone, stopSoundscape]);

  // Geiger Counter Logic (Background Clicks based on Anomaly count)
  useEffect(() => {
    if (!activeAudio || !mission?.anomalies?.length) return;

    const interval = setInterval(() => {
      // Probability of click increases with anomaly count
      const threshold = 0.95 - (mission.anomalies.length * 0.05);
      if (Math.random() > Math.max(0.1, threshold)) {
        playGeigerClick();
      }
    }, 100);

    return () => clearInterval(interval);
  }, [activeAudio, mission?.anomalies, playGeigerClick]);

  const toggleAudio = () => {
    if (activeAudio) {
      stopDrone();
      stopSoundscape();
      setActiveAudio(false);
    } else {
      startDrone();
      startHum();
      startWhoosh();
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
      <CommandHUD />
      <AchievementToast />
      <ReplayOverlay />
      <GlitchOverlay intensity={distortionIntensity} isActive={distortionIntensity > 0.3} />
      {showSpaceWeatherAlert && (
        <SpaceWeatherAlert
          level={spaceWeather.geomagneticStorm}
          solarFlux={spaceWeather.solarFlux}
          onDismiss={() => setShowSpaceWeatherAlert(false)}
        />
      )}
      <DashboardDimOverlay isActive={isRedPhoneCoverOpen} />

      {/* Biometric System */}
      {showBiometrics && (
        <>
          <BiometricPulse biometricData={biometricData} />
          <BiometricHUD biometricData={biometricData} />
        </>
      )}
      <HighContrastOverlay
        isActive={biometricData.missedAlerts >= 3}
        missedAlerts={biometricData.missedAlerts}
        onAcknowledge={resetMissedAlerts}
      />
      <AutoPilotProposal
        biometricData={biometricData}
        onEnable={() => {
          enableAutoPilot();
          setShowAutoPilotProposal(false);
        }}
        onDismiss={() => setShowAutoPilotProposal(false)}
      />
      <CommandPalette
        isOpen={showPalette}
        onClose={() => setShowPalette(false)}
        onNav={setActiveTab}
      />
      <RemediationDrawer />
      <DashboardHeader data={mission} />

      {/* Red Phone Reset Button */}
      <div className="fixed bottom-6 right-6 z-50">
        <RedPhoneReset onResetConfirm={executeSystemReset} />
      </div>

      {/* Proximity Alert Panel */}
      {showProximityAlert && (
        <ProximityAlertPanel
          debrisObjects={debrisObjects}
          closestDebris={closestDebris}
          onDismiss={() => setShowProximityAlert(false)}
        />
      )}

      {/* Incident Playbook Overlay */}
      <IncidentPlaybook
        playbook={activePlaybook}
        onDismiss={() => setActivePlaybook(null)}
        onStepComplete={(stepId) => console.log('Step completed:', stepId)}
        onHighlightPanel={setHighlightedPanel}
      />

      {/* Panel Highlighting */}
      <PanelHighlight targetPanelId={highlightedPanel} />

      {/* Layer Control */}
      <LayerControl
        showGroundStations={showGroundStations}
        onToggleGroundStations={() => setShowGroundStations(!showGroundStations)}
        showDragMetrics={showDragMetrics}
        onToggleDragMetrics={() => setShowDragMetrics(!showDragMetrics)}
        showBiometrics={showBiometrics}
        onToggleBiometrics={() => setShowBiometrics(!showBiometrics)}
        showProximityAlert={showProximityAlert}
        onToggleProximityAlert={() => setShowProximityAlert(!showProximityAlert)}
        isReplayMode={isReplayMode}
        onToggleReplayMode={toggleReplayMode}
        showSolarAlert={showSpaceWeatherAlert}
        onToggleSolarAlert={() => setShowSpaceWeatherAlert(!showSpaceWeatherAlert)}
        isSolarActivityActive={isGeomagneticStorm || spaceWeather.solarFlux > 50}
      />

      {/* Ground Station Panel */}
      {showGroundStations && (
        <GroundStationPanel
          groundStations={groundStations}
          activeStation={activeStation}
          onSwitchStation={switchStation}
        />
      )}

      {/* Atmospheric Drag Metrics - Adjusted Position via prop or CSS class if flexible, 
          but here we'll assume it handles itself or we wrap it to move it down if needed.
          Actually, we should update DragMetricsPanel to accept className or style, 
          OR just accept that LayerControl is at top-24 and DragPanel might need to move.
          
          Current DragMetricsPanel is fixed right-6 top-24. 
          LayerControl is fixed right-6 top-24. 
          Overlap!
          
          I will update DragMetricsPanel in next step to move to top-36 (top-24 + ~48px).
       */}
      {showDragMetrics && (
        <div className="fixed right-6 top-40 z-30">
          {/* Wrapping to override position if component allows, 
                 but component has 'fixed' class. 
                 It needs to be passed a className or updated.
                 I'll update the component file separately to accept className or change default.
              */}
          <DragMetricsPanel
            physics={dragPhysics}
            onReboost={executeReboost}
          />
        </div>
      )}

      <div className="flex min-h-screen pt-[100px] lg:pt-[80px] flex-col">
        <nav className="sticky top-[100px] lg:top-[80px] z-20 bg-black/80 backdrop-blur-xl border-b border-teal-500/30 px-6 flex flex-col md:flex-row md:items-center justify-between flex-shrink-0 mb-4" role="tablist">

          {/* Mobile: Vertical Stack (only visible on mobile) */}
          <MobileNavHamburger activeTab={activeTab} onTabChange={setActiveTab} />

          {/* Desktop: Horizontal (hidden on mobile) */}
          <DesktopTabNav activeTab={activeTab} onTabChange={setActiveTab} />

          <div className="hidden md:flex ml-auto items-center gap-4">
            <ThemeSwitcher />
            <div className="h-6 w-[1px] bg-slate-800 mx-2" />
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
                  {activeTab === 'vault' && (
                    <TransitionWrapper isActive={activeTab === 'vault'}>
                      <AchievementPanel />
                    </TransitionWrapper>
                  )}
                  {activeTab === 'diagnostics' && (
                    <TransitionWrapper isActive={activeTab === 'diagnostics'}>
                      <DiagnosticsPanel />
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
        <TimelineScrubber />
        <CopilotChat />
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
