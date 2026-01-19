import React, { useState, useEffect } from 'react';
import styles from './Monitor.module.css';
import { Html, useGLTF } from '@react-three/drei';
import { DEVICE, SCENE_MANAGER } from '../../../config/config';
import { Box3, Group, Material, Mesh, Vector3 } from 'three';
import { GLTF } from 'three-stdlib';
import { useSceneStore } from '../../../core/SceneManager';

const SCROLL_HINT_TIMEOUT = 15000;
const FULLSCREEN_HINT_TIMEOUT = 20000;

const HTML_POSITION_X_OFFSET = -0.2;
const HTML_POSITION_Y_OFFSET = 0.01;
const HTML_DEFAULT_Y_POS = 2.55; // default approx position

interface MonitorGLTF {
    nodes: {
        MonitorScreen: Mesh;
        Object_4: Mesh;
        Object_7: Mesh;
    };
    materials: {
        plastic: Material;
        'Material.040': Material;
        'Material.001': Material;
    };
}

interface MonitorProps {
    roomGLTF: GLTF;
}

const Monitor: React.FC<MonitorProps> = ({ roomGLTF }): JSX.Element => {
    const { sceneZoomed, setFullscreenActive } = useSceneStore();

    const [deskPosition, setDeskPosition] = useState(new Vector3(0, 0, 0)); // desk position from room model, will be set after the model is loaded
    const [monitorScreenGeometry, setMonitorScreenGeometry] = useState<Box3 | null>(null); // monitor screen geometry from monitor model, will be set after the model is loaded
    const [isFullscreen, setIsFullscreen] = useState(false); // is fullscreen mode enabled for html
    const [showScrollHint, setShowScrollHint] = useState(true);
    const [showFullscreenHint, setShowFullscreenHint] = useState(true);

    const monitorScreenRef = React.useRef<Group>(null); // ref to monitor screen node

    // load monitor model
    const { nodes: monitorNodes, materials: monitorMaterials } = useGLTF(SCENE_MANAGER.SCENE_ASSETS.models.room.monitor) as unknown as MonitorGLTF;

    // set monitor screen dimensions after the monitor model is loaded
    useEffect(() => {
        if (!monitorNodes.MonitorScreen) return;

        const geometry = monitorNodes.MonitorScreen.geometry;
        geometry.computeBoundingBox();
        const box = geometry.boundingBox;
        setMonitorScreenGeometry(box);
    }, [monitorNodes.MonitorScreen]);

    // set desk position after the room model is loaded
    useEffect(() => {
        if (roomGLTF.scene) {
            let _deskPosition: Vector3 = new Vector3(0, 0, 0);
            const desk = roomGLTF.scene.getObjectByName("DeskTop"); // top of the desk
            if (desk) {
                desk.getWorldPosition(_deskPosition);
                setDeskPosition(_deskPosition);
            }
        }
    }, [roomGLTF])

    // hide hints when zoomed in after timeout
    useEffect(() => {
        if (sceneZoomed === 'in') {
            let scrollTimer: number | undefined;
            let fullscreenTimer: number | undefined;

            // scroll hint
            scrollTimer = setTimeout(() => {
                setShowScrollHint(false);
            }, SCROLL_HINT_TIMEOUT);

            // fullscreen hint
            fullscreenTimer = setTimeout(() => {
                setShowFullscreenHint(false);
            }, FULLSCREEN_HINT_TIMEOUT);

            return () => {
                if (scrollTimer) clearTimeout(scrollTimer);
                if (fullscreenTimer) clearTimeout(fullscreenTimer);
            };
        } else {
            // reset hints when zoomed out
            setShowScrollHint(true);
            setShowFullscreenHint(true);
        }
    }, [sceneZoomed]);

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

    // update fullscreen active state in the store
    useEffect(() => {
        setFullscreenActive(isFullscreen);
    }, [isFullscreen])

    const html = (
        <Html
            // if isFullscreen, set html to fullscreen mode, otherwise show in the monitor
            {...{
                ...(isFullscreen ? {
                    fullscreen: true,
                    position: [deskPosition.z + DEVICE.MONITOR.POSITION_OFFSET.z - 0.161 + .05, deskPosition.y + DEVICE.MONITOR.POSITION_OFFSET.y + 0.717, 0], // compensate for camera position
                    zIndexRange: [1000, 10000] // make it above UI
                } : {
                    occlude: "blending",
                    transform: true,
                    position: [HTML_POSITION_X_OFFSET, monitorScreenGeometry ? monitorScreenGeometry.max.y + HTML_POSITION_Y_OFFSET : HTML_DEFAULT_Y_POS, 0],
                    rotation: [-Math.PI / 2, 0, Math.PI / 2],
                    scale: [0.23, 0.266, 0.25],
                    center: true,
                    zIndexRange: [5, 10]
                })
            }}
        >
            <div className={`${styles['monitor-container']} ${isFullscreen ? styles['fullscreen'] : ''}`}>
                {/* scroll hint */}
                {showScrollHint && (
                    <div className={styles['monitor-scroll-hint']} style={{ animation: `${styles.fadeInOut} ${SCROLL_HINT_TIMEOUT / 1000}s forwards` }}>
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
                                    {isFullscreen ? ' exit fullscreen, ' : ' '}
                                    place cursor outside the monitor and scroll back</div>
                            </div>
                        </div>
                    </div>
                )}

                {/* fullscreen hint */}
                {showFullscreenHint && (
                    <div className={styles['monitor-fullscreen-instructions-hint']}
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
                            Click the fullscreen button in Firefox toolbar or press F11 to expand
                        </div>
                        <div className={styles['hint-subtitle']}>
                            Press ESC to exit fullscreen mode
                        </div>
                    </div>
                )}

                {/* linux GNOME top panel (task bar) */}
                <div className={styles['gnome-panel']}>
                    <div className={styles['panel-left']}>
                        <div className={styles['activities-button']}>
                            Activities
                        </div>
                    </div>

                    <div className={styles['panel-time']}>
                        <div>3:33</div>
                        <div className={styles['time-period']}>AM</div>
                    </div>
                </div>

                {/* firefox window */}
                <div className={styles['firefox-window']}>
                    <div className={styles['title-bar']}>
                        <div className={styles['title-bar-left']}>
                            <div className={styles['firefox-logo']}>
                                <svg height="18px" width="18px" version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg"
                                    viewBox="0 0 291.678 291.678" >
                                    <g>
                                        <g>
                                            <path style={{ fill: "#2394BC" }} d="M145.66,4.277c75.561,0,136.556,60.995,136.556,136.556S221.22,277.389,145.66,277.389
			S9.104,216.394,9.104,140.833S70.099,4.277,145.66,4.277z"/>
                                            <path style={{ fill: "#EC8840" }} d="M169.329,284.671c69.188-11.835,121.99-71.009,121.99-143.839l-0.91,1.821
			c1.821-13.656,1.821-26.401-0.91-36.415c-0.91,8.193-1.821,12.745-3.642,14.566c0-0.91,0-9.104-2.731-20.028
			c-0.91-8.193-2.731-16.387-5.462-23.67c0.91,3.641,0.91,6.373,0.91,9.104c-10.924-28.222-36.415-63.726-101.051-62.816
			c0,0,22.759,2.731,32.773,18.207c0,0-10.924-2.731-19.118,1.821c10.014,3.641,19.118,8.193,26.401,12.745h0.91
			c1.821,0.91,3.641,2.731,5.462,3.641c13.656,10.014,26.401,23.67,25.49,40.967c-3.641-5.462-7.283-9.104-12.745-10.014
			c6.373,24.58,6.373,44.608,1.821,60.085c-3.641-10.924-6.373-16.387-9.104-19.118c3.641,32.773-0.91,56.443-15.476,71.919
			c2.731-9.104,3.641-17.297,3.641-23.67c-17.297,25.49-36.415,39.146-58.264,40.056c-8.193,0-16.387-0.91-24.58-3.641
			c-10.924-3.641-20.939-10.014-30.042-19.118c13.656,0.91,27.311-0.91,38.236-7.283l18.207-11.835l0,0
			c2.731-0.91,4.552-0.91,7.283,0c4.552-0.91,6.373-2.731,4.552-7.283c-1.821-2.731-5.462-5.462-10.014-8.193
			c-9.104-4.552-19.118-3.641-29.132,2.731c-10.014,5.462-19.118,5.462-28.222-0.91c-5.462-3.641-11.835-9.104-17.297-16.387
			l-1.821-3.641c-0.91,8.193,0,17.297,3.641,30.042l0,0l0,0c-3.641-11.835-4.552-21.849-3.641-30.042l0,0
			c0-6.373,2.731-10.924,8.193-10.924h-1.821h2.731c6.373,0.91,12.745,1.821,20.939,4.552c0.91-7.283,0-15.476-5.462-23.67l0,0
			c7.283-7.283,13.656-11.835,19.118-14.566c2.731-0.91,3.641-3.641,4.552-6.373l0,0l0,0l0,0c1.821-3.641,0.91-5.462-0.91-7.283
			c-5.462,0-10.014,0-15.476-0.91l0,0c-1.821-0.91-4.552-2.731-8.193-5.462l-8.193-8.193l-2.731-1.821l0,0l0,0l0,0l-0.91-0.91
			l0.91-0.91c0.91-6.373,2.731-11.835,5.462-16.387l0.91-0.91c2.731-4.552,8.193-9.104,15.476-14.566
			c-14.566,1.821-27.311,8.193-39.146,19.118c-9.104-2.731-20.939-1.821-33.684,3.641l-1.821,0.91l0,0l1.821-0.91l0,0
			c-8.193-3.641-13.656-14.566-16.387-32.773C20.939,36.14,16.387,55.258,16.387,81.659l-2.731,4.552l-0.91,0.91l0,0l0,0l0,0
			c-1.821,2.731-3.641,6.373-6.373,10.924c-3.641,7.283-5.462,12.745-5.462,18.207l0,0l0,0v1.821l0,0c0,0.91,0,2.731,0,3.641
			l8.193-6.373c-2.731,8.193-5.462,16.387-6.373,24.58v3.641L0,140.833c0,30.953,10.014,60.085,26.401,83.754l0.91,0.91l0.91,0.91
			c11.835,16.387,27.311,30.042,45.519,40.967c12.745,7.283,26.401,12.745,40.967,16.387l2.731,0.91
			c2.731,0.91,6.373,0.91,9.104,1.821c2.731,0,4.552,0.91,7.283,0.91h2.731h4.552h4.552h3.641h6.373c3.641,0,7.283-0.91,10.924-0.91
			C166.598,284.671,169.329,284.671,169.329,284.671z M261.277,107.149v0.91V107.149L261.277,107.149z"/>
                                        </g>
                                    </g>
                                </svg>
                            </div>

                            <div className={styles['window-title']}>
                                Portfolio - Vladyslav Shtatskyi (techinz) | Mozilla Firefox
                            </div>
                        </div>

                        <div className={styles['window-controls']}>
                            <button className={styles['window-button']}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" fill="#bbb" viewBox="0 0 16 16">
                                    <path d="M14 1a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h12zM2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2H2z" />
                                    <path d="M3 3.5a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5zm0 4a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5z" />
                                </svg>
                            </button>

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

                    {/* firefox toolbar */}
                    <div className={styles['firefox-toolbar']}>
                        <div className={styles['toolbar-buttons']}>
                            <button className={styles['toolbar-button']}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#bbb" viewBox="0 0 16 16">
                                    <path fillRule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z" />
                                </svg>
                            </button>

                            <button className={styles['toolbar-button']}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#bbb" viewBox="0 0 16 16">
                                    <path fillRule="evenodd" d="M1 8a.5.5 0 0 1 .5-.5h11.793l-3.147-3.146a.5.5 0 0 1 .708-.708l4 4a.5.5 0 0 1 0 .708l-4 4a.5.5 0 0 1-.708-.708L13.293 8.5H1.5A.5.5 0 0 1 1 8z" />
                                </svg>
                            </button>

                            <button className={styles['toolbar-button']}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#bbb" viewBox="0 0 16 16">
                                    <path fillRule="evenodd" d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2v1z" />
                                    <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466z" />
                                </svg>
                            </button>
                        </div>

                        <div className={styles['address-bar']}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="#4d9bd8" viewBox="0 0 16 16">
                                <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm2-3a2 2 0 1 1-4 0 2 2 0 0 1 4 0zm4 8c0 1-1 1-1 1H3s-1 0-1-1 1-4 6-4 6 3 6 4zm-1-.004c-.001-.246-.154-.986-.832-1.664C11.516 10.68 10.289 10 8 10c-2.29 0-3.516.68-4.168 1.332-.678.678-.83 1.418-.832 1.664h10z" />
                            </svg>
                            techinz.dev
                        </div>
                    </div>

                    {/* web content (portfolio) */}
                    <div className={styles['web-content']}>
                        <iframe
                            src="/templates/Portfolio.html"
                            title="Portfolio"
                            className={styles['web-iframe']}
                        />
                    </div>
                </div>
            </div>
        </Html>
    )

    // monitor model converted to tsx (jsx) using "npx gltfjsx /assets/models/monitor.glb"
    return (
        <group name="Monitor" dispose={null}
            position={[deskPosition.x + DEVICE.MONITOR.POSITION_OFFSET.x, DEVICE.MONITOR.POSITION_OFFSET.y, deskPosition.z + DEVICE.MONITOR.POSITION_OFFSET.z]} // set relative to desk position
            rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, 1]}>
            <group rotation={[-Math.PI, 0, 0]} scale={[1, 2.006, 2.006]}>
                <group rotation={[Math.PI / 2, 0, 0]}>
                    <group name="MonitorScreen" ref={monitorScreenRef} position={[-0.161, 0.717, 0]} rotation={[0, 0, -Math.PI / 2]} scale={[0.144, 0.064, 0.144]}>
                        {html}
                        <mesh geometry={monitorNodes.Object_4.geometry} material={monitorMaterials.plastic} />
                        <mesh geometry={monitorNodes.MonitorScreen.geometry} material={monitorMaterials['Material.040']}>
                        </mesh>
                    </group>
                    <mesh geometry={monitorNodes.Object_7.geometry} material={monitorMaterials['Material.001']} position={[-0.161, 0.721, 0]} scale={[0.063, 0.096, 0.096]} />
                </group>
            </group>
        </group>
    );
};

export default Monitor;