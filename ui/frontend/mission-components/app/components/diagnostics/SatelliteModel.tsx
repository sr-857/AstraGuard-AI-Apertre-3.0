import * as React from 'react';
import { useFrame } from '@react-three/fiber';
import './XRayMaterial'; // Register shader material

interface SubSystemProps {
    position: [number, number, number];
    size: [number, number, number];
    color?: string;
    isPulsing?: boolean;
    name: string;
}

const SubSystem = ({ position, size, color = '#00f2ff', isPulsing = false }: SubSystemProps) => {
    const materialRef = React.useRef<any>();

    useFrame((state) => {
        if (materialRef.current) {
            if (isPulsing) {
                // Pulse logic: Sin wave oscillation between 0 and 1
                materialRef.current.uPulse = Math.sin(state.clock.elapsedTime * 5) * 0.5 + 0.5;
            } else {
                materialRef.current.uPulse = 0;
            }
        }
    });

    const XRayMat: any = 'xRayShaderMaterial';

    return (
        <mesh position={position}>
            <boxGeometry args={size} />
            <XRayMat
                ref={materialRef}
                transparent
                uColor={color}
                uOpacity={0.6}
                uFresnelPower={1.5}
            />
        </mesh>
    );
};

interface SatelliteModelProps {
    faultySystems?: string[];
}

export const SatelliteModel = ({ faultySystems = [] }: SatelliteModelProps) => {
    const groupRef = React.useRef<any>();
    const XRayMat: any = 'xRayShaderMaterial';

    useFrame((state) => {
        if (groupRef.current) {
            groupRef.current.rotation.y += 0.005;
            groupRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.2) * 0.1;
        }
    });

    return (
        <group ref={groupRef}>
            {/* Main Bus (Chassis) */}
            <mesh>
                <boxGeometry args={[1.5, 2, 1.5]} />
                <XRayMat
                    transparent
                    uOpacity={0.2}
                    uFresnelPower={3.0}
                />
            </mesh>

            {/* Solar Arrays */}
            <mesh position={[2, 0, 0]}>
                <boxGeometry args={[2.5, 1, 0.1]} />
                <XRayMat transparent uOpacity={0.4} />
            </mesh>
            <mesh position={[-2, 0, 0]}>
                <boxGeometry args={[2.5, 1, 0.1]} />
                <XRayMat transparent uOpacity={0.4} />
            </mesh>

            {/* Internal Sub-Systems (X-Ray Targets) */}
            <SubSystem
                name="Battery"
                position={[0, 0.5, 0]}
                size={[0.8, 0.6, 0.8]}
                isPulsing={faultySystems.includes('Battery')}
            />

            <SubSystem
                name="ACS"
                position={[0, -0.5, 0.2]}
                size={[0.6, 0.4, 0.6]}
                isPulsing={faultySystems.includes('ACS')}
                color="#00ffd5"
            />

            <SubSystem
                name="Comm"
                position={[0, 1.2, 0]}
                size={[1.1, 0.3, 1.1]}
                isPulsing={faultySystems.includes('Comm')}
                color="#b3ff00"
            />

            {/* Antenna Dish */}
            <mesh position={[0, 1.6, 0]}>
                <cylinderGeometry args={[0.8, 0.2, 0.4, 32]} />
                <XRayMat transparent uOpacity={0.5} />
            </mesh>
        </group>
    );
};
