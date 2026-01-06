import type React from "react"
import type { Metadata, Viewport } from "next"
import { Playfair_Display, Geist_Mono } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
})

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
})

export const metadata: Metadata = {
  title: "AstraGuard AI | Autonomous Fault Recovery for CubeSats",
  description:
    "Satellites don't debug themselves. AstraGuard does. Real-time anomaly detection and autonomous fault recovery for space systems.",
  keywords: ["CubeSat", "Fault Recovery", "Anomaly Detection", "Space AI", "Telemetry", "Machine Learning"],
  authors: [{ name: "sr-857" }],
  openGraph: {
    title: "AstraGuard AI | Autonomous Fault Recovery for CubeSats",
    description: "Real-time anomaly detection and autonomous fault recovery for space systems.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AstraGuard AI",
    description: "Satellites don't debug themselves. AstraGuard does.",
  },
    generator: 'v0.app'
}

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${playfair.variable} ${geistMono.variable}`}>
      <body className="font-sans antialiased overflow-x-hidden">
        <div className="noise-overlay" />
        {children}
        <Analytics />
      </body>
    </html>
  )
}
