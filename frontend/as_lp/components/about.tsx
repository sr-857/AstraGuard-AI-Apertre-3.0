"use client"

import { useRef } from "react"
import { motion, useScroll, useTransform, useSpring } from "framer-motion"

const statements = [
  "Satellites don't debug themselves. AstraGuard does.",
  "Autonomous anomaly detection at 5Hz.",
  "ML-powered fault classification in real-time.",
  "Self-healing systems for deep space.",
  "When ground control is 20 minutes away, autonomy is survival.",
]

export function About() {
  const containerRef = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"],
  })

  const x = useTransform(scrollYProgress, [0, 1], ["0%", "-100%"])
  const smoothX = useSpring(x, { stiffness: 100, damping: 30 })

  return (
    <section ref={containerRef} className="relative py-32 overflow-hidden md:py-0">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="px-8 md:px-12 mb-0 py-20"
      >
        <p className="font-mono text-xs tracking-[0.3em] text-muted-foreground mb-4">03 — THE MISSION</p>
        <h2 className="font-sans text-3xl md:text-5xl font-light italic">Why Autonomy Matters</h2>
      </motion.div>

      {/* Horizontal Scroll Container */}
      <div className="relative flex items-center overflow-hidden py-0 gap-0 h-16">
        <motion.div style={{ x: smoothX }} className="flex gap-16 md:gap-24 px-8 md:px-12 whitespace-nowrap">
          {statements.map((statement, index) => (
            <motion.p
              key={index}
              className="text-4xl md:text-6xl lg:text-7xl font-sans font-light tracking-tight text-white/90"
              style={{
                WebkitTextStroke: index % 2 === 0 ? "none" : "1px rgba(255,255,255,0.3)",
                color: index % 2 === 0 ? "inherit" : "transparent",
              }}
            >
              {statement}
            </motion.p>
          ))}
        </motion.div>
      </div>

      {/* Decorative Line */}
      <motion.div
        initial={{ scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="mt-16 mx-8 md:mx-12 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent origin-left"
      />
    </section>
  )
}
