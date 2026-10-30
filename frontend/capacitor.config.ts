import type { CapacitorConfig } from '@capacitor/cli';

// Set NIFTY_LAB_SERVER_URL to your deployed Render URL before building.
const serverUrl = process.env.NIFTY_LAB_SERVER_URL || 'https://nifty-lab.onrender.com';

const config: CapacitorConfig = {
  appId: 'com.niftylab.terminal',
  appName: 'NIFTY LAB',
  webDir: 'dist',
  bundledWebRuntime: false,
  server: {
    url: serverUrl,
    cleartext: false,
    allowNavigation: ['*.onrender.com'],
  },
  android: {
    allowMixedContent: false,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
};

export default config;
