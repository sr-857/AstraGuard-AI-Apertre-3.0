import { useThree } from '@react-three/fiber';
import { useEffect, useState } from 'react';

import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { SavePass } from 'three/examples/jsm/postprocessing/SavePass.js';
import { BlendShader } from 'three/examples/jsm/shaders/BlendShader.js';
import { CopyShader } from 'three/examples/jsm/shaders/CopyShader.js';
import { LinearFilter, Vector2, WebGLRenderTarget } from 'three';

// Base Composer for post-processing
export function useBaseComposer(isVisible: boolean): EffectComposer | null {
  const { scene, camera, gl: renderer } = useThree();
  const [composer, setComposer] = useState<EffectComposer | null>(null);

  useEffect(() => {
    if (!isVisible) {
      if (composer) {
        composer.dispose();
        setComposer(null);
      }
      return;
    }

    let newComposer: EffectComposer | null = null;
    try {
      renderer.autoClear = false;
      newComposer = new EffectComposer(renderer);
      const renderPass = new RenderPass(scene, camera);
      newComposer.addPass(renderPass);
      newComposer.setSize(window.innerWidth, window.innerHeight);

      setComposer(newComposer);
    } catch (error) {
      console.error("Failed to create effect composer:", error);
    }

    return () => {
      if (newComposer) {
        newComposer.dispose();
      }
    };
  }, [scene, camera, renderer, isVisible]); // Re-create if core dependencies change

  useEffect(() => {
    if (!composer) return undefined;

    const handleResize = () => {
      composer.setSize(window.innerWidth, window.innerHeight);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [composer]);

  return composer;
}

// Bloom effect for galaxy
export function useBloomComposer(isVisible: boolean): EffectComposer | null {
  return null; // DEBUG: Disable composer to fix white screen
  const composer = useBaseComposer(isVisible);

  useEffect(() => {
    if (!composer) return undefined;

    let bloomPass: UnrealBloomPass | null = null;
    let outputPass: OutputPass | null = null;
    let originalResize: Function | null = null;

    try {
      bloomPass = new UnrealBloomPass(
        new Vector2(typeof window !== 'undefined' ? window.innerWidth * 0.25 : 100, typeof window !== 'undefined' ? window.innerHeight * 0.25 : 100),
        0.4, 0.4, 0.7
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
    if (!composer) return undefined;

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