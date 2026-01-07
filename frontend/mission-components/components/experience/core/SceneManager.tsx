import { Quaternion, Vector3 } from 'three';
import { create } from 'zustand';
import { SCENE_MANAGER } from '../config/config';

export type SceneType = typeof SCENE_MANAGER.SCENE_ORDER[number];
export type CameraData = { position: Vector3; quaternion: Quaternion; fov: number };

interface SceneState {
  loadingProgress: number; // loading progress of all assets
  loadingText?: string; // loading text (optional)

  currentScene: SceneType; // current scene name (key)

  zoomDirection: 'in' | 'out' | null; // after switching scene you can determine if the previous one was zoomed in or out
  sceneZoomed: 'in' | 'out' | null; // if current scene zoomed in or out (progress is 0 or 1 within the same scene, sets in navigationAnimation)

  isFullscreenActive: boolean; // is the fullscreen html active

  zoomOutCameraData: Record<SceneType, CameraData>; // save camera data for all scenes before zooming in, used to set back after zooming out to recreate the same view

  // actions
  setLoadingProgress: (progress: number) => void; // set loading progress of all assets
  setLoadingText: (text: string) => void; // set loading text (optional)

  setSceneZoomed: (zoomed: 'in' | 'out' | null) => void; // set zoomed state for the current scene, it will reset when the scene is switched

  setFullscreenActive: (isActive: boolean) => void; // set fullscreen html active state

  getZoomOutCameraData: (scene: SceneType) => { position: Vector3; quaternion: Quaternion; fov: number }; // get zoom out camera data for the current scene (used to set back after zooming out)
  setZoomOutCameraData: (scene: SceneType, data: { position: Vector3; quaternion: Quaternion; fov: number }) => void; // set zoom out camera data for the current scene (used to save before zooming in)

  endTransition: (isZoomIn: boolean) => void; // called when zoom animation ends to switch the scene to next/previous one
}

export const useSceneStore = create<SceneState>((set, get) => ({
  loadingProgress: 0,
  loadingText: undefined,

  currentScene: 'galaxy', // start scene

  zoomDirection: null,
  sceneZoomed: null,

  isFullscreenActive: false,

  // set default zoom out camera data for all scenes
  // used to save before zooming in and set back after zooming out
  zoomOutCameraData: Object.fromEntries(
    SCENE_MANAGER.SCENE_ORDER.map(scene => [scene, SCENE_MANAGER.ZOOM_OUT_CAMERA_DATA_DEFAULT])
  ) as Record<SceneType, typeof SCENE_MANAGER.ZOOM_OUT_CAMERA_DATA_DEFAULT>,

  setLoadingProgress: (progress) => set({ loadingProgress: progress }),
  setLoadingText: (text) => set({ loadingText: text }), // set loading text (optional)

  setSceneZoomed: (zoomed: 'in' | 'out' | null) => {
    set({ sceneZoomed: zoomed });
  },

  setFullscreenActive: (isActive: boolean) => {
    set({ isFullscreenActive: isActive });
  },

  getZoomOutCameraData: (scene: SceneType) => {
    const { zoomOutCameraData } = get();
    return zoomOutCameraData[scene];
  },

  setZoomOutCameraData: (scene: SceneType, data: { position: Vector3; quaternion: Quaternion; fov: number }) => {
    set((state) => ({
      zoomOutCameraData: {
        ...state.zoomOutCameraData,
        [scene]: data
      }
    }));
  },

  endTransition: (isZoomIn: boolean) => {
    const { currentScene } = get();
    const currentIndex = SCENE_MANAGER.SCENE_ORDER.indexOf(currentScene);

    if (isZoomIn) {
      const nextIndex = Math.min(currentIndex + 1, SCENE_MANAGER.SCENE_ORDER.length - 1);
      const nextScene = SCENE_MANAGER.SCENE_ORDER[nextIndex] as SceneType;

      if (nextScene !== currentScene) { // end point, nowhere to go
        console.debug(`[SceneManager] Extracting to next scene: ${currentScene} -> ${nextScene}`);
        set({
          currentScene: nextScene,
          zoomDirection: 'in',
          sceneZoomed: null
        });
      }
    } else {
      const prevIndex = Math.max(currentIndex - 1, 0);
      const prevScene = SCENE_MANAGER.SCENE_ORDER[prevIndex] as SceneType;

      if (prevScene !== currentScene) { // end point, nowhere to go
        set({
          currentScene: prevScene,
          zoomDirection: 'out',
          sceneZoomed: null
        });
      }
    }
  }
}));