import { PerspectiveCamera, Quaternion, Vector3 } from 'three';
import { SCENE_MANAGER } from '../config/config';

// Sets up camera for zoom transitions, handling both directions
// when zooming in, it saves the current camera data (before zoomed in, so initial position)
// when zooming out, it restores the saved camera data (after zoomed out, so initial position to restore the animation timeline)
export function setupZoomCamera(
  camera: PerspectiveCamera,
  sceneKey: string,
  backwards: boolean,
  { getZoomOutCameraData, setZoomOutCameraData, endTransition }: {
    getZoomOutCameraData: (sceneKey: string) => { position: Vector3; quaternion: Quaternion; fov: number } | undefined;
    setZoomOutCameraData: (sceneKey: string, data: { position: Vector3; quaternion: Quaternion; fov: number }) => void;
    endTransition: (success: boolean) => void;
  }
) {
  if (!backwards) {
    // save current camera data when zooming in
    setZoomOutCameraData(sceneKey, {
      position: camera.position.clone(),
      quaternion: camera.quaternion.clone(),
      fov: camera.fov,
    });
  } else {
    // restore camera data when zooming out
    const zoomOutCameraData = getZoomOutCameraData(sceneKey);
    if (zoomOutCameraData) {
      camera.position.copy(zoomOutCameraData.position);
      camera.quaternion.copy(zoomOutCameraData.quaternion);
      camera.fov = zoomOutCameraData.fov;
      camera.updateProjectionMatrix();
    }
    else if (
      SCENE_MANAGER.SCENE_ORDER.indexOf(sceneKey) > 0 && (zoomOutCameraData === SCENE_MANAGER.ZOOM_OUT_CAMERA_DATA_DEFAULT)
    ) { // it happens when the user just switched to the scene and didn't zoom in to set the camera data yet, so no zoom out is possible - just switch scene back 
      endTransition(false);
      return;
    }
  }
}