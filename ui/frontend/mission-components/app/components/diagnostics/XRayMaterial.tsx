import * as THREE from 'three';
import { shaderMaterial } from '@react-three/drei';
import { extend } from '@react-three/fiber';

const XRayShaderMaterial = shaderMaterial(
  {
    uColor: new THREE.Color('#00f2ff'),
    uOpacity: 0.2,
    uFresnelBias: 0.1,
    uFresnelScale: 1.0,
    uFresnelPower: 2.0,
    uPulse: 0,
    uPulseColor: new THREE.Color('#ff0044'),
  },
  // Vertex Shader
  `
  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
  `,
  // Fragment Shader
  `
  uniform vec3 uColor;
  uniform float uOpacity;
  uniform float uFresnelBias;
  uniform float uFresnelScale;
  uniform float uFresnelPower;
  uniform float uPulse;
  uniform vec3 uPulseColor;

  varying vec3 vNormal;
  varying vec3 vViewPosition;

  void main() {
    vec3 viewDirection = normalize(vViewPosition);
    float fresnelTerm = dot(vNormal, viewDirection);
    fresnelTerm = clamp(1.0 - fresnelTerm, 0.0, 1.0);
    float fresnel = uFresnelBias + uFresnelScale * pow(fresnelTerm, uFresnelPower);

    vec3 finalColor = mix(uColor, uPulseColor, uPulse);
    gl_FragColor = vec4(finalColor, fresnel * uOpacity);
  }
  `
);

extend({ XRayShaderMaterial });

export default XRayShaderMaterial;
