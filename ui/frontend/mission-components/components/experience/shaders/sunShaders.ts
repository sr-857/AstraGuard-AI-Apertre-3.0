
export const sunVertexShaderSurface = `
varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying float vDisplacement;

uniform float time;

// simple noise function
float noise(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453);
}

void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    
    // create subtle vertex displacement for surface turbulence
    float displacement = noise(position * 0.1 + vec3(0.0, 0.0, time * 0.1));
    displacement += 0.5 * noise(position * 0.2 + vec3(time * 0.05, 0.0, 0.0));
    displacement = displacement * 0.3 - 0.15;
    
    vDisplacement = displacement;
    
    // apply displacement along normal
    vec3 newPosition = position + normal * displacement * 0.2;
    
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
}
`;

export const sunFragmentShaderSurface = `
uniform sampler2D sunTexture;
uniform float time;

varying vec2 vUv;
varying vec3 vNormal;
varying vec3 vPosition;
varying float vDisplacement;

// improved noise functions
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    
    // first corner
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    
    // other corners
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy; // 2.0*C.x = 1/3 = C.y
    vec3 x3 = x0 - D.yyy; // -1.0+3.0*C.x = -0.5 = -D.y
    
    // permutations
    i = mod289(i);
    vec4 p = permute(permute(permute(
        i.z + vec4(0.0, i1.z, i2.z, 1.0))
        + i.y + vec4(0.0, i1.y, i2.y, 1.0))
        + i.x + vec4(0.0, i1.x, i2.x, 1.0));
        
    // gradients: 7x7 points over a square, mapped onto an octahedron
    float n_ = 0.142857142857; // 1.0/7.0
    vec3 ns = n_ * D.wyz - D.xzx;
    
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z); // mod(p,7*7)
    
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_); // mod(j,N)
    
    vec4 x = x_ *ns.x + ns.yyyy;
    vec4 y = y_ *ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    
    // normalise gradients
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x;
    p1 *= norm.y;
    p2 *= norm.z;
    p3 *= norm.w;
    
    // mix final noise value
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// creates plasma turbulence effect
float turbulence(vec3 p) {
    float w = 100.0;
    float t = -0.5;
    for (float f = 1.0; f <= 10.0; f++) {
        float power = pow(2.0, f);
        t += abs(snoise(vec3(power * p.x, power * p.y, power * p.z)) / power);
    }
    return t;
}

void main() {
    // sample base texture with distorted UVs
    vec2 distortedUv = vUv;
    distortedUv.x += 0.02 * sin(distortedUv.y * 10.0 + time * 0.1);
    distortedUv.y += 0.02 * cos(distortedUv.x * 10.0 + time * 0.15);
    
    vec4 baseColor = texture2D(sunTexture, distortedUv);
    
    // create plasma effect using noise
    float noise1 = turbulence(vPosition * 0.015 + time * 0.01);
    float noise2 = turbulence(vPosition * 0.03 + vec3(0.0, time * 0.02, 0.0));
    
    // create sunspots
    float sunspots = smoothstep(0.4, 0.6, snoise(vPosition * 0.05 + vec3(time * 0.01, 0.0, 0.0)));
    sunspots = pow(sunspots, 3.0) * 0.6;
    
    // edge darkening (limb darkening effect)
    float edgeFactor = dot(normalize(vNormal), vec3(0.0, 0.0, 1.0));
    edgeFactor = pow(edgeFactor, 0.6); // Adjust power for intensity
    
    // mix hot spots and dark regions
    float hotSpots = noise1 * noise2 * 3.0;
    hotSpots = clamp(hotSpots, 0.0, 1.0);
    
    // final color calculation
    vec3 color = baseColor.rgb;
    color = mix(color, vec3(1.0, 0.9, 0.5), hotSpots * 0.3); // Add hot spots
    color = mix(color, vec3(0.8, 0.2, 0.0), sunspots); // Add dark sunspots
    color = mix(color * 0.6, color, edgeFactor); // Apply limb darkening
    
    // add emission for the glow
    color += vec3(1.0, 0.6, 0.1) * hotSpots * 0.4;
    
    // brighten based on displacement for 3D effect
    color *= 1.0 + vDisplacement * 2.0;
    
    gl_FragColor = vec4(color, 1.0);
}
`;

export const sunVertexShaderCorona = `
varying vec3 vNormal;
varying vec3 vViewPosition;

void main() {
    vNormal = normalize(normalMatrix * normal);
    
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;
    
    gl_Position = projectionMatrix * mvPosition;
}
`;

export const sunFragmentShaderCorona = `
uniform float time;
uniform vec3 coronaColor1;
uniform vec3 coronaColor2;

varying vec3 vNormal;
varying vec3 vViewPosition;

// simplex noise function
float snoise(vec3 v) {
    return 0.0; // or not
}

void main() {
    // normalized view direction
    vec3 viewDir = normalize(vViewPosition);
    
    // fresnel effect for corona falloff
    float fresnelFactor = pow(1.0 - abs(dot(vNormal, viewDir)), 4.0);
    
    // animate corona with turbulent noise
    float noiseValue = snoise(vNormal * 2.0 + vec3(0.0, time * 0.1, 0.0));
    noiseValue += 0.5 * snoise(vNormal * 4.0 + vec3(time * 0.2, 0.0, 0.0));
    
    // create animated solar flares
    float flares = pow(max(0.0, snoise(vNormal * 3.0 + vec3(time * 0.05, 0.0, 0.0))), 4.0);
    
    // combine colors based on noise and fresnel
    vec3 color = mix(coronaColor1, coronaColor2, noiseValue * 0.5 + 0.5);
    
    // add flares
    color += vec3(1.0, 0.6, 0.2) * flares * 0.8;
    
    // apply fresnel falloff for edge glow
    float alpha = fresnelFactor * (0.7 + 0.3 * sin(time * 0.5 + noiseValue * 5.0));
    
    gl_FragColor = vec4(color, alpha);
}
`;