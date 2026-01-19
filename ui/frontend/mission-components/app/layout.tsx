import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap"
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
});

export const metadata: Metadata = {
  title: "AstraGuard AI | Autonomous Fault Recovery",
  description: "Real-time anomaly detection and autonomous fault recovery for space systems.",
  keywords: ["CubeSat", "Fault Recovery", "Anomaly Detection", "Space AI", "Telemetry"],
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

import { ThemeProvider } from "../components/theme-provider";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased overflow-x-hidden bg-background text-foreground" suppressHydrationWarning>
        <ThemeProvider
          attribute="data-theme"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
          themes={['dark', 'stealth', 'clean', 'high-visibility']}
        >
          <div className="noise-overlay" />
          {children}
          <Analytics />
        </ThemeProvider>
      </body>
    </html>
  );
}
