import { useRef, useMemo } from 'react'
import { SCENE_MANAGER, SOLAR_SYSTEM } from '../../../config/config';
import { AdditiveBlending, BufferGeometry, Color, Float32BufferAttribute, Group, MathUtils, Points, PointsMaterial, TextureLoader } from 'three';

function Nebula() {
    const groupRef = useRef<Group | null>(null);

    // nebula particles
    const nebulaParticles = useMemo(() => {
        const spread = SOLAR_SYSTEM.NEBULA.PARTICLE_SPREAD;

        const particles = [];
        for (let i = 0; i < SOLAR_SYSTEM.NEBULA.PARTICLE_COUNT; i++) {
            const x = MathUtils.randFloatSpread(spread);
            const y = MathUtils.randFloatSpread(spread);
            const z = MathUtils.randFloatSpread(spread);
            particles.push(x, y, z);
        }

        return particles;
    }, []);

    const nebulaGeometry = useMemo(() => {
        const geometry = new BufferGeometry();
        geometry.setAttribute('position', new Float32BufferAttribute(nebulaParticles, 3));
        return geometry;
    }, [nebulaParticles]);

    const nebulaClustersRef = useRef<Points[]>([]);

    const nebulaColors = SOLAR_SYSTEM.NEBULA.COLORS.map(color => new Color(color));

    const nebulaTexture = useMemo(() =>
        new TextureLoader().load(SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.smoke),
        []);

    const nebulaMaterials = useMemo(() => {
        return nebulaColors.map(color => new PointsMaterial({
            size: SOLAR_SYSTEM.NEBULA.MATERIAL_SIZE,
            transparent: true,
            depthWrite: false,
            blending: AdditiveBlending,
            opacity: SOLAR_SYSTEM.NEBULA.MATERIAL_OPACITY,
            map: nebulaTexture,
            color: color.multiplyScalar(SOLAR_SYSTEM.NEBULA.COLOR_MULTIPLIER) // make colors darker
        }));
    }, [nebulaTexture]);

    const nebula = useMemo(() => {
        const nebulaClusters: Points[] = [];

        const spread = SOLAR_SYSTEM.NEBULA.CLUSTER_SPREAD;

        nebulaColors.forEach((_, index) => {
            const nebula = new Points(nebulaGeometry, nebulaMaterials[index]);

            // position each nebula in different regions
            nebula.position.set(
                MathUtils.randFloatSpread(spread),
                MathUtils.randFloatSpread(spread),
                MathUtils.randFloatSpread(spread)
            );

            nebulaClusters.push(nebula);
        })

        nebulaClustersRef.current = nebulaClusters;

        return nebulaClusters;
    }, [nebulaGeometry]);

    return (
        <group ref={groupRef}>
            {nebula.map((nebulaPoints, index) => (
                <primitive
                    key={`nebula-${index}`}
                    object={nebulaPoints}
                    frustumCulled={true}
                />
            ))}
        </group>
    );
}

export default Nebula;