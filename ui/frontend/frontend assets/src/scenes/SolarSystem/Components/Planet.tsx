import React, { useMemo, useRef, forwardRef } from "react";
import { useFrame, useLoader } from "@react-three/fiber";
import {
  Group,
  Color,
  DoubleSide,
  RingGeometry,
  TextureLoader,
  ShaderMaterial,
  SRGBColorSpace,
  AdditiveBlending,
  MeshPhongMaterial,
  MeshBasicMaterial,
  IcosahedronGeometry,
  Mesh as ThreeMesh,
  Vector3,
  Material,
} from "three";
import { planetGlowFragmentShader, planetGlowVertexShader, planetNightTextureFragmentShader, planetNightTextureVertexShader } from "../../../shaders/planetShaders";
import { SCENE_MANAGER } from "../../../config/config";

export interface RingsOptions {
  ringsSize: number;
  ringsTexture: string;
}

export interface PlanetOptions {
  orbitSpeed?: number;
  orbitRadius?: number;
  orbitRotationDirection?: "clockwise" | "counterclockwise";
  planetSize?: number;
  planetAngle?: number;
  planetRotationSpeed?: number;
  planetRotationDirection?: "clockwise" | "counterclockwise";
  planetTexture?: string;
  planetNightTexture?: string | null;
  planetCloudsTexture?: string;
  rimHex?: number;
  facingHex?: number;
  rings?: RingsOptions | null;
}

// base from https://dev.to/cookiemonsterdev/solar-system-with-threejs-3fe0
export const Planet = forwardRef<Group, PlanetOptions & JSX.IntrinsicElements["group"]>(({
  orbitSpeed = 1,
  orbitRadius = 1,
  orbitRotationDirection = "clockwise",
  planetSize = 1,
  planetAngle = 0,
  planetRotationSpeed = 1,
  planetRotationDirection = "clockwise",
  planetTexture = SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.mercury,
  planetNightTexture = null,
  planetCloudsTexture = null,
  rimHex = 0x0088ff,
  facingHex = 0x000000,
  rings = null,
  ...props
}, ref) => {
  const groupRef = useRef<Group>(null!);
  const planetGroupRef = (ref as React.MutableRefObject<Group>) || useRef<Group>(null!);

  const texture = useLoader(TextureLoader, planetTexture);
  const planetMaterial = useMemo(() => {
    if (planetNightTexture) {
      // planet night texture combined with day texture (night texture is visible when light from the sun is not hitting the planet)
      const nightMap = useLoader(TextureLoader, planetNightTexture);

      const uniforms = {
        dayTexture: { value: texture },
        nightTexture: { value: nightMap },
        sunDirection: { value: new Vector3(1, 0, 0) }
      };

      return new ShaderMaterial({
        uniforms,
        vertexShader: planetNightTextureVertexShader,
        fragmentShader: planetNightTextureFragmentShader,
      });
    } else {
      const mat = new MeshPhongMaterial({ map: texture });
      if (mat.map) {
        mat.map.colorSpace = SRGBColorSpace;
      }
      return mat;
    }

  }, [texture, planetNightTexture]);

  // clouds
  let cloudsMaterial: Material | null = null;
  if (planetCloudsTexture) {
    const cloudsTexture = useLoader(TextureLoader, planetCloudsTexture);

    cloudsMaterial = useMemo(() =>
      new MeshBasicMaterial({
        map: cloudsTexture,
        alphaMap: cloudsTexture,
        transparent: true,
        opacity: .9,
        blending: AdditiveBlending,
        depthWrite: false // prevents z-fighting with atmosphere
      }), [cloudsTexture]);
  }

  const planetGeometry = useMemo(() => new IcosahedronGeometry(planetSize, 12), [planetSize]);

  const glowMaterial = useMemo(() => {
    const uniforms = {
      color1: { value: new Color(rimHex) },
      color2: { value: new Color(facingHex) },
      fresnelBias: { value: 0.2 },
      fresnelScale: { value: 0.1 },
      fresnelPower: { value: 1.0 },
    };

    return new ShaderMaterial({
      uniforms,
      vertexShader: planetGlowVertexShader,
      fragmentShader: planetGlowFragmentShader,
      transparent: true,
      blending: AdditiveBlending,
    });
  }, [rimHex, facingHex]);

  // create rings mesh if provided
  const ringsTexture = rings ? useLoader(TextureLoader, rings.ringsTexture) : null;
  const ringsMesh = useMemo(() => {
    if (!rings) return null;
    const innerRadius = planetSize + 0.1;
    const outerRadius = innerRadius + rings.ringsSize;
    const geometry = new RingGeometry(innerRadius, outerRadius, 32);
    const material = new MeshBasicMaterial({ side: DoubleSide, transparent: true, map: ringsTexture! });
    const mesh = new ThreeMesh(geometry, material);
    mesh.rotation.x = Math.PI / 2;
    return mesh;
  }, [rings, planetSize, ringsTexture]);

  // animate orbit and planet rotation
  useFrame(() => {
    if (groupRef.current) {
      if (groupRef.current.rotation.y === 0) {
        // move the planet from the starting position.
        groupRef.current.rotation.y = orbitRotationDirection === "clockwise" ? -orbitSpeed * 10000 : orbitSpeed * 10000;
      }
      groupRef.current.rotation.y += orbitRotationDirection === "clockwise" ? -orbitSpeed : orbitSpeed;
    }
    if (planetGroupRef.current) {
      planetGroupRef.current.rotation.y += planetRotationDirection === "clockwise" ? -planetRotationSpeed : planetRotationSpeed;
    }
  });

  return (
    <group ref={groupRef} {...props}>
      <group ref={planetGroupRef} position={[orbitRadius - planetSize / 9, 0, 0]} rotation-z={planetAngle}>
        <mesh geometry={planetGeometry} material={planetMaterial} />

        {cloudsMaterial && <mesh geometry={planetGeometry} material={cloudsMaterial} scale={[1.005, 1.005, 1.005]} />}
        <mesh geometry={planetGeometry} material={glowMaterial} scale={[1.05, 1.05, 1.05]} />

        {ringsMesh && <primitive object={ringsMesh} />}
      </group>
    </group>
  );
});