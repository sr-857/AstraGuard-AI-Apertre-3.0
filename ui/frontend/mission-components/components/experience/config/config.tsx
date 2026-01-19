import { Color, Quaternion, Vector3 } from "three";

// Global
export const GLOBAL = {
    INITIAL_CAMERA_MOBILE_POS: new Vector3(0, -12, 5.5), // initial camera position for mobile devices
    INITIAL_CAMERA_DESKTOP_POS: new Vector3(0, -10, 4.5), // initial camera position for desktop devices
    INITIAL_CAMERA_MOBILE_FOV: 100, // initial camera field of view for mobile devices
    INITIAL_CAMERA_DESKTOP_FOV: 75, // initial camera field of view for desktop devices 

    TONE_MAPPING_EXPOSURE: .5, // exposure for tone mapping
}

// SceneManager
export const SCENE_MANAGER = {
    ZOOM_OUT_CAMERA_DATA_DEFAULT: { position: new Vector3(0, 0, 0), quaternion: new Quaternion(0, 0, 0, 1), fov: 75, zoomedIn: false }, // default zoom out camera data for all scenes
    SCENE_ORDER: [ // the order of the scenes, in which they will be loaded and rendered
        'galaxy', 'solarSystemApproach', 'solarSystemRotation',
        'earthApproach', 'earth', 'continent', 'city', 'district'
    ],
    SCENE_ASSETS: { // used to preload assets
        models: {
            // scenes
            galaxy: {
                galaxy: '/assets/models/galaxy.glb'
            },
            // Room removed
        },
        textures: {
            // scenes
            galaxy: {
                disc: '/assets/img/discs/disc.png',
            },
            solarSystem: {
                disc: '/assets/img/discs/disc.png',
                smoke: '/assets/img/other/smoke.png',
                sun: '/assets/img/planets/sun.jpg',
                mercury: '/assets/img/planets/mercury.jpg',
                venus: '/assets/img/planets/venus.jpg',
                earth: '/assets/img/planets/earth.jpg',
                earthnight: '/assets/img/planets/earthnight.jpg',
                earthclouds: '/assets/img/planets/earthclouds.jpg',
                mars: '/assets/img/planets/mars.jpg',
                jupiter: '/assets/img/planets/jupiter.jpg',
                saturn: '/assets/img/planets/saturn.jpg',
                saturnring: '/assets/img/planets/saturnring.jpg',
                uranus: '/assets/img/planets/uranus.jpg',
                uranusring: '/assets/img/planets/uranusring.jpg',
                neptune: '/assets/img/planets/neptune.jpg',
            },
            continent: {
                continent: '/assets/img/continent/continent.jpg',
            },
            city: {
                city: '/assets/img/city/city.jpg',
            },
            district: {
                district: '/assets/img/district/district.jpg',
            },
        },
        icons: {
            // zoom progress indicator
            zoomProgressIndicator: {
                galaxy: '/assets/icons/zoom_progress_indicator/galaxy.png',
                solarSystemApproach: '/assets/icons/zoom_progress_indicator/space.png',
                solarSystemRotation: '/assets/icons/zoom_progress_indicator/solarsystem.png',
                earthApproach: '/assets/icons/zoom_progress_indicator/earthapproach.png',
                earth: '/assets/icons/zoom_progress_indicator/earth.png',
                continent: '/assets/icons/zoom_progress_indicator/continent.png',
                city: '/assets/icons/zoom_progress_indicator/city.png',
                district: '/assets/icons/zoom_progress_indicator/district.png',
                // Room removed
                // end (last point) - when last scene zoomed in (not a real scene, just visual because the zoom indicator goes below the room)
                end: '/assets/icons/zoom_progress_indicator/pin.png',


                // character icons
                astronaut: '/assets/icons/zoom_progress_indicator/astronaut.png',
                superhero: '/assets/icons/zoom_progress_indicator/superhero.png',
                human: '/assets/icons/zoom_progress_indicator/human.png',
            }
        }
    }
}

