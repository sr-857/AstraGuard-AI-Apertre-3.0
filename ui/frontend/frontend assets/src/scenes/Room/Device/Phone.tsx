import React, { useState, useEffect } from 'react';
import styles from './Phone.module.css';
import { Html, useGLTF } from '@react-three/drei';
import { DEVICE, SCENE_MANAGER } from '../../../config/config';
import { useSceneStore } from '../../../core/SceneManager';
import { GLTF } from 'three-stdlib';
import { Material, Mesh, Vector3 } from 'three';
import { useMobile } from '../../../contexts/MobileContext';

// btw, fullscreen mode was not supposed to be here
// after tests on multiple devices, it appeared that only beloved iOS works in a different way - as always:
// all external browsers on iOS like Chrome or Firefox are just wrappers around Safari, so they behave the same way as Safari does
// Safari blocks interaction with embedded in 3d html content (like iframe) with "transform" or "prepend" attributes
// so we need to set html fullscreen mode for iOS to make it work
// at first I thought that it is a workaround, not a solution, but later actually I saw it as a good idea and
// added optional fullscreen mode for other devices as well

const SCROLL_HINT_TIMEOUT = 5000;
const FULLSCREEN_HINT_TIMEOUT = 20000;
const IOS_HINT_TIMEOUT = 7000;

const HTML_POSITION_Y_OFFSET = 0.046; // approx screen height pos

interface PhoneGLTF {
    nodes: {
        SideButtons: Mesh;
        Plane011: Mesh;
        Plane011_1: Mesh;
        Plane011_2: Mesh;
        Plane011_3: Mesh;
        Plane011_4: Mesh;
        Plane014: Mesh;
        Plane014_1: Mesh;
        Dynamic1: Mesh;
        Dynamic2: Mesh;
    };
    materials: {
        'Metal Cromado': Material;
        'Vidrio Negro': Material;
        'Metal Negro': Material;
        'Bandas magneticas': Material;
    };
}

interface PhoneProps {
    roomGLTF: GLTF;
}

