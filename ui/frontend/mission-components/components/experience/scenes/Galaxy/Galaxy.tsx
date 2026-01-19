import { Points, useGLTF } from '@react-three/drei'
import { GLTF } from 'three-stdlib'
import { useFrame, useLoader, useThree } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import { GALAXY, GLOBAL, SCENE_MANAGER } from '../../config/config'
import { useSceneStore } from '../../core/SceneManager'
import { gsap } from 'gsap'
import { createNavigationAnimation } from '../../utils/navigationAnimation';
import { useNavigation } from '../../hooks/useNavigation'
import { useBloomComposer } from '../../hooks/usePostProcessing'
import { setupZoomCamera } from '../../utils/setupZoomCamera'
import { useMobile } from '../../contexts/MobileContext'
import { Color, Group, MathUtils, Mesh, MeshBasicMaterial, PerspectiveCamera, PointsMaterial, TextureLoader, Vector3 } from 'three'

export function Galaxy() {
  const { camera } = useThree() as { camera: PerspectiveCamera };

  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  const sceneKey = 'galaxy'
  const sceneVisible = currentScene === sceneKey;

  const { isMobile } = useMobile();

  const galaxyRef = useRef<Group>(null!)
  const solarSystemStarRef = useRef<Mesh>(null!); // ref of the solar system star (star in the middle of the galaxy)

  const starTexture = useLoader(TextureLoader, SCENE_MANAGER.SCENE_ASSETS.textures.galaxy.disc)

  // load the galaxy model
  const { nodes } = useGLTF(SCENE_MANAGER.SCENE_ASSETS.models.galaxy.galaxy) as unknown as GLTF & {
    nodes: {
      Object_2: Mesh
    }
    materials: {
      ['Scene_-_Root']: PointsMaterial
    }
  }
  const [positions, colors] = useMemo(() => {
    nodes.Object_2.geometry.center()
    const positions = new Float32Array(
      nodes.Object_2.geometry.attributes.position.array.buffer
    )
    const colors = new Float32Array(positions.length)

    const getDistanceToCenter = (x: number, y: number, z: number) =>
      Math.sqrt(x * x + y * y + z * z)

    // make colors closer to 0, 0, 0 be more reddish and colors further away be more blueish
    const color = new Color()
    for (let i = 0; i < positions.length; i += 3) {
      const x = positions[i]
      const y = positions[i + 1]
      const z = positions[i + 2]
      const distanceToCenter = getDistanceToCenter(x, y, z)
      const normalizedDistanceToCenter = distanceToCenter / 100

      color.setRGB(
        Math.cos(normalizedDistanceToCenter),
        MathUtils.randFloat(0, 0.8),
        Math.sin(normalizedDistanceToCenter)
      )
      color.toArray(colors, i)
    }
    return [positions, colors]
  }, [nodes])

  const composer = useBloomComposer(sceneVisible);

  // render
  useFrame(({ clock, camera }) => {
    // slowly rotate the galaxy
    galaxyRef.current.rotation.z = clock.getElapsedTime() / 15

    // solar system star size based on distance to camera (closer = bigger)
    if (solarSystemStarRef?.current) {
      const objectPosition = new Vector3();
      solarSystemStarRef.current.getWorldPosition(objectPosition);

      const dist = objectPosition.distanceTo(camera.position);

      let starSize = 1 / (dist * 0.5);
      starSize = Math.max(GALAXY.SOLAR_SYSTEM_STAR.SIZE_MIN, Math.min(starSize, GALAXY.SOLAR_SYSTEM_STAR.SIZE_MAX));
      solarSystemStarRef.current.scale.set(starSize, starSize, starSize);
    }

    // render bloom
    if (composer) {
      composer.render();
    }
  })

  function zoomInGalaxyFunction(backwards: boolean = false) {
    setupZoomCamera(camera, 'galaxy', backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    if (!solarSystemStarRef.current) return

    const initial = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_POS : GLOBAL.INITIAL_CAMERA_DESKTOP_POS;

    const tweenObj = { progress: 0 };

    const tl = gsap.timeline({
      onUpdate: function () {
        if (!solarSystemStarRef.current) return;

        const solarSystemStarPosition = new Vector3();
        solarSystemStarRef.current.getWorldPosition(solarSystemStarPosition);

        const material = solarSystemStarRef.current.material as MeshBasicMaterial;

        const distanceToSolarSystemStar = solarSystemStarPosition.distanceTo(camera.position);
        if (distanceToSolarSystemStar < GALAXY.STAR_ZOOM_EFFECT_DISTANCE) { // zoomed in too close to the star - make zoom in effect
          camera.position.copy(solarSystemStarPosition).add(GALAXY.SOLAR_SYSTEM_STAR.CAMERA_OFFSET.clone());

          const minFov = GALAXY.SOLAR_SYSTEM_STAR.ZOOMED_IN_FOV;
          const maxFov = camera.fov;
          camera.fov = MathUtils.lerp(maxFov, minFov, .9);

          material.color.set(0x000) // make the star black when zoomed in
        } else {
          const minFov = camera.fov;
          const maxFov = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV;
          camera.fov = MathUtils.lerp(maxFov, minFov, .1);

          material.color.set(GALAXY.SOLAR_SYSTEM_STAR.COLOR) // reset the star color when zoomed out
        }

        camera.updateProjectionMatrix();
      },
    });

    tl.to(tweenObj, {
      progress: 1,
      onUpdate: function () {
        let dynamicTarget = (() => {
          const pos = new Vector3();
          if (solarSystemStarRef.current) {
            solarSystemStarRef.current.getWorldPosition(pos);
          }
          pos.add(GALAXY.SOLAR_SYSTEM_STAR.CAMERA_OFFSET.clone());
          return pos;
        })();

        const newPosition = initial.clone().lerp(dynamicTarget, tweenObj.progress);
        camera.position.copy(newPosition);

        camera.updateProjectionMatrix();
      }
    });

    const animation = createNavigationAnimation({
      sceneKey: sceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
      zoomDirections: { in: true, out: false },
    });

    return () => {
      animation.cleanup();
    };
  }

  useNavigation({
    sceneKey: sceneKey,
    zoomFunction: zoomInGalaxyFunction,
    isVisible: sceneVisible,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  return (
    <group dispose={null} ref={galaxyRef}>
      <pointLight
        position={[0, 0, 0]}
        intensity={0.5}
      />
      <ambientLight intensity={0.5} />

      <Points scale={0.05} positions={positions} colors={colors}>
        <pointsMaterial
          map={starTexture}
          transparent
          depthWrite={false}
          vertexColors
          opacity={1}
          depthTest
          size={0.01}
        />
      </Points>

      <group name="SolarSystemStar">
        <mesh
          ref={solarSystemStarRef}
          position={GALAXY.SOLAR_SYSTEM_STAR.INIT_POSITION}
        >
          <sphereGeometry args={GALAXY.SOLAR_SYSTEM_STAR.INIT_SIZE} />
          <meshBasicMaterial map={starTexture} color={GALAXY.SOLAR_SYSTEM_STAR.COLOR} />
        </mesh>
      </group>
    </group>
  );
}