// Navigation animation
export const NAVIGATION_ANIMATION = {
    DEFAULT_FRICTION: 0.6, // default friction for the animation (0<x<1, 0 = no friction, 1 = no movement)
    DEFAULT_ACCELERATION: 0.04, // acceleration for the animation (0<x<1, 0 = no acceleration, 1 = instant movement)
    DEFAULT_WHEEL_SENSITIVITY: 1, // wheel sensitivity for the animation (0<x<1, 0 = no sensitivity, 1 = instant movement)
    DEFAULT_TOUCH_SENSITIVITY: 0.3, // touch sensitivity for the animation (0<x<1, 0 = no sensitivity, 1 = instant movement)

    COMPLETION_SENSITIVITY: 0.01, // 0<x<1, more sensitivity = faster switch between animation (condition works earlier)
    ZOOMED_IN_SENSITIVITY_MULTIPLIER: 10, // count as zoomed in (sceneZoomed='in') x times earlier

    VELOCITY_THRESHOLD: 0.000001, // threshold for the velocity (prevent it from stopping completely and follow the object (run timeline onUpdate function))
}

// -- Scenes --
// Galaxy
export const GALAXY = {
    STAR_ZOOM_EFFECT_DISTANCE: 0.25, // maximum distance to the galaxy star when zoomed in (to make zoom in effect) = zoomed in too close to the star - make zoom in effect

    // Solar System Star (the star in the galaxy that will be zoomed in to open solar system)
    SOLAR_SYSTEM_STAR: {
        INIT_POSITION: new Vector3(0.038105392881217164, -2.745814737039023, 0.7172299984047412), // the initial position of the star in the galaxy (manually chosen one from the needed area)
        INIT_SIZE: [0.01, 32, 32] as [number, number, number], // the size of the star
        COLOR: 0xFFFFCC, // white-yellowish color
        CAMERA_OFFSET: new Vector3(0, -0.185, 0.185 / 2), // constant offset between the camera and the target
        SIZE_MIN: 0.01, // minimum size of the star (when zoomed out)
        SIZE_MAX: 15, // maximum size of the star (when zoomed in)
        ZOOMED_IN_FOV: 25 // field of view when zoomed in (to make it take the whole screen)
    }
};

