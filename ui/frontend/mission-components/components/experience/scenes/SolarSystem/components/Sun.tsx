import { useRef, useMemo } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import { sunFragmentShaderCorona, sunFragmentShaderSurface, sunVertexShaderCorona, sunVertexShaderSurface } from "../../../shaders/sunShaders";
import { SCENE_MANAGER, SOLAR_SYSTEM } from "../../../config/config";
import { AdditiveBlending, BackSide, Group, IcosahedronGeometry, Mesh, PointLight, ShaderMaterial, SphereGeometry, TextureLoader } from "three";

function Sun(props: JSX.IntrinsicElements["group"]) {
    const groupRef = useRef<Group>(null!);

    const sunTexture = useLoader(TextureLoader, SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.sun);

    const sunMaterial = useMemo(() => {
        return new ShaderMaterial({
            uniforms: {
                sunTexture: { value: sunTexture },
                time: { value: 0.0 },
            },
            vertexShader: sunVertexShaderSurface,
            fragmentShader: sunFragmentShaderSurface,
            depthWrite: false,
        });
    }, [sunTexture]);

    const sunGeometry = useMemo(() => new IcosahedronGeometry(SOLAR_SYSTEM.SUN.RADIUS, SOLAR_SYSTEM.SUN.DETAIL), []);
    const sunMesh = useMemo(() => new Mesh(sunGeometry, sunMaterial),
        [sunGeometry, sunMaterial]);

    const sunLight = useMemo(() => {
        const light = new PointLight(SOLAR_SYSTEM.SUN.LIGHT.COLOR, SOLAR_SYSTEM.SUN.LIGHT.INTENSITY,
            SOLAR_SYSTEM.SUN.LIGHT.DISTANCE, SOLAR_SYSTEM.SUN.LIGHT.DECAY
        );
        light.position.set(SOLAR_SYSTEM.SUN.POSITION.x, SOLAR_SYSTEM.SUN.POSITION.y, SOLAR_SYSTEM.SUN.POSITION.z);
        return light;
    }, []);

    const coronaMaterial = useMemo(() => {
        return new ShaderMaterial({
            uniforms: {
                time: { value: 0.0 },
                coronaColor1: { value: SOLAR_SYSTEM.SUN.CORONA.INNER_CORONA_COLOR }, // inner corona color
                coronaColor2: { value: SOLAR_SYSTEM.SUN.CORONA.OUTER_CORONA_COLOR }, // outer corona color
            },
            vertexShader: sunVertexShaderCorona,
            fragmentShader: sunFragmentShaderCorona,
            side: BackSide,
            blending: AdditiveBlending,
            transparent: true,
            depthWrite: false,
        });
    }, []);

    const coronaMesh = useMemo(() => {
        const geometry = new SphereGeometry(SOLAR_SYSTEM.SUN.CORONA.RADIUS, SOLAR_SYSTEM.SUN.CORONA.DETAIL, SOLAR_SYSTEM.SUN.CORONA.DETAIL);
        const mesh = new Mesh(geometry, coronaMaterial);
        mesh.scale.set(SOLAR_SYSTEM.SUN.CORONA.SCALE, SOLAR_SYSTEM.SUN.CORONA.SCALE, SOLAR_SYSTEM.SUN.CORONA.SCALE); // larger corona
        return mesh;
    }, [coronaMaterial]);

    // animation
    useFrame((state) => {
        const time = state.clock.getElapsedTime();

        if (sunMaterial.uniforms) {
            sunMaterial.uniforms.time.value = time;
        }

        if (coronaMaterial.uniforms) {
            coronaMaterial.uniforms.time.value = time;
        }

        // rotate sun
        if (groupRef.current) {
            groupRef.current.rotation.y = -time * 0.05;
        }
    });

    return (
        <group ref={groupRef} {...props}>
            <primitive object={sunMesh} />
            <primitive object={sunLight} />
            <primitive object={coronaMesh} />
        </group>
    );
}

export default Sun;