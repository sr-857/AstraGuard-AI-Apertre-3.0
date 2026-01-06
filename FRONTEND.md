# AstraGuard AI - Frontend Documentation

## 🌌 Orbital Command: The Interface
Welcome to the AstraGuard AI frontend documentation. This application is not just a dashboard; it is an immersive "Orbital Command" interface designed to visualize complex satellite telemetry and fault recovery operations. Built with **Next.js 16** and **React 19**, it represents the pinnacle of modern web engineering, combining high-performance functional logic with a cinematic, glassmorphic aesthetic inspired by sci-fi avionics.

The frontend serves as the primary interaction layer for the AstraGuard autonomous system, providing real-time visibility into satellite health, anomaly detection logs, and automated recovery sequences. It is optimized for speed, accessibility, and visual impact.

---

## 🏗️ Architecture & Structure

The codebase follows a modular Feature-First architecture within the Next.js App Router.

| Directory | Sub-path | Description |
| :--- | :--- | :--- |
| **`app/`** | `/page.tsx` | The root landing page composition, orchestrating the scroll flow. |
| | `/layout.tsx` | Global layout wrapper containing fonts, metadata, and theme providers. |
| | `/globals.css` | Tailwind CSS v4 configuration, custom animations, and OKLCH color variables. |
| **`components/`** | `/sentient-sphere.tsx` | **Core Visual**: Custom GLSL shader experimentation playground. |
| | `/hero.tsx` | Initial view port component with scroll-linked animations. |
| | `/works.tsx` | Interactive project showcase with magnetic hover effects. |
| | `/navbar.tsx` | Responsive navigation with glassmorphism and mobile overlay. |
| | `/tech-marquee.tsx` | Infinite scrolling animation for technology stack display. |
| | `/custom-cursor.tsx` | Custom fluid interaction cursor for enhanced immersion. |

---

## 🛠️ Technology Stack

State-of-the-art libraries ensuring performance and developer experience.

| Category | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Core** | **Next.js** | `16.0.x` | React Framework for Production (App Router). |
| | **React** | `19.2.x` | UI Library with Concurrent Mode features. |
| **Styling** | **Tailwind CSS** | `v4.0` | Utility-first styling with native CSS variable support. |
| | **Radix UI** | `Latest` | Headless, accessible UI primitives for interactive elements. |
| **Animation** | **Framer Motion** | `12.x` | Production-ready animation library (springs, layout transitions). |
| | **GSAP / Lenis** | `1.3` | Smooth momentum scrolling normalization. |
| **3D Graphics** | **Three.js** | `0.181` | WebGL rendering engine. |
| | **R3F** | `9.4` | React Three Fiber - Declarative Three.js for React. |
| **Language** | **TypeScript** | `5.x` | Static typing for robust application logic. |

---

## 🎨 Design System: "Deep Space"

The visual language is strictly defined to evoke the feeling of a spacecraft interface.

### Typography
| Role | Font Family | Usage | Characteristics |
| :--- | :--- | :--- | :--- |
| **Display** | *Playfair Display* | Headings, Titles | Elegant, editorial, high-contrast serif. |
| **Interface** | *Geist Mono* | Stats, Labels, Data | Technical, monospaced, precise, legible at small sizes. |

### Color Palette (OKLCH)
We utilize the **OKLCH** color space for perceptual uniformity, enabling vibrant neon accents against deep blacks.

| Token | Variable | Semantic Role |
| :--- | :--- | :--- |
| **Background** | `--background` | Deep void black (`oklch(0.145 0 0)`) for maximum contrast. |
| **Primary** | `--primary` | Stark white (`oklch(0.985 0 0)`) for primary text and borders. |
| **Accent** | `--accent` | **Neon Green** (`oklch(0.546 0.245 262)`) for active states and successful operations. |
| **Muted** | `--muted` | Greyed out text for tertiary information (labels, timestamps). |
| **Glass** | `backdrop-blur` | Used heavily in `Navbar` and Cards to create depth hierarchy. |

---

## 🔮 Key Component Engineering

### 1. The Sentient Sphere (`sentient-sphere.tsx`)
The centerpiece of the landing page is an interactive, procedurally generated 3D object.
*   **Implementation**: A custom standard material shader acting on an Icosahedron geometry.
*   **Interactivity**: The sphere tracks mouse movement, updating its rotation vector and surface noise intensity in real-time.
*   **Optimization**: Uses `useFrame` to handle the animation loop outside of React's render cycle for 60fps performance.

### 2. Magnetic Works Gallery (`works.tsx`)
A showcase of related mission components.
*   **Physics**: Uses `useSpring` and `useMotionValue` from Framer Motion to create a "floating image" that follows the cursor with fluid physics when hovering over a list item.
*   **Glitch Effect**: Applies a CSS mix-blend-mode overlay on hover to simulate digital signal interference.

### 3. Scroll-Linked Hero (`hero.tsx`)
*   **Parallax**: Utilizes `useScroll` to map vertical scroll progress to opacity and scale transforms, creating a cinematic "departure" effect as the user scrolls down from the hero section.
*   **Typography**: Staggered entry animations utilizing `staggerChildren` variants for a dramatic introduction.

---

## 🚀 Performance & Optimization

To ensure a seamless experience even on lower-powered devices:
1.  **Static Export**: The entire frontend is configured with `output: 'export'` in `next.config.mjs`, generating pure HTML/CSS/JS for edge delivery via GitHub Pages.
2.  **Unoptimized Images**: Image handling is set to `unoptimized: true` to bypass server-side processing requirements, compatible with static hosting.
3.  **Component Lazy Loading**: Heavy 3D components like the `SentientSphere` are loaded with `next/dynamic` (implied best practice) or carefully isolated to avoid main-thread blocking during hydration.
4.  **Lenis Scroll**: Replaces native browser scrolling with a normalized momentum scroll, ensuring consistent feel across different input devices (trackpad vs. mouse).

## 📦 Deployment Workflow

The project uses a **GitOps** workflow for continuous deployment:
*   **Push to Main**: Triggers GitHub Actions (`.github/workflows/nextjs.yml`).
*   **Build**: Runs `npm run build`, generating the `out/` directory.
*   **Deploy**: Uploads the artifact to GitHub Pages.

### Manual Build
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Create production build
npm run build
```