// Solar System
export const SOLAR_SYSTEM = {
    SUN_POSITION: new Vector3(0, 0, 0), // initial position of the sun (in the center of the solar system)
    SUN: {
        POSITION: new Vector3(0, 0, 0), // initial position of the sun (in the center of the solar system)

        RADIUS: 5, // radius of the sun
        DETAIL: 24, // detail of the sun (number of segments)

        LIGHT: {
            COLOR: 0xffff99, // color of the light
            INTENSITY: 1000, // intensity of the light
            DISTANCE: 2000, // light attenuation distance
            DECAY: 1.5, // physical light falloff
        },

        CORONA: {
            SCALE: 1.1, // scale of the corona (to make it larger)
            RADIUS: 5, // radius of the corona
            DETAIL: 64, // detail of the corona (number of segments)
            INNER_CORONA_COLOR: new Color(0xFF7700), // inner corona color
            OUTER_CORONA_COLOR: new Color(0xFFCC33), // outer corona color
        }
    },

    PLANETS: [ // solar system planets data
        {
            orbitSpeed: 0.00048,
            orbitRadius: 10,
            orbitRotationDirection: "clockwise",
            planetSize: 0.2,
            planetRotationSpeed: 0.005,
            planetRotationDirection: "counterclockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.mercury,
            rimHex: 0xf9cf9f,
        },
        {
            orbitSpeed: 0.00035,
            orbitRadius: 13,
            orbitRotationDirection: "clockwise",
            planetSize: 0.5,
            planetRotationSpeed: 0.0005,
            planetRotationDirection: "clockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.venus,
            rimHex: 0xb66f1f,
        },
        {
            orbitSpeed: 0.00024,
            orbitRadius: 19,
            orbitRotationDirection: "clockwise",
            planetSize: 0.3,
            planetRotationSpeed: 0.01,
            planetRotationDirection: "counterclockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.mars,
            rimHex: 0xbc6434,
        },
        {
            orbitSpeed: 0.00013,
            orbitRadius: 22,
            orbitRotationDirection: "clockwise",
            planetSize: 1,
            planetRotationSpeed: 0.06,
            planetRotationDirection: "counterclockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.jupiter,
            rimHex: 0xf3d6b6,
        },
        {
            orbitSpeed: 0.0001,
            orbitRadius: 25,
            orbitRotationDirection: "clockwise",
            planetSize: 0.8,
            planetRotationSpeed: 0.05,
            planetRotationDirection: "counterclockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.saturn,
            rimHex: 0xd6b892,
            rings: {
                ringsSize: 0.5,
                ringsTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.saturnring,
            },
        },
        {
            orbitSpeed: 0.00007,
            orbitRadius: 28,
            orbitRotationDirection: "clockwise",
            planetSize: 0.5,
            planetRotationSpeed: 0.02,
            planetRotationDirection: "clockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.uranus,
            rimHex: 0x9ab6c2,
            rings: {
                ringsSize: 0.4,
                ringsTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.uranusring,
            },
        },
        {
            orbitSpeed: 0.000054,
            orbitRadius: 31,
            orbitRotationDirection: "clockwise",
            planetSize: 0.5,
            planetRotationSpeed: 0.02,
            planetRotationDirection: "counterclockwise",
            planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.neptune,
            rimHex: 0x5c7ed7,
        },
    ],
    EARTH_PARAMS: {
        orbitSpeed: 0.00029,
        orbitRadius: 16,
        orbitRotationDirection: "clockwise",
        planetSize: 0.5,
        planetAngle: (-23.4 * Math.PI) / 180,
        planetRotationSpeed: 0.01,
        planetRotationDirection: "counterclockwise",
        planetTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.earth,
        planetNightTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.earthnight,
        planetCloudsTexture: SCENE_MANAGER.SCENE_ASSETS.textures.solarSystem.earthclouds,
    },
    ZOOMED_IN_CAMERA_POS: new Vector3(30, 30, 30), // camera position when zoomed in
    ZOOMED_OUT_CAMERA_POS: new Vector3(400, 400, 400), // initial camera position when loaded and/or zoomed out

    NEBULA: {
        PARTICLE_COUNT: 50, // number of particles in the nebula (50 give the best performance and real look)
        PARTICLE_SPREAD: 1000, // spread of the particles
        MATERIAL_SIZE: 400, // size of the material
        MATERIAL_OPACITY: 0.1, // opacity of the material

        COLORS: [ // colors of the nebula particles
            new Color(0x9966ff),
            new Color(0xff6699),
            new Color(0x66ff99),
            new Color(0x4C72BF),
            new Color(0xff0000),
        ],
        COLOR_MULTIPLIER: 0.1, // color multiplier for the nebula particles (to make them darker)

        CLUSTER_SPREAD: 600, // spread of the nebula clusters
    },

    STARS: {
        COUNT: 1000, // count of the stars
        SPREAD: 1000, // spread of the stars
        MATERIAL_COLOR: 0x888888, // color of the stars
        MATERIAL_SIZE: 1, // size of the stars
    }
}

// Earth (in Solar System)
export const EARTH = {
    ZOOMED_IN_FOV: 20, // fov to set when zoom in Earth to make it take the whole screen
    APPROACH_OFFSET: new Vector3(.5, .5, .5),  // offset for camera when looking at the Earth while approaching
    ZOOMED_IN_OFFSET: new Vector3(.5, .3, .3)  // offset for camera from earth for earth scene
}

// Continent, City, District 
export const IMAGE_SCENE = {
    IMAGE_PLANE_POSITION: new Vector3(5, 5, 5), // image position
    IMAGES_DATA: {
        continent: { width: 1846, height: 1080, targetRepeat: { x: 0.1, y: 0.1 }, targetCoords: { x: 800, y: 700 } },
        city: { width: 1846, height: 1080, targetRepeat: { x: 0.1, y: 0.1 }, targetCoords: { x: 670, y: 500 } },
        district: { width: 1846, height: 1080, targetRepeat: { x: 0.1, y: 0.1 }, targetCoords: { x: 1150, y: 850 } },
    }
}

// Room
export const ROOM = {
    ZOOMED_OUT_CAMERA_POS: new Vector3(6.92, 4.5, 6.5) // initial room camera position when loaded and/or zoomed out
}

// Device
export const DEVICE = {
    MONITOR: {
        POSITION_OFFSET: new Vector3(-1, 2.588, -.1), // offset for monitor position (relative to desk)
        CAMERA_OFFSET: new Vector3(1.5, 0, 0) // offset to center the monitor screen on the camera when zoomed in
    },
    PHONE: {
        POSITION_OFFSET: new Vector3(.2, 2.61, 1.8), // offset for phone position (relative to desk)
        CAMERA_OFFSET: new Vector3(0.05, -.6, 0) // offset to center the phone screen on the camera when zoomed in
    }
}