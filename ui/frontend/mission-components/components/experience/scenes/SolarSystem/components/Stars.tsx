import { useRef, useMemo } from 'react'
import { useLoader } from '@react-three/fiber';
import { SCENE_MANAGER, SOLAR_SYSTEM } from '../../../config/config';
import { AdditiveBlending, BufferGeometry, Float32BufferAttribute, Group, MathUtils, PointsMaterial, TextureLoader } from 'three';

function Stars() {
    const starTexture = useLoader(TextureLoader, SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.disc);
    const groupRef = useRef<Group | null>(null);

    // generate stars positions
    const stars = useMemo(() => {
        const tempStars = [];
        for (let i = 0; i < SOLAR_SYSTEM.STARS.COUNT; i++) {
            const spread = SOLAR_SYSTEM.STARS.SPREAD;
            const x = MathUtils.randFloatSpread(spread);
            const y = MathUtils.randFloatSpread(spread);
            const z = MathUtils.randFloatSpread(spread);
            tempStars.push(x, y, z);
        }
        return tempStars;
    }, []);

    // create stars geometry
    const starsGeometry = useMemo(() => {
        const geometry = new BufferGeometry();
        geometry.setAttribute(
            "position", new Float32BufferAttribute(stars, 3)
        );
        return geometry;
    }, [stars]);

    const starsMaterial = useMemo(() => new PointsMaterial({
        color: SOLAR_SYSTEM.STARS.MATERIAL_COLOR,
        size: SOLAR_SYSTEM.STARS.MATERIAL_SIZE,
        map: starTexture,
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
    }), [starTexture]);

    return (
        <group ref={groupRef}>
            <points geometry={starsGeometry} material={starsMaterial} />
        </group>
    );
}

export default Stars;