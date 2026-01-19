import { Navbar } from "@/components/navbar"
import { Hero } from "@/components/hero"
import { About } from "@/components/about"
import { Works } from "@/components/works"
import { TechMarquee } from "@/components/tech-marquee"
import { Footer } from "@/components/footer"
import { CustomCursor } from "@/components/custom-cursor"
import { SmoothScroll } from "@/components/smooth-scroll"
import { SectionBlend } from "@/components/section-blend"
import { ApiDemo } from "@/components/api-demo"
import { FederatedLearningDashboard } from "@/components/federated-learning-dashboard"
import { FederatedLearningVisualization } from "@/components/federated-learning-visualization"
import { FederatedLearningDemo } from "@/components/federated-learning-demo"
import { MultiCloudAnomalyDashboard } from "@/components/multi-cloud-anomaly-dashboard"

export default function Home() {
  return (
    <SmoothScroll>
      <CustomCursor />
      <Navbar />
      <main>
        <Hero />
        <SectionBlend />
        <About />
        <Works />
        <ApiDemo />

        {/* Federated Learning Section */}
        <section id="federated-learning" className="py-20 bg-gray-50 dark:bg-gray-900">
          <div className="container mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
                Federated Learning
              </h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
                Experience privacy-preserving distributed AI training. Train anomaly detection models
                across multiple nodes without sharing sensitive telemetry data.
              </p>
            </div>

            <div className="space-y-16">
              <FederatedLearningDemo />
              <FederatedLearningDashboard />
              <FederatedLearningVisualization metrics={[]} participants={[]} />
            </div>
          </div>
        </section>

        {/* Multi-Cloud Anomaly Detection Section */}
        <section id="multi-cloud-anomaly" className="py-20 bg-white dark:bg-gray-800">
          <div className="container mx-auto px-4">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
                Multi-Cloud Anomaly Detection
              </h2>
              <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
                Unified monitoring and recovery across AWS, Azure, and GCP. Detect and respond to
                anomalies with provider-agnostic strategies in hybrid and multi-cloud environments.
              </p>
            </div>

            <MultiCloudAnomalyDashboard />
          </div>
        </section>

        <TechMarquee />
        <Footer />
      </main>
    </SmoothScroll>
  )
}
