## 🚀 Mission Control Dashboard MVP

[![Lighthouse](https://img.shields.io/badge/Lighthouse-95%2B-green.svg)](reports/)
[![Cypress](https://img.shields.io/badge/Cypress-100%25-blue.svg)](coverage/)
[![Vercel Deployed](https://img.shields.io/badge/Vercel-Live-brightgreen.svg)](https://dashboard.vercel.app)

| Feature | Status | Lighthouse |
|---------|--------|------------|
| Tabbed Mission/Systems | ✅ Live WS | 🟢 98 |
| Satellite Tracker+Map | ✅ Anomaly ACK | 🟢 96 |
| KPI Row + Breakers | ✅ Live drift | 🟢 97 |
| Charts Grid + Health Table | ✅ Sort/Expand | 🟢 95 |
| Mobile Responsive | ✅ iPhone→Desktop | 🟢 95+ |
| WebSocket Resilience | ✅ Reconnect/Poll | 🟢 100 |

**Live Demo**: https://astraguard-dashboard.vercel.app  
**90s Walkthrough**: ![Demo](public/demo.mp4)

### Quickstart
```bash
npm i
npm run mock    # Terminal 1: WS backend
npm run dev     # Terminal 2: Frontend
open localhost:3000/dashboard
```

### Verification
```bash
# E2E Tests
npm run test:e2e

# Lighthouse Audit
npm run test:lighthouse
```