const Phone: React.FC<PhoneProps> = ({ roomGLTF }): JSX.Element => {
    const { sceneZoomed } = useSceneStore();
    const { isIOS } = useMobile();

    const [deskPosition, setDeskPosition] = useState(new Vector3(0, 0, 0)); // desk position from room model, will be set after the model is loaded
    const [isFullscreen, setIsFullscreen] = useState(false); // is fullscreen mode enabled for html
    const [showScrollHint, setShowScrollHint] = useState(true);
    const [showFullscreenHint, setShowFullscreenHint] = useState(true);
    const [showIOSHint, setShowIOSHint] = useState(true);

    // load phone model
    const { nodes: phoneNodes, materials: phoneMaterials } = useGLTF(SCENE_MANAGER.SCENE_ASSETS.models.room.phone) as unknown as PhoneGLTF;

    // set desk position after the room model is loaded
    useEffect(() => {
        if (roomGLTF.scene) {
            let _deskPosition: Vector3 = new Vector3(0, 0, 0);
            const desk = roomGLTF.scene.getObjectByName("DeskTop"); // top of the desk
            if (desk) {
                desk.getWorldPosition(_deskPosition);
                setDeskPosition(_deskPosition)
            }
        }
    }, [roomGLTF])

    // hide hints when zoomed in after timeout
    useEffect(() => {
        if (sceneZoomed === 'in') {
            let scrollTimer: number | undefined;
            let fullscreenTimer: number | undefined;
            let iosTimer: number | undefined;

            // scroll hint
            scrollTimer = setTimeout(() => {
                setShowScrollHint(false);
            }, SCROLL_HINT_TIMEOUT);

            // fullscreen hint
            fullscreenTimer = setTimeout(() => {
                setShowFullscreenHint(false);
            }, FULLSCREEN_HINT_TIMEOUT);

            if (isIOS) {
                // iOS fullscreen notice
                iosTimer = setTimeout(() => {
                    setShowIOSHint(false);
                }, IOS_HINT_TIMEOUT);
            }

            return () => {
                if (scrollTimer) clearTimeout(scrollTimer);
                if (fullscreenTimer) clearTimeout(fullscreenTimer);
                if (iosTimer) clearTimeout(iosTimer);
            };
        } else {
            // reset hints when zoomed out
            setShowScrollHint(true);
            setShowFullscreenHint(true);
            setShowIOSHint(true);
        }
    }, [sceneZoomed]);

    // set fullscreen mode for IOS
    useEffect(() => {
        if (isIOS && sceneZoomed === 'in') {
            setIsFullscreen(true);
        } else if (isIOS && sceneZoomed === 'out') {
            setIsFullscreen(false);
        }
    }, [isIOS, sceneZoomed]);

    // handle escape key to exit fullscreen mode
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isFullscreen) {
                setIsFullscreen(false);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isFullscreen]);

    const htmlInPhone = (
        <Html
            // if isFullscreen, set html to fullscreen mode, otherwise show in the phone
            {...{
                ...(isFullscreen ? {
                    fullscreen: true,
                    position: [0, deskPosition.x + DEVICE.PHONE.POSITION_OFFSET.x + 0.505 + 0.542, 0], // compensate for camera position
                    zIndexRange: [1000, 10000] // make it above UI
                } : {
                    occlude: "blending",
                    transform: true,
                    position: [0, HTML_POSITION_Y_OFFSET, 0],
                    rotation: [Math.PI / -2, 0, Math.PI * 2],
                    scale: [.089, .08, .2],
                    center: true,
                    zIndexRange: [5, 10]
                })
            }}
        >
            <div className={`${styles['android-phone-container']} ${isFullscreen ? styles['fullscreen'] : ''}`}
                onTouchStart={(e) => e.stopPropagation()}
                onTouchEnd={(e) => e.stopPropagation()}
                onTouchMove={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}>

                {/* scroll hint */}
                {showScrollHint && (
                    <div className={styles['phone-scroll-hint']}
                        style={{ animation: `${styles.fadeInOut} ${SCROLL_HINT_TIMEOUT / 1000}s forwards` }}>
                        <div className={styles['scroll-hint-content']}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M8 3.5a.5.5 0 0 1 .5.5v9a.5.5 0 0 1-1 0V4a.5.5 0 0 1 .5-.5z" />
                                <path d="M8 5a.5.5 0 0 1 .5.5v5a.5.5 0 0 1-1 0v-5A.5.5 0 0 1 8 5z" />
                                <path d="M7.646 1.146a.5.5 0 0 1 .708 0l1.5 1.5a.5.5 0 0 1-.708.708L8.5 2.707V4.5a.5.5 0 0 1-1 0V2.707l-.646.647a.5.5 0 1 1-.708-.708l1.5-1.5zM8 10a.5.5 0 0 1 .5.5v2.793l.646-.647a.5.5 0 0 1 .708.708l-1.5 1.5a.5.5 0 0 1-.708 0l-1.5-1.5a.5.5 0 0 1 .708-.708l.646.647V10.5a.5.5 0 0 1 .5-.5z" />
                            </svg>
                            <div>
                                <div className={styles['hint-title']}>Try scrolling!</div>
                                <div className={styles['hint-subtitle']}>This is real HTML content you can interact with 👇</div>
                                <div className={`${styles['hint-subtitle']} ${styles['hint-subtitle-extra']}`}>To zoom out,
                                    {isFullscreen ? ' exit fullscreen and ' : ''}
                                    gesture outside the phone</div>
                            </div>
                        </div>
                    </div>
                )}

                {/* fullscreen hint */}
                {showFullscreenHint && (
                    <div className={styles['fullscreen-instructions-hint']}
                        style={{ animation: `${styles.fadeInOut} ${FULLSCREEN_HINT_TIMEOUT / 1000}s forwards` }}>
                        <div className={styles['hint-icon']}>
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6">
                                <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
                            </svg>
                            →
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="#9aa0a6">
                                <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" />
                            </svg>
                        </div>
                        <div className={styles['hint-text']}>
                            Use the fullscreen button to expand or press ESC to exit
                        </div>
                    </div>
                )}

                {/* iOS auto fullscreen explanation hint */}
                {showIOSHint && isIOS && isFullscreen && (
                    <div className={styles['ios-fullscreen-notice']}
                        style={{ animation: `${styles.fadeInOut} ${IOS_HINT_TIMEOUT / 1000}s forwards` }}>
                        <div className={styles['notice-content']}>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="#007AFF">
                                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                            </svg>
                            <span>
                                Fullscreen mode enabled automatically for iOS compatibility, for other devices it is optional.
                                <br />
                                <small>Safari requires this mode for interactive embedded content.</small>
                            </span>
                        </div>
                        <button className={styles['notice-close']} onClick={() =>
                            document.querySelector(`.${styles['ios-fullscreen-notice']}`)?.classList.add(styles['hidden'])
                        }>
                            ✕
                        </button>
                    </div>
                )}


                {/* android status bar */}
                <div className={styles['android-status-bar']}>
                    <div className={styles['status-time']}>3:33</div>
                    <div className={styles['status-icons']}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                            <path d="M12 21.75c5.385 0 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25 2.25 6.615 2.25 12s4.365 9.75 9.75 9.75z" fillOpacity=".3" />
                            <path d="M12 6c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6 2.69-6 6-6z" />
                        </svg>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                            <path d="M1 9h2v11h-2zm4-4h2v15h-2zm4-4h2v19h-2zm4 4h2v15h-2zm4 4h2v11h-2z" />
                        </svg>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                            <path d="M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.33C7 21.4 7.6 22 8.33 22h7.33c.74 0 1.34-.6 1.34-1.33V5.33C17 4.6 16.4 4 15.67 4zM11 20v-5.5H9L13 7v5.5h2L11 20z" />
                        </svg>
                    </div>
                </div>

                {/* chrome android UI */}
                <div className={styles['chrome-container']}>
                    <div className={styles['chrome-search-bar']}>
                        <div className={styles['chrome-omnibox']}>
                            <div className={styles['omnibox-left']}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 12 2ZM13 17H11V11H13V17ZM13 9H11V7H13V9Z" fill="#9aa0a6" />
                                </svg>

                                <div className={styles['url-text']}>
                                    techinz.dev
                                </div>
                            </div>

                            <div className={styles['omnibox-right']}>
                                <button
                                    className={`${styles['fullscreen-toggle']} ${styles['attention-pulse']} ${isFullscreen ? styles['is-active'] : ''}`}
                                    onClick={() => setIsFullscreen(!isFullscreen)}
                                    title={isFullscreen ? "Exit fullscreen mode" : "View in fullscreen mode"}
                                >
                                    {isFullscreen ? (
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="#9aa0a6">
                                            <path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" />
                                        </svg>
                                    ) : (
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="#9aa0a6">
                                            <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" />
                                        </svg>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* web content (portfolio) */}
                    <div className={styles['web-content']}>
                        <iframe
                            src="/templates/Portfolio.html"
                            title="Portfolio"
                            className={styles['content-iframe']}
                        />
                    </div>
                </div>

                {/* chrome android bottom bar */}
                <div className={styles['chrome-bottom-bar']}>
                    {/* back button */}
                    <button className={styles['nav-button']}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6">
                            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
                        </svg>
                    </button>

                    {/* home button */}
                    <button className={styles['nav-button']}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6">
                            <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
                        </svg>
                    </button>

                    {/* tabs button */}
                    <button className={`${styles['nav-button']} ${styles['tabs-button']}`}>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="#9aa0a6">
                            <path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z" />
                        </svg>
                        <div className={styles['tabs-count']}>1</div>
                    </button>
                </div>
            </div>
        </Html>
    );

    // phone model converted to tsx (jsx) using "npx gltfjsx /assets/models/phone.glb"
    // comment "<mesh geometry={phoneNodes.Plane011_2.geometry} material={phoneMaterials.Pantalla}"! it's the original screen.
    return (
        <group name="Phone" dispose={null} position={[deskPosition.x + DEVICE.PHONE.POSITION_OFFSET.x, DEVICE.PHONE.POSITION_OFFSET.y, deskPosition.z + DEVICE.PHONE.POSITION_OFFSET.z]} rotation={[Math.PI / -2, 0, Math.PI / 2]} scale={[.35, .35, .35]}>
            <mesh
                geometry={phoneNodes.SideButtons.geometry}
                material={phoneMaterials['Metal Cromado']}
                position={[0.505, 0.542, 0]}
                rotation={[Math.PI / 2, 0, 0]}
                scale={[1, 0.672, 1]}
            />
            <group rotation={[Math.PI / 2, 0, 0]}>
                <mesh geometry={phoneNodes.Plane011.geometry} material={phoneMaterials['Vidrio Negro']} />
                <mesh geometry={phoneNodes.Plane011_1.geometry} material={phoneMaterials['Metal Cromado']} />
                {/* <mesh geometry={phoneNodes.Plane011_2.geometry} material={phoneMaterials.Pantalla} /> */}
                <mesh geometry={phoneNodes.Plane011_3.geometry} material={phoneMaterials['Metal Negro']} />
                <mesh geometry={phoneNodes.Plane011_4.geometry} material={phoneMaterials['Bandas magneticas']} />

                {htmlInPhone}
            </group>
            <group position={[0, 1, 0]} rotation={[Math.PI / 2, 0, 0]}>
                <mesh geometry={phoneNodes.Plane014.geometry} material={phoneMaterials['Vidrio Negro']} />
                <mesh geometry={phoneNodes.Plane014_1.geometry} material={phoneMaterials['Metal Cromado']} />
            </group>
            <mesh
                geometry={phoneNodes.Dynamic1.geometry}
                material={phoneMaterials['Metal Negro']}
                position={[0.219, -0.995, 0]}
                rotation={[Math.PI / 2, 0, 0]}
            />
            <mesh
                geometry={phoneNodes.Dynamic2.geometry}
                material={phoneMaterials['Metal Negro']}
                position={[-0.219, -0.993, 0]}
                rotation={[Math.PI / 2, 0, 0]}
                scale={[1.017, 1.102, 1.017]}
            />
        </group>
    );
};

export default Phone;