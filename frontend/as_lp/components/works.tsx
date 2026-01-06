"use client"

import type React from "react"

import { useState, useRef } from "react"
import { motion, useMotionValue, useSpring } from "framer-motion"
import { ArrowUpRight } from "lucide-react"

const projects = [
  {
    title: "AstraGuard-AI",
    tags: ["FastAPI", "React", "Grafana", "ML"],
    image: "/abstract-neural-network-visualization-dark-theme.jpg",
    year: "2025",
    description:
      "Full-stack autonomous fault detection & recovery system for CubeSats. Features security engine, memory engine, and real-time monitoring.",
    link: "https://github.com/sr-857/AstraGuard-AI",
    event: "ECWoC '26",
  },
  {
    title: "AstraGuard-SkyHack",
    tags: ["Streamlit", "3D Viz", "Isolation Forest"],
    image: "/futuristic-data-dashboard-dark-minimal.jpg",
    year: "2025",
    description:
      "Hackathon build with interactive Streamlit dashboard, 3D attitude visualizer, and ML-powered anomaly detection.",
    link: "https://github.com/sr-857/AstraGuard-SkyHack-AI",
    event: "SkyHack 2.0",
  },
  {
    title: "AstraGuard-Frontier",
    tags: ["Pathway", "BDH Memory", "Agentic AI"],
    image: "/abstract-memory-storage-visualization.jpg",
    year: "2025",
    description:
      "Advanced implementation with Pathway streaming engine, biologically-inspired memory system, and agentic decision-making.",
    link: "https://github.com/sr-857/AstraGuard-Frontier-AI",
    event: "Frontier AI Hack",
  },
]

export function Works() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const springX = useSpring(mouseX, { stiffness: 150, damping: 20 })
  const springY = useSpring(mouseY, { stiffness: 150, damping: 20 })

  const handleMouseMove = (e: React.MouseEvent) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      mouseX.set(e.clientX - rect.left)
      mouseY.set(e.clientY - rect.top)
    }
  }

  return (
    <section id="works" className="relative py-32 px-8 md:px-12 md:py-24">
      {/* Section Header - Updated title */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="mb-24"
      >
        <p className="font-mono text-xs tracking-[0.3em] text-muted-foreground mb-4">04 — PROJECT VARIANTS</p>
        <h2 className="font-sans text-3xl md:text-5xl font-light italic">AstraGuard Ecosystem</h2>
      </motion.div>

      {/* Projects List */}
      <div ref={containerRef} onMouseMove={handleMouseMove} className="relative">
        {projects.map((project, index) => (
          <motion.div
            key={project.title}
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, delay: index * 0.1 }}
            className="relative border-t border-white/10 py-8 md:py-12"
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <a
              href={project.link}
              target="_blank"
              rel="noopener noreferrer"
              data-cursor-hover
              className="group flex flex-col gap-4"
            >
              {/* Top row: Year/Event + Title */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Year & Event Badge */}
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-muted-foreground tracking-widest">{project.year}</span>
                  <span className="font-mono text-[10px] tracking-wider px-2 py-1 border border-[#22c55e]/30 rounded text-[#22c55e]">
                    {project.event}
                  </span>
                </div>

                {/* Title */}
                <motion.h3
                  className="font-sans text-4xl md:text-6xl lg:text-7xl font-light tracking-tight group-hover:text-white/70 transition-colors duration-300 flex-1 flex items-center gap-4"
                  animate={{
                    x: hoveredIndex === index ? 20 : 0,
                  }}
                  transition={{ type: "spring", stiffness: 300, damping: 20 }}
                >
                  {project.title}
                  <motion.span
                    animate={{
                      opacity: hoveredIndex === index ? 1 : 0,
                      x: hoveredIndex === index ? 0 : -10,
                    }}
                    transition={{ duration: 0.2 }}
                  >
                    <ArrowUpRight className="w-8 h-8 md:w-10 md:h-10" />
                  </motion.span>
                </motion.h3>

                {/* Tags */}
                <div className="flex gap-2 flex-wrap">
                  {project.tags.map((tag) => (
                    <span
                      key={tag}
                      className="font-mono text-[10px] tracking-wider px-3 py-1 border border-white/20 rounded-full text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Description */}
              <motion.p
                className="font-mono text-sm text-muted-foreground max-w-2xl leading-relaxed"
                animate={{
                  opacity: hoveredIndex === index ? 1 : 0.6,
                }}
                transition={{ duration: 0.3 }}
              >
                {project.description}
              </motion.p>
            </a>
          </motion.div>
        ))}

        {/* Floating Image */}
        <motion.div
          className="absolute pointer-events-none z-50 w-64 h-40 md:w-80 md:h-48 overflow-hidden rounded-lg"
          style={{
            x: springX,
            y: springY,
            translateX: "-50%",
            translateY: "-320%",
          }}
          animate={{
            opacity: hoveredIndex !== null ? 1 : 0,
            scale: hoveredIndex !== null ? 1 : 0.8,
          }}
          transition={{ duration: 0.2 }}
        >
          {hoveredIndex !== null && (
            <motion.img
              src={projects[hoveredIndex].image}
              alt={projects[hoveredIndex].title}
              className="w-full h-full object-cover"
              initial={{ scale: 1.2 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.4 }}
              style={{
                filter: "grayscale(50%) contrast(1.1)",
              }}
            />
          )}
          {/* Glitch overlay - Updated accent color to green */}
          <div className="absolute inset-0 bg-[#22c55e]/10 mix-blend-overlay" />
        </motion.div>
      </div>

      {/* Bottom Border */}
      <div className="border-t border-white/10" />
    </section>
  )
}
