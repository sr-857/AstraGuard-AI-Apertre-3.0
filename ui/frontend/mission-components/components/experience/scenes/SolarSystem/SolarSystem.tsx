import { useThree } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import { Planet } from './components/Planet';
import { Earth } from './Earth'
import Sun from './components/Sun';
import { GLOBAL, SOLAR_SYSTEM } from '../../config/config'
import { gsap } from "gsap";
import { useSceneStore } from '../../core/SceneManager'
import { createNavigationAnimation } from '../../utils/navigationAnimation'
import { useNavigation } from '../../hooks/useNavigation'
import { setupZoomCamera } from '../../utils/setupZoomCamera'
import { useMobile } from '../../contexts/MobileContext'
import Stars from './components/Stars';
import Nebula from './components/Nebula';
import { Group, PerspectiveCamera } from 'three'

export function SolarSystem() {
  const { camera } = useThree() as { camera: PerspectiveCamera };

  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  // SolarSystem component handles 2 scenes: solarSystemApproach and solarSystemRotation
  const solarSystemApproachSceneKey = 'solarSystemApproach'
  const solarSystemRotationSceneKey = 'solarSystemRotation'

  const isSolarSystemApproachScene = currentScene === solarSystemApproachSceneKey;
  const isSolarSystemRotationScene = currentScene === solarSystemRotationSceneKey;

  const solarSystemRef = useRef<Group>(null!)
  const earthRef = useRef<Group>(null);

  const { isMobile } = useMobile();

  function initSolarSystemApproach() {
    camera.fov = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV;
    camera.position.set(SOLAR_SYSTEM.ZOOMED_OUT_CAMERA_POS.x, SOLAR_SYSTEM.ZOOMED_OUT_CAMERA_POS.y, SOLAR_SYSTEM.ZOOMED_OUT_CAMERA_POS.z);
    camera.lookAt(SOLAR_SYSTEM.SUN_POSITION);
    camera.updateProjectionMatrix();
  }

  // when just zoomed in from the galaxy to the solar system, set start camera position deep in the space 
  useEffect(() => {
    if (currentScene === solarSystemApproachSceneKey && zoomDirection === 'in') {
      initSolarSystemApproach();
    }
  }, [currentScene])

  // zoom in/out for the solarSystemApproach scene
  function zoomInSolarSystemApproachFunction(backwards: boolean = false) {
    setupZoomCamera(camera, solarSystemApproachSceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    const tl = gsap.timeline({
      onStart: () => {
        console.debug("[SolarSystem] Starting SolarSystem Rotation Animation");
        initSolarSystemApproach();
      },
    });
    tl.to(camera.position, {
      x: SOLAR_SYSTEM.ZOOMED_IN_CAMERA_POS.x,
      y: SOLAR_SYSTEM.ZOOMED_IN_CAMERA_POS.y,
      z: SOLAR_SYSTEM.ZOOMED_IN_CAMERA_POS.z,
    });

    const animation = createNavigationAnimation({
      sceneKey: solarSystemApproachSceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    return () => {
      animation.cleanup();
    };
  }

  // zoom in/out for the solarSystemRotation scene
  function zoomInSolarSystemRotationFunction(backwards: boolean = false) {
    setupZoomCamera(camera, solarSystemRotationSceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    const xzDistance = Math.sqrt(    // calculate radius based on the X and Z distance only
      Math.pow(camera.position.x - SOLAR_SYSTEM.SUN_POSITION.x, 2) +
      Math.pow(camera.position.z - SOLAR_SYSTEM.SUN_POSITION.z, 2)
    );

    const startAngle = Math.atan2( // calculate the current angle in the XZ plane
      camera.position.x - SOLAR_SYSTEM.SUN_POSITION.x,
      camera.position.z - SOLAR_SYSTEM.SUN_POSITION.z
    );

    const cameraY = camera.position.y; // preserve the original Y value

    // start by putting camera exactly on the circle (important!)
    const initialX = SOLAR_SYSTEM.SUN_POSITION.x + xzDistance * Math.sin(startAngle);
    const initialZ = SOLAR_SYSTEM.SUN_POSITION.z + xzDistance * Math.cos(startAngle);
    camera.position.set(initialX, cameraY, initialZ);

    const endAngle = startAngle + Math.PI / 2;

    const animationObject = { angle: startAngle };

    const tl = gsap.timeline();
    tl.to(animationObject, {
      duration: 5,
      angle: endAngle,
      onUpdate: function () {
        const currentAngle = animationObject.angle;

        // use xzDistance instead of radius for consistency
        const newX = SOLAR_SYSTEM.SUN_POSITION.x + xzDistance * Math.sin(currentAngle);
        const newZ = SOLAR_SYSTEM.SUN_POSITION.z + xzDistance * Math.cos(currentAngle);

        camera.position.set(newX, cameraY, newZ);

        camera.lookAt(SOLAR_SYSTEM.SUN_POSITION);
      }
    });

    const animation = createNavigationAnimation({
      sceneKey: solarSystemRotationSceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    return () => {
      animation.cleanup();
    };
  }

  useNavigation({
    sceneKey: solarSystemApproachSceneKey,
    zoomFunction: zoomInSolarSystemApproachFunction,
    isVisible: isSolarSystemApproachScene,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  useNavigation({
    sceneKey: solarSystemRotationSceneKey,
    zoomFunction: zoomInSolarSystemRotationFunction,
    isVisible: isSolarSystemRotationScene,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  return (
    <group ref={solarSystemRef}>
      <ambientLight intensity={0.05} />

      <Stars />
      <Nebula />

      <Sun />
      {SOLAR_SYSTEM.PLANETS.map((item, index) => {
        return <Planet key={index} {...(item as any)} />;
      })}

      <Earth ref={earthRef}
        {...SOLAR_SYSTEM.EARTH_PARAMS} />
    </group>
  )
}
