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

export function City() {
  const { viewport, camera } = useThree() as { viewport: any, camera: PerspectiveCamera };
  const {
    currentScene,
    zoomDirection,
    getZoomOutCameraData, setZoomOutCameraData,
    endTransition
  } = useSceneStore();

  const sceneKey = 'city';
  const sceneVisible = currentScene === sceneKey;

  const { isMobile } = useMobile();

  const imagePlaneRef = useRef<Mesh>(null!);
  const cityTexture = useLoader(TextureLoader, SCENE_MANAGER.SCENE_ASSETS.textures.city.city);

  const imagePlanePosition = IMAGE_SCENE.IMAGE_PLANE_POSITION.clone();


  // composer for post processing motion blur effect (zoom in images)
  const composer = useMotionBlurComposer(sceneVisible)

  // render
  useFrame(() => {
    if (composer) {
      composer.render();
    }
  })

  function zoomInCityFunction(backwards: boolean = false) {
    setupZoomCamera(camera, sceneKey, backwards, {
      getZoomOutCameraData,
      setZoomOutCameraData,
      endTransition
    });

    // reset the texture offset and repeat to show the entire image again
    if (backwards) {
      cityTexture.offset.set(0, 0);
      cityTexture.repeat.set(1, 1);
    }

    const imageData = IMAGE_SCENE.IMAGES_DATA[sceneKey]

    // convert the approx target pixel coordinate into normalized UV coordinates
    const targetUV = {
      x: imageData.targetCoords.x / imageData.width,
      y: imageData.targetCoords.y / imageData.height
    };

    const tl = gsap.timeline({
      onStart: () => {
        // set the camera position and look at the center of the image
        camera.position.set(imagePlanePosition.x, imagePlanePosition.y, imagePlanePosition.z + 10);
        camera.lookAt(imagePlanePosition.x, imagePlanePosition.y, imagePlanePosition.z);

        const targetFov = isMobile ? GLOBAL.INITIAL_CAMERA_MOBILE_FOV : GLOBAL.INITIAL_CAMERA_DESKTOP_FOV;
        camera.fov = targetFov;

        if (imagePlaneRef.current) {
          const material = imagePlaneRef.current.material as MeshBasicMaterial;
          material.map = cityTexture;
          material.needsUpdate = true;
        }

        camera.updateProjectionMatrix();
      }
    });

    tl.to(cityTexture.offset, {
      x: targetUV.x,
      y: targetUV.y,
    }).to(
      cityTexture.repeat,
      {
        // lower repeat values show a smaller portion of the image, "zooming in" (lower value = higher zoom)
        x: imageData.targetRepeat.x,
        y: imageData.targetRepeat.y
      },
      "<" // run concurrently
    );

    const animation = createNavigationAnimation({
      sceneKey: sceneKey,
      timeline: tl,
      onComplete: endTransition,
      backwards: backwards,
    });

    // cleanup
    return () => {
      animation.cleanup();
    };
  }

  useNavigation({
    sceneKey: sceneKey,
    zoomFunction: zoomInCityFunction,
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
        <meshBasicMaterial map={cityTexture} />
      </mesh>
    </group>
  );
}
