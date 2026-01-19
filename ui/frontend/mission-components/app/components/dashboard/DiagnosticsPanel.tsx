import * as React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, ContactShadows } from '@react-three/drei';
import { motion } from 'framer-motion';
import { Activity, Zap, Radio, Target } from 'lucide-react';
import { SatelliteModel } from '../diagnostics/SatelliteModel';
import { useDashboard } from '../../context/DashboardContext';
import { TelemetryState } from '../../types/websocket';
import { MissionState } from '../../types/dashboard';

const StatCard = ({ icon: Icon, label, value, status }: any) => (
    <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="bg-black/40 border border-white/10 p-4 rounded-xl flex items-center gap-4 backdrop-blur-md"
    >
        <div className={`p-2 rounded-lg ${status === 'nominal' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
            <Icon className={`w-5 h-5 ${status === 'nominal' ? 'text-green-400' : 'text-red-400'}`} />
        </div>
        <div>
            <p className="text-xs text-white/50 uppercase tracking-widest">{label}</p>
            <p className="text-xl font-mono text-white tracking-tighter">{value}</p>
        </div>
    </motion.div>
);

export const DiagnosticsPanel = () => {
    const { state } = useDashboard();
    const mission = (state as TelemetryState).mission as MissionState;
    const [faultySystems, setFaultySystems] = React.useState<string[]>([]);

    React.useEffect(() => {
        if (!mission) return;
        const list = [];
        if (mission.aiHealth?.load > 80) list.push('ACS');
        if (mission.phase === 'SAFE_MODE') list.push('Battery', 'Comm');
        setFaultySystems(list);
    }, [mission]);

    return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-180px)]">
            {/* 3D Digital Twin View */}
            <div className="lg:col-span-3 relative bg-gradient-to-b from-blue-950/20 to-black/40 rounded-3xl border border-white/10 overflow-hidden shadow-2xl">
                <div className="absolute top-6 left-6 z-10 flex items-center gap-3">
                    <div className="w-3 h-3 bg-cyan-400 rounded-full animate-pulse shadow-[0_0_10px_#22d3ee]" />
                    <h2 className="text-sm font-bold text-white/80 tracking-widest uppercase">Neural Digital Twin</h2>
                </div>

                <Canvas shadows gl={{ antialias: true, stencil: true }}>
                    <PerspectiveCamera makeDefault position={[5, 3, 5]} fov={40} />
                    <OrbitControls
                        enablePan={false}
                        minDistance={4}
                        maxDistance={8}
                        makeDefault
                        autoRotate
                        autoRotateSpeed={0.5}
                    />

                    <ambientLight intensity={0.5} />
                    <pointLight position={[10, 10, 10]} intensity={1} />
                    <spotLight position={[0, 5, 0]} intensity={2} penumbra={1} castShadow />

                    <React.Suspense fallback={null}>
                        <SatelliteModel faultySystems={faultySystems} />
                        <ContactShadows
                            position={[0, -2, 0]}
                            opacity={0.4}
                            scale={10}
                            blur={2}
                            far={4.5}
                        />
                    </React.Suspense>

                    <Environment preset="night" />
                </Canvas>

                {/* HUD Elements */}
                <div className="absolute bottom-6 left-6 right-6 flex justify-between items-end pointer-events-none">
                    <div className="space-y-2">
                        <div className="flex gap-2">
                            <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-400 text-[10px] font-bold rounded ring-1 ring-cyan-500/30">X-RAY ACTIVE</span>
                            <span className="px-2 py-0.5 bg-white/5 text-white/40 text-[10px] font-bold rounded border border-white/10 uppercase font-mono tracking-tighter">ASTRA-LIDAR 1.0</span>
                        </div>
                        <p className="text-[10px] text-white/30 font-mono">DRAG TO ROTATE • SCROLL TO ZOOM</p>
                    </div>

                    {faultySystems.length > 0 && (
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            className="px-4 py-2 bg-red-500/20 border border-red-500/30 rounded-lg backdrop-blur-md"
                        >
                            <p className="text-red-400 text-[10px] font-bold uppercase tracking-widest flex items-center gap-2">
                                <Activity className="w-3 h-3 animate-pulse" />
                                Hardware Alert: {faultySystems.join(', ')} Critical
                            </p>
                        </motion.div>
                    )}
                </div>
            </div>

            {/* Subsystem sidebar */}
            <div className="space-y-4">
                <h3 className="text-xs font-bold text-white/40 uppercase tracking-[0.2em] px-2 mb-2">Hardware Nodes</h3>

                <StatCard
                    icon={Zap}
                    label="Power Bus (PTU)"
                    value="24.8V"
                    status={faultySystems.includes('Battery') ? 'alert' : 'nominal'}
                />
                <StatCard
                    icon={Target}
                    label="Attitude Control (ACS)"
                    value="0.002°/s"
                    status={faultySystems.includes('ACS') ? 'alert' : 'nominal'}
                />
                <StatCard
                    icon={Radio}
                    label="Downlink Signal"
                    value="-102 dBm"
                    status={faultySystems.includes('Comm') ? 'alert' : 'nominal'}
                />

                <div className="mt-6 p-4 rounded-xl border border-white/5 bg-white/5 space-y-4">
                    <div className="flex justify-between items-center text-[10px] text-white/40 font-bold uppercase tracking-wider">
                        <span>LIDAR Resolution</span>
                        <span className="text-cyan-400">8K - SCANNING</span>
                    </div>
                    <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                        <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: '100%' }}
                            transition={{ duration: 2, repeat: Infinity }}
                            className="h-full bg-cyan-500 shadow-[0_0_10px_#06b6d4]"
                        />
                    </div>
                    <p className="text-[10px] text-white/20 leading-relaxed uppercase font-mono">
                        Direct volumetric visualization active. Synthetic aperture radar providing real-time occlusion clearance for internal bus diagnostics.
                    </p>
                </div>
            </div>
        </div>
    );
};
