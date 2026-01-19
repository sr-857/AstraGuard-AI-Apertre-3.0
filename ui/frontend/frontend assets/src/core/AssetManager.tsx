import { useCallback, useEffect, useMemo, useState } from 'react';
import { useGLTF } from '@react-three/drei';
import { useSceneStore } from './SceneManager';
import { useThree } from '@react-three/fiber';
import { TextureLoader } from 'three';
import { SCENE_MANAGER } from '../config/config';
import React from 'react';
import { ScenePrecompiler } from './ScenePrecompiler';

// scenes
import GalaxyScene from '../scenes/Galaxy/GalaxyScene';
import SolarSystemScene from '../scenes/SolarSystem/SolarSystemScene';
import ContinentScene from '../scenes/Continent/ContinentScene';
import CityScene from '../scenes/City/CityScene';
import DistrictScene from '../scenes/District/DistrictScene';
import RoomScene from '../scenes/Room/RoomScene';

export function AssetManager() {
  const { gl, camera } = useThree();
  const { loadingProgress, setLoadingProgress, setLoadingText } = useSceneStore();

  const [loadedCount, setLoadedCount] = useState(0);
  const [assetsLoaded, setAssetsLoaded] = useState(false);

  const precompileScenes = [
    <GalaxyScene />,
    <SolarSystemScene />,
    <ContinentScene />,
    <CityScene />,
    <DistrictScene />,
    <RoomScene />,
  ];

  const totalAssets = useMemo(() => {
    let count = 0;

    // count models
    Object.values(SCENE_MANAGER.SCENE_ASSETS.models).forEach(models => {
      count += Object.keys(models).length;
    });

    // count textures
    Object.values(SCENE_MANAGER.SCENE_ASSETS.textures).forEach(textures => {
      count += Object.keys(textures).length;
    });

    // count icons
    Object.values(SCENE_MANAGER.SCENE_ASSETS.icons).forEach(icons => {
      count += Object.keys(icons).length;
    });

    count += precompileScenes.length; // add precompile scenes to the count

    return count;
  }, [SCENE_MANAGER.SCENE_ASSETS.models, SCENE_MANAGER.SCENE_ASSETS.textures, precompileScenes]);

  // update loaded count
  const updateProgress = useCallback(() => {
    setLoadedCount(prevCount => prevCount + 1);
  }, [totalAssets]);

  // update loading progress text
  useEffect(() => {
    const progress = (loadedCount / totalAssets) * 100;
    if (progress > 100) {
      setLoadingProgress(100);
      return;
    }

    console.debug(`Loading progress: ${Math.round(progress)}% (${loadedCount}/${totalAssets})`);
    setLoadingProgress(progress);
  }, [loadedCount])

  useEffect(() => {
    console.debug('Start preloading assets...');

    // preload models
    const preloadModels = async () => {
      try {
        // collect models
        const modelEntries: { path: string; scene: string; name: string }[] = [];
        Object.entries(SCENE_MANAGER.SCENE_ASSETS.models).forEach(([scene, models]) => {
          Object.entries(models).forEach(([name, path]) => {
            modelEntries.push({ path: path as string, scene, name });
          });
        });

        // load models in parallel
        const loadedModels = await Promise.all(
          modelEntries.map(({ path }) => {
            useGLTF.preload(path, true); // unfortunately, useGLTF.preload does not give any progress control
          })
        );

        loadedModels.forEach((_, index) => {
          setLoadingText(`Loading models...`);

          console.debug(`Model loaded: ${index}`);

          updateProgress(); // update progress only after each model is loaded
        });
      } catch (error) {
        console.error('Error preloading models:', error);
      }
    };

    // preload textures
    const preloadTextures = async () => {
      const textureLoader = new TextureLoader();

      const textureEntries: { path: string; scene: string; name: string }[] = [];
      Object.entries(SCENE_MANAGER.SCENE_ASSETS.textures).forEach(([scene, textures]) => {
        Object.entries(textures).forEach(([name, path]) => {
          textureEntries.push({ path: path as string, scene, name });
        });
      });

      // create a promise for each texture that resolves when the texture is loaded
      const texturePromises = textureEntries.map(
        ({ path }) =>
          new Promise((resolve, reject) => {
            textureLoader.load(
              path,
              (texture) => {
                setLoadingText(`Loading textures...`);

                console.debug(`Texture loaded: ${path}`);

                // store the texture in the cache for later use
                texture.userData.path = path;

                updateProgress();

                resolve(texture);
              },
              undefined,
              (error) => {
                console.error(`Error loading texture ${path}:`, error);

                reject(error);
              }
            );
          })
      );

      try {
        // wait for all textures to load
        await Promise.all(texturePromises);
      } catch (error) {
        console.error('Error loading textures:', error);
      }
    };

    const preloadIcons = async () => {
      const iconEntries: { path: string; name: string }[] = [];
      Object.entries(SCENE_MANAGER.SCENE_ASSETS.icons.zoomProgressIndicator).forEach(([name, path]) => {
        iconEntries.push({ path: path as string, name });
      });

      // create a promise for each icon, it resolves when the icon is loaded
      const iconPromises = iconEntries.map(
        ({ path }) =>
          new Promise((resolve, reject) => {
            setLoadingText(`Loading interface icons...`);

            const img = new Image();

            img.onload = () => {
              console.debug(`Icon loaded: ${path}`);
              updateProgress();
              resolve(img);
            };

            img.onerror = (error) => {
              console.error(`Error loading icon ${path}:`, error);
              updateProgress();
              reject(error);
            };

            img.src = path;
          })
      );

      try {
        await Promise.all(iconPromises);
        console.debug('All icons loaded.');
      } catch (error) {
        console.error('Error preloading icons:', error);
      }
    };

    const loadAllAssets = async () => {
      await Promise.all([preloadModels(), preloadTextures(), preloadIcons()]);
      console.debug('Assets preloading complete.');

      setAssetsLoaded(true);

      setLoadingText(`Precompiling scenes...`);
    };

    loadAllAssets();

    return
  }, [gl, camera]);

  // update loading text when progress reaches 100%
  useEffect(() => {
    if (loadingProgress >= 100) {
      setLoadingText(`Loading complete!`);
    }
  }, [loadingProgress]);

  // precompile all scenes after all assets loaded
  return assetsLoaded ? (
    precompileScenes.map((scene, index) => (
      <React.Fragment key={`portal-${index}-${scene.key}`}>
        <ScenePrecompiler scene={scene} updateProgress={updateProgress} />
      </React.Fragment>
    ))
  ) : null;
}