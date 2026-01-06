export function SectionBlend() {
  return (
    <div className="relative h-40 -mt-20 z-10 pointer-events-none">
      <div
        className="absolute inset-0 h-1/2"
        style={{
          background: "linear-gradient(to bottom, transparent, #050505)",
        }}
      />
      <div
        className="absolute inset-0 top-1/2 h-1/2"
        style={{
          background: "linear-gradient(to bottom, #050505, transparent)",
        }}
      />
    </div>
  )
}
