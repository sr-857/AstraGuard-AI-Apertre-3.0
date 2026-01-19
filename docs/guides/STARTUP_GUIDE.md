# AstraGuard AI - Complete Setup & Startup Guide

## 🚀 Quick Start

### Option 1: One-Command Startup (Recommended)
```bash
npm run app:start
```
This starts both backend and frontend simultaneously and opens the dashboard in your browser.

### Option 2: Manual Startup

**Terminal 1 - Start Backend API:**
```bash
python run_api.py
```

**Terminal 2 - Start Frontend (Next.js):**
```bash
cd frontend/as_lp
npm run dev
```

Then open: [http://localhost:3000](http://localhost:3000)

> **Note**: The dashboard now features the "Orbital Command" aesthetic with a deep space starfield, holographic glass panels, and a HUD-style interface.

## 📍 Available Endpoints

### Frontend
- **Dashboard**: http://localhost:3000

### Backend API
- **API Base**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Monitoring
- **Metrics**: http://localhost:9090/metrics (requires auth)

## 🔗 API Endpoints

### Telemetry
- `POST /api/v1/telemetry` - Send single telemetry data
- `POST /api/v1/telemetry/batch` - Send batch telemetry data

### System Status
- `GET /api/v1/status` - Get system status
- `GET /api/v1/health` - Health check

### Mission Phase Management
- `GET /api/v1/phase` - Get current mission phase
- `POST /api/v1/phase` - Update mission phase

### Data Retrieval
- `GET /api/v1/history/anomalies` - Get anomaly detection history
- `GET /api/v1/memory/stats` - Get memory statistics

## 🛠️ Frontend Configuration

The frontend automatically connects to the backend using environment variables in `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_TELEMETRY=/api/v1/telemetry
NEXT_PUBLIC_API_BATCH=/api/v1/telemetry/batch
NEXT_PUBLIC_API_STATUS=/api/v1/status
NEXT_PUBLIC_API_PHASE=/api/v1/phase
NEXT_PUBLIC_API_HISTORY=/api/v1/history/anomalies
NEXT_PUBLIC_API_MEMORY=/api/v1/memory/stats
```

## 📦 Using the API Client

### In React Components

```tsx
import { apiClient } from "@/lib/api-client";
import { useSystemStatus, usePhase } from "@/lib/api-hooks";

// Using the client directly
async function checkStatus() {
  const status = await apiClient.getStatus();
  console.log(status);
}

// Using the hooks
function MyComponent() {
  const { status, loading, error } = useSystemStatus();
  const { phase } = usePhase();
  
  return (
    <div>
      {loading ? <p>Loading...</p> : <p>Status: {JSON.stringify(status)}</p>}
    </div>
  );
}
```

### Available Hooks
- `useSystemStatus()` - Fetch system status
- `usePhase()` - Get current mission phase
- `useAnomalyHistory(limit?)` - Get anomaly detection history
- `useMemoryStats()` - Get memory statistics
- `useHealthCheck()` - Check backend health

## 🐛 Troubleshooting

### Backend not connecting
1. Ensure backend is running: `python run_api.py`
2. Check if port 8000 is available: `netstat -an | findstr :8000`
3. Verify environment variables in `.env.local`

### Frontend not connecting to backend
### Frontend not connecting to backend
1. Check `.env.local` file exists in `frontend/as_lp/`
2. Ensure `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Check browser console for CORS errors
4. Verify backend is accessible: `curl http://localhost:8000/health`

### Port already in use
```bash
# Kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Kill process on port 3000
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

## 📊 Project Structure

```
AstraGuard-AI/
├── api/                      # FastAPI backend service
│   ├── models.py            # Request/response models
│   └── service.py           # Main API service
├── backend/                 # Backend services
│   ├── main.py              # Entry point
│   └── recovery_orchestrator.py
├── frontend/
│   └── as_lp/               # Next.js application
│       ├── app/             # App pages and layouts (Next.js 13+)
│       ├── components/      # React components
│       ├── lib/
│       │   ├── api-client.ts    # API client utility
│       │   └── api-hooks.ts     # React hooks
│       ├── package.json
│       └── .env.local       # Environment variables
├── run_api.py               # API startup script
├── start-app.js             # Complete stack startup
└── package.json             # Root scripts
```

## 🎯 Next Steps

1. **Start the application**: `npm run app:start`
2. **Open dashboard**: http://localhost:3000
3. **Explore API**: http://localhost:8000/docs
4. **Send telemetry**: Use the frontend or API directly
5. **Monitor anomalies**: View detection history in dashboard

## 📝 Notes

- Backend runs on port **8000**
- Frontend runs on port **3000**
- Metrics server runs on port **9090**
- First-time startup may take 15-20 seconds for dependencies
- CORS is configured to allow frontend requests

## 🔒 Security

⚠️ **Warning**: Metrics endpoint requires authentication. Set environment variables:
```bash
export METRICS_USER=your_username
export METRICS_PASSWORD=your_password
```

Or add to `.env`:
```
METRICS_USER=your_username
METRICS_PASSWORD=your_secure_password
```
