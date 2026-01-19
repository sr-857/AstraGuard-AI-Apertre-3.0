#!/usr/bin/env node
/**
 * AstraGuard AI - Complete Stack Startup Script
 * 
 * This script starts:
 * 1. Backend API Server (FastAPI on port 8000)
 * 2. Frontend App (Next.js on port 3000)
 * 3. Opens dashboard in browser
 * 
 * Usage:
 *   node start-app.js
 *   npm run app:start
 */

const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const os = require('os');

const isWindows = os.platform() === 'win32';
const isLinux = os.platform() === 'linux';

// Get log level from environment variable
const LOG_LEVEL = (process.env.LOG_LEVEL || 'INFO').toUpperCase();
const LOG_LEVELS = { 'NONE': 0, 'ERROR': 1, 'WARNING': 2, 'INFO': 3, 'DEBUG': 4 };
const currentLogLevel = LOG_LEVELS[LOG_LEVEL] || LOG_LEVELS.INFO;

// Simple logger function
function log(level, message) {
  if (LOG_LEVELS[level] <= currentLogLevel) {
    console.log(`[${level}] ${message}`);
  }
}

let apiProcess = null;
let appProcess = null;

console.log(`
╔═══════════════════════════════════════════════════════════╗
║    AstraGuard AI - Complete Stack Startup                 ║
╚═══════════════════════════════════════════════════════════╝
`);

log('INFO', 'Starting AstraGuard AI stack...');

/**
 * Wait for a server to be ready
 */
function waitForServer(port, maxAttempts = 30) {
  return new Promise((resolve) => {
    let attempts = 0;

    const check = () => {
      attempts++;
      const req = http.get(`http://localhost:${port}`, (res) => {
        log('INFO', `Server on port ${port} is ready!`);
        resolve(true);
      });

      req.on('error', () => {
        if (attempts < maxAttempts) {
          setTimeout(check, 1000);
        } else {
          console.warn(`⚠️  Server on port ${port} not ready after ${maxAttempts}s`);
          resolve(false);
        }
      });
    };

    check();
  });
}

/**
 * Open browser
 */
function openBrowser(url) {
  const start = isWindows ? 'start' : isLinux ? 'xdg-open' : 'open';
  spawn(start, [url], { stdio: 'ignore' });
}

/**
 * Start backend API
 */
async function startBackend() {
  log('INFO', 'Starting Backend API Server...');

  return new Promise((resolve) => {
    const python = isWindows ? 'python' : 'python3';
    apiProcess = spawn(python, ['run_api.py'], {
      cwd: path.join(__dirname),
      stdio: 'pipe',
    });

    apiProcess.stdout.on('data', (data) => {
      const output = data.toString();
      if (output.includes('Application startup complete')) {
        log('INFO', 'Backend API Server is running on http://localhost:8002');
        log('INFO', 'API Docs: http://localhost:8002/docs');
        resolve(true);
      }
    });

    apiProcess.stderr.on('data', (data) => {
      console.log(data.toString());
    });

    setTimeout(() => resolve(true), 5000);
  });
}

/**
 * Start frontend app
 */
async function startFrontend() {
  log('INFO', 'Starting Frontend App (Next.js)...');

  return new Promise((resolve) => {
    const cmd = isWindows ? 'npm.cmd' : 'npm';
    appProcess = spawn(cmd, ['run', 'dev'], {
      cwd: path.join(__dirname, 'frontend', 'as_lp'),
      stdio: 'pipe',
    });

    appProcess.stdout.on('data', (data) => {
      const output = data.toString();
      if (output.includes('ready - started server') || output.includes('compiled')) {
        log('INFO', 'Frontend App is running on http://localhost:3000');
        resolve(true);
      }
    });

    appProcess.stderr.on('data', (data) => {
      console.log(data.toString());
    });

    setTimeout(() => resolve(true), 8000);
  });
}

/**
 * Main startup sequence
 */
async function main() {
  try {
    // Start backend
    await startBackend();
    await waitForServer(8002);

    console.log('');

    // Start frontend
    await startFrontend();
    await waitForServer(3000);

    console.log(`
╔═══════════════════════════════════════════════════════════╗
║              🚀 AstraGuard AI is Running!                 ║
╚═══════════════════════════════════════════════════════════╝

🌐 Frontend App: http://localhost:3000
📡 Backend API:  http://localhost:8002
📚 API Docs:     http://localhost:8002/docs
📊 Metrics:      http://localhost:9090/metrics

🎯 Opening dashboard in browser...
    `);

    // Open browser
    openBrowser('http://localhost:3000');

    // Handle shutdown
    process.on('SIGINT', () => {
      console.log('\n\n🛑 Shutting down AstraGuard AI...');
      if (apiProcess) apiProcess.kill();
      if (appProcess) appProcess.kill();
      process.exit(0);
    });
  } catch (error) {
    console.error('❌ Error starting AstraGuard AI:', error);
    process.exit(1);
  }
}

main();
