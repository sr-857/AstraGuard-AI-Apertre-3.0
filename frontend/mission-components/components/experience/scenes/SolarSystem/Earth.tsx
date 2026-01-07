import { useRef, forwardRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Planet } from "./components/Planet";
import { EARTH } from "../../config/config";
import { gsap } from "gsap";
import { useSceneStore } from "../../core/SceneManager";
import { createNavigationAnimation } from "../../utils/navigationAnimation";
import { useNavigation } from "../../hooks/useNavigation";
import { setupZoomCamera } from "../../utils/setupZoomCamera";
import { Group, MathUtils, PerspectiveCamera, Quaternion, Vector3 } from "three";


export const Earth = forwardRef<Group>((props, ref: React.ForwardedRef<Group>) => {
  const { camera } = useThree() as { camera: PerspectiveCamera };

  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  // Earth component handles 2 scenes: earthApproach and earth
  const earthApproachSceneKey = 'earthApproach';
  const earthSceneKey = 'earth';

  const isEarthApproachScene = currentScene === earthApproachSceneKey;
  const isEarthScene = currentScene === earthSceneKey;

  const angleRef = useRef<number | null>(null); // current angle of the camera for zoom in/out

  const earthApproachCameraOffset = EARTH.APPROACH_OFFSET.clone();
  const earthCameraOffset = EARTH.ZOOMED_IN_OFFSET.clone();

  function getZoomedInEarthCameraTargetPosition(offset: Vector3) {
    const earthPosition = new Vector3();
    if (ref && typeof ref !== 'function' && ref.current) {
      ref.current.getWorldPosition(earthPosition);
    }

    // center of the object (earth) + offset
    const center = earthPosition.clone().add(offset);

    if (angleRef.current === null) {
      const offset = camera.position.clone().sub(center);
      angleRef.current = Math.atan2(offset.z, offset.x);
    }

    const baseRadius = center.clone().sub(earthPosition).length();
    const spinRadius = baseRadius * 1; // 1 - orbit radius multiplier, can be used to reduce the orbit radius

    // look at the center of the earth
    const desiredPos = new Vector3(
      earthPosition.x + spinRadius * Math.cos(angleRef.current),
      earthApproachCameraOffset.y,
      earthPosition.z + spinRadius * Math.sin(angleRef.current) - earthApproachCameraOffset.z
    );

    return desiredPos;
  }

  // render
  useFrame(() => {
    // follow earth while looking at it when its earth scene
    if (isEarthScene) {
      const desiredPos = getZoomedInEarthCameraTargetPosition(earthApproachCameraOffset);

      camera.position.copy(desiredPos)

      if (ref && typeof ref !== 'function' && ref.current) {
        const earthPosition = new Vector3();
        ref?.current.getWorldPosition(earthPosition);

        camera.lookAt(earthPosition);
      }
    }
  });

  // zoom in/out for the earthApproach scene
  function zoomInEarthApproachFunction(backwards: boolean = false) {
    setupZoomCamera(camera, earthApproachSceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    // remember start quaternion to smoothly change the camera lookAt from sun to earth
    const startQuaternion = new Quaternion().copy(camera.quaternion);

    const tl = gsap.timeline({
      onStart: () => console.debug("[Earth] Starting Earth Approach Animation"),
      onUpdate: function () {
        const earthPosition = new Vector3();
        if (ref && typeof ref !== 'function' && ref.current) {
          ref?.current.getWorldPosition(earthPosition);
        }

        // get earth position every update because its moving
        let dynamicTarget = (() => {
          let inEarthZoomedInCameraPos = getZoomedInEarthCameraTargetPosition(earthApproachCameraOffset);
          inEarthZoomedInCameraPos.y = earthApproachCameraOffset.y;

          return inEarthZoomedInCameraPos;
        })();

        // lerp the camera position to the target position and quaternion to get smooth camera movement
        // this code probably needs to be refactored to use a more generic function
        const progress = this.progress();

        const newPosition = camera.position.clone().lerp(dynamicTarget, progress);

        camera.position.copy(newPosition);

        const q1 = new Quaternion().copy(startQuaternion);

        const qStart = new Quaternion().copy(camera.quaternion);

        camera.lookAt(earthPosition);
        const qEarth = new Quaternion().copy(camera.quaternion);

        camera.quaternion.copy(qStart);

        camera.quaternion.slerpQuaternions(qStart, qEarth, progress);

        const q2 = new Quaternion().copy(camera.quaternion);

        camera.quaternion.slerpQuaternions(q1, q2, progress);
      },
    });

    tl.to(camera.position, {
      duration: 2,

      // update target position on every frame because is moving
      x: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.x;
      }),
      y: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.y;
      }),
      z: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.z;
      }),
    });

    const animation = createNavigationAnimation({
      sceneKey: earthApproachSceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    return () => {
      animation.cleanup();
    };
  }

  // zoom in/out for the earth scene
  function zoomInEarthFunction(backwards: boolean = false) {
    setupZoomCamera(camera, earthSceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    const startCameraFov = camera.fov;

    const tl = gsap.timeline({
      onUpdate: function () {
        // get earth position every update because its moving
        const earthPosition = new Vector3();
        if (ref && typeof ref !== 'function' && ref.current) {
          ref?.current.getWorldPosition(earthPosition);
        }

        // lerp the camera quaternion and fov to get smooth camera movement and fov change
        const q1 = new Quaternion().copy(camera.quaternion);

        camera.lookAt(earthPosition);

        const q2 = new Quaternion().copy(camera.quaternion);

        camera.quaternion.slerpQuaternions(q1, q2, this.progress());

        camera.lookAt(earthPosition);

        const targetFov = EARTH.ZOOMED_IN_FOV;

        camera.fov = MathUtils.lerp(startCameraFov, targetFov, this.progress());
        camera.updateProjectionMatrix();
      },
    });

    tl.to(camera.position, {
      duration: 1,

      // update target position on every frame because is moving
      x: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.x;
      }),
      y: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.y;
      }),
      z: (() => {
        const targetPosition = getZoomedInEarthCameraTargetPosition(earthCameraOffset);
        return targetPosition.z;
      }),
    });

    const animation = createNavigationAnimation({
      sceneKey: earthSceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    return () => {
      animation.cleanup();
    };
  }

  useNavigation({
    sceneKey: earthApproachSceneKey,
    zoomFunction: zoomInEarthApproachFunction,
    isVisible: isEarthApproachScene,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  useNavigation({
    sceneKey: earthSceneKey,
    zoomFunction: zoomInEarthFunction,
    isVisible: isEarthScene,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  return (
    <group {...props} >
      <Planet {...props} ref={ref} />
    </group>
  );
});