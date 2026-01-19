import { useRef } from "react";
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import { IMAGE_SCENE, GLOBAL, SCENE_MANAGER } from "../../config/config";
import { gsap } from "gsap";
import { useSceneStore } from "../../core/SceneManager";
import { createNavigationAnimation } from "../../utils/navigationAnimation";
import { useNavigation } from "../../hooks/useNavigation";
import { useMotionBlurComposer } from "../../hooks/usePostProcessing";
import { setupZoomCamera } from "../../utils/setupZoomCamera";
import { useMobile } from "../../contexts/MobileContext";
import { Mesh, MeshBasicMaterial, PerspectiveCamera, TextureLoader } from "three";

export function District() {
  const { viewport, camera } = useThree() as { viewport: any, camera: PerspectiveCamera };

  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  const sceneKey = 'district';
  const sceneVisible = currentScene === sceneKey;

  const { isMobile } = useMobile();

  const imagePlaneRef = useRef<Mesh>(null!);
  const districtTexture = useLoader(TextureLoader, SCENE_MANAGER.SCENE_ASSETS.textures.district.district);

  const imagePlanePosition = IMAGE_SCENE.IMAGE_PLANE_POSITION.clone();

  // composer for post processing motion blur effect (zoom in images)
  const composer = useMotionBlurComposer(sceneVisible);

  // render
  useFrame(() => {
    if (composer) {
      composer.render();
    }
  })

  function zoomInDistrictFunction(backwards: boolean = false) {
    setupZoomCamera(camera, sceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    // reset the texture offset and repeat to show the entire image again
    if (backwards) {
      districtTexture.offset.set(0, 0);
      districtTexture.repeat.set(1, 1);
    }

    const imageData = IMAGE_SCENE.IMAGES_DATA[sceneKey]

    // convert the approx target pixel coordinate into normalized UV coordinates
    const targetUV = {
      x: imageData.targetCoords.x / imageData.width,
      y: imageData.targetCoords.y / imageData.height
    };

    // zoom in sequence: satellite picture (Europe continent) -> city picture (Hannover) -> district picture (hannover3D) -> room model (gltf)
    // pictures are zoomed in with a motion blur effect and then the camera is animated to the room model's monitor

    const tl = gsap.timeline({
      onStart: () => {
        // set the camera position and look at the center of the image
        camera.position.set(imagePlanePosition.x, imagePlanePosition.y, imagePlanePosition.z + 10);
        camera.lookAt(imagePlanePosition.x, imagePlanePosition.y, imagePlanePosition.z);

        const targetFov = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV;
        camera.fov = targetFov;

        if (imagePlaneRef.current) {
          const material = imagePlaneRef.current.material as MeshBasicMaterial;
          material.map = districtTexture;
          material.needsUpdate = true;
        }

        camera.updateProjectionMatrix();
      }
    });

    tl.to(districtTexture.offset, {
      duration: 1,
      x: targetUV.x,
      y: targetUV.y
    }).to(districtTexture.repeat, {
      duration: 1,
      x: imageData.targetRepeat.x,
      y: imageData.targetRepeat.y
    }, "<" // run concurrently 
    );

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
    zoomFunction: zoomInDistrictFunction,
    isVisible: sceneVisible,
    zoomDirection: zoomDirection,
    getZoomOutCameraData: getZoomOutCameraData
  });

  const getImagePlaneSize = () => {
    const imageData = IMAGE_SCENE.IMAGES_DATA[sceneKey];
    const imageAspect = imageData.width / imageData.height;

    // on mobile make it fit the screen properly
    if (isMobile) {
      return {
        width: window.innerWidth * camera.aspect * imageAspect / 10,
        height: window.innerHeight * camera.aspect / 15,
      };
    }

    return {
      width: viewport.width,
      height: viewport.height,
    };
  };

  const planeSize = getImagePlaneSize();

  return (
    <group>
      <mesh ref={imagePlaneRef} position={imagePlanePosition}>
        <planeGeometry args={[planeSize.width, planeSize.height]} />
        <meshBasicMaterial map={districtTexture} />
      </mesh>
    </group>
  );
}
