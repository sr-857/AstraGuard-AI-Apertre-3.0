import { useThree } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';

import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { SavePass } from 'three/addons/postprocessing/SavePass.js';
import { BlendShader } from 'three/addons/shaders/BlendShader.js';
import { CopyShader } from 'three/addons/shaders/CopyShader.js';
import { LinearFilter, Vector2, WebGLRenderTarget } from 'three';

// Base Composer for post-processing
export function useBaseComposer(isVisible: boolean): EffectComposer | null {
  const { scene, camera, gl: renderer } = useThree();

  const composer = useMemo(() => {
    if (!isVisible) return null;

    try {
      renderer.autoClear = false;
      const comp = new EffectComposer(renderer);
      const renderPass = new RenderPass(scene, camera);
      comp.addPass(renderPass);

      return comp;
    } catch (error) {
      console.error("Failed to create effect composer:", error);
      return null;
    }
  }, [scene, camera, renderer, isVisible]);

  useEffect(() => {
    if (!composer) return;

    try {
      const handleResize = () => {
        composer.setSize(window.innerWidth, window.innerHeight);
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        // we don't dispose the composer itself here because it may be used by parent components
      };
    } catch (error) {
      console.error("Error in resize handler setup:", error);
    }
  }, [composer]);

  return composer;
}

// Bloom effect for galaxy
export function useBloomComposer(isVisible: boolean): EffectComposer | null {
  const composer = useBaseComposer(isVisible);

  useEffect(() => {
    if (!composer) return;

    let bloomPass: UnrealBloomPass | null = null;
    let outputPass: OutputPass | null = null;
    let originalResize: Function | null = null;

    try {
      bloomPass = new UnrealBloomPass(
        new Vector2(window.innerWidth * 0.5, window.innerHeight * 0.5),
        1, 1, 0
      );

      outputPass = new OutputPass();

      composer.addPass(bloomPass);
      composer.addPass(outputPass);

      originalResize = composer.setSize.bind(composer);
      composer.setSize = (width: number, height: number) => {
        if (originalResize) {
          originalResize(width, height);
        }
        bloomPass?.resolution.set(width * 0.5, height * 0.5);
      };
    } catch (error) {
      console.error("Error setting up bloom effect:", error);
    }

    // cleanup
    return () => {
      try {
        if (bloomPass) {
          composer.removePass(bloomPass);
          bloomPass.dispose();
        }

        if (outputPass) {
          composer.removePass(outputPass);
          outputPass.dispose();
        }

        // restore original resize method
        if (originalResize) {
          composer.setSize = originalResize as (width: number, height: number) => void;
        }
      } catch (error) {
        console.error("Error cleaning up bloom effect:", error);
      }
    };
  }, [composer]);

  return composer;
}

// Motion blur effect for zoom in images
export function useMotionBlurComposer(isVisible: boolean): EffectComposer | null {
  const composer = useBaseComposer(isVisible);

  useEffect(() => {
    if (!composer) return;

    let savePass: SavePass | null = null;
    let blendPass: ShaderPass | null = null;
    let outputPass: ShaderPass | null = null;

    try {
      const renderTargetParameters = {
        minFilter: LinearFilter,
        magFilter: LinearFilter,
        stencilBuffer: false
      };

      savePass = new SavePass(
        new WebGLRenderTarget(window.innerWidth, window.innerHeight, renderTargetParameters)
      );

      blendPass = new ShaderPass(BlendShader, 'tDiffuse1');
      blendPass.uniforms['tDiffuse2'].value = savePass.renderTarget.texture;
      blendPass.uniforms['mixRatio'].value = 0.65;

      outputPass = new ShaderPass(CopyShader);
      outputPass.renderToScreen = true;

      composer.addPass(blendPass);
      composer.addPass(savePass);
      composer.addPass(outputPass);

      // set up resize handler
      const originalResize = composer.setSize.bind(composer);
      composer.setSize = (width: number, height: number) => {
        originalResize(width, height);

        // update savePass render target size
        if (savePass && savePass.renderTarget) {
          savePass.renderTarget.setSize(width, height);
        }
      };
    } catch (error) {
      console.error("Error setting up motion blur effect:", error);
    }

    // cleanup
    return () => {
      try {
        if (blendPass) {
          composer.removePass(blendPass);
          blendPass.dispose();
        }

        if (savePass) {
          composer.removePass(savePass);
          if (savePass.renderTarget) {
            savePass.renderTarget.dispose();
          }
          savePass.dispose();
        }

        if (outputPass) {
          composer.removePass(outputPass);
          outputPass.dispose();
        }
      } catch (error) {
        console.error("Error cleaning up motion blur effect:", error);
      }
    };
  }, [composer]);

  return composer;
}