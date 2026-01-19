import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import { GLOBAL, DEVICE, ROOM, SCENE_MANAGER } from "../../config/config";
import { gsap } from "gsap";
import { useGLTF } from '@react-three/drei';
import { useMobile } from "../../contexts/MobileContext";
import { useSceneStore } from "../../core/SceneManager";
import { createNavigationAnimation } from "../../utils/navigationAnimation";
import { useNavigation } from "../../hooks/useNavigation";
import { setupZoomCamera } from "../../utils/setupZoomCamera";
import Monitor from "./Device/Monitor";
import Phone from "./Device/Phone";
import { PerspectiveCamera, Quaternion, Vector3 } from "three";

export function Room() {
  const { camera } = useThree() as { camera: PerspectiveCamera };

  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  const sceneKey = 'room';
  const sceneVisible = currentScene === sceneKey;

  const { isMobile } = useMobile();

  // load the room model
  const roomGLTF = useGLTF(SCENE_MANAGER.SCENE_ASSETS.models.room.room, true);

  // rotate chair top by 0.8 radians around
  useEffect(() => {
    if (!roomGLTF) return;

    const chairTop = roomGLTF.scene.getObjectByName("ChairTop");
    if (chairTop) {
      const initialRotationY = chairTop.rotation.y;

      gsap.to(chairTop.rotation, {
        duration: 4,
        y: initialRotationY + 0.8,
        ease: "power1.inOut",
        repeat: -1,
        yoyo: true,
        repeatDelay: 0.1
      });
    }
  }, [roomGLTF]);

  // get screen position (monitor or phone) in the room model to zoom in
  function getScreenPosition() {
    let screenPosition: Vector3 = new Vector3(0, 0, 0);

    if (roomGLTF.scene) {
      let deskPosition: Vector3 = new Vector3(0, 0, 0);
      const desk = roomGLTF.scene.getObjectByName("DeskTop"); // top of the desk
      if (desk) {
        desk.getWorldPosition(deskPosition);
      }

      // set relative screen position to the desk position
      if (isMobile) {
        screenPosition = new Vector3(deskPosition.x + DEVICE.PHONE.POSITION_OFFSET.x, DEVICE.PHONE.POSITION_OFFSET.y, deskPosition.z + DEVICE.PHONE.POSITION_OFFSET.z);
      } else {
        const MONITOR_SCREEN_OFFSET = new Vector3(0, 0.5, 0); // offset to look at the monitor's screen, not at the entire monitor

        screenPosition = new Vector3(deskPosition.x + DEVICE.MONITOR.POSITION_OFFSET.x, DEVICE.MONITOR.POSITION_OFFSET.y + MONITOR_SCREEN_OFFSET.y, deskPosition.z + DEVICE.MONITOR.POSITION_OFFSET.z);
      }
    }

    return screenPosition;
  }

  function zoomInMonitorFunction(backwards: boolean = false) {
    setupZoomCamera(camera, sceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    const offset = isMobile ? DEVICE.PHONE.CAMERA_OFFSET.clone() : DEVICE.MONITOR.CAMERA_OFFSET.clone();

    function animateRoomIn() {
      let monitorPosition: Vector3 = new Vector3(0, 0, 0);

      const tl = gsap.timeline();
      tl.call(() => {
        monitorPosition = getScreenPosition();
      })
        // delay
        .to({}, {
          duration: .1,
          onComplete: () => {
            camera.position.set(ROOM.ZOOMED_OUT_CAMERA_POS.x, ROOM.ZOOMED_OUT_CAMERA_POS.y, ROOM.ZOOMED_OUT_CAMERA_POS.z);
            camera.lookAt(monitorPosition);
          },
        })
        // animate the camera to the monitor position
        .to(camera.position, {
          duration: 3,
          x: () => {
            return monitorPosition.x + offset.x; // add some offset to the x position to avoid going through the monitor
          },
          y: () => {
            return monitorPosition.y + offset.y;
          },
          z: () => {
            return monitorPosition.z + offset.z;
          },
          onUpdate: function () {
            // slerp quaternions to smoothly rotate the camera to look at the monitor
            const q1 = new Quaternion().copy(camera.quaternion);

            if (isMobile) {
              monitorPosition.y = 0 // look at the phone from the top
            }

            camera.lookAt(monitorPosition);

            const q2 = new Quaternion().copy(camera.quaternion);

            camera.quaternion.slerpQuaternions(q1, q2, this.progress()); // 0 < time < 1
            camera.updateProjectionMatrix();
          }
        });
      return tl;
    }

    const tl = gsap.timeline({
      onStart: () => {
        camera.position.copy(ROOM.ZOOMED_OUT_CAMERA_POS);
        camera.lookAt(getScreenPosition());

        const targetFov = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV;
        camera.fov = targetFov;
        camera.updateProjectionMatrix();
      }
    });
    tl.add(animateRoomIn(), 0); //  animate room (in)

    const animation = createNavigationAnimation({
      sceneKey: sceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    return () => {
      animation.cleanup();
    };
  }

  useNavigation({
    sceneKey: sceneKey,
    zoomFunction: zoomInMonitorFunction,
    isVisible: sceneVisible,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  return (
    <group>
      <primitive object={roomGLTF.scene} position={[0, -1, 0]} scale={[1, 1, 1]}>
        <Monitor roomGLTF={roomGLTF} />
        <Phone roomGLTF={roomGLTF} />
      </primitive>
    </group>
  );
}
