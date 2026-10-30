# NIFTY LAB — Android APK build guide

## Conversion approach
This package prepares the existing React/Vite frontend for Capacitor Android. The Android app is an online wrapper around your deployed NIFTY LAB site. It continues to use the existing FastAPI backend and does not duplicate or change the trading calculations, historical analysis, exports, or API routes. Internet access is required.

## 1. Deploy the web application first
Deploy this project to Render as a Docker Web Service. Confirm the website and its `/api/health` endpoint work in a browser. Copy the public HTTPS service URL (for example `https://your-service.onrender.com`, without a trailing slash).

## 2. Set the server URL
Open `frontend/capacitor.config.ts` and replace `https://YOUR-RENDER-SERVICE.onrender.com` with your actual Render URL. If you use a custom domain, add that hostname to `allowNavigation` in the same file.

## 3. Generate the Android project (Windows PowerShell)
Install Node.js 20+ and Android Studio. In Android Studio SDK Manager, install Android SDK Platform 35 and Android SDK Build-Tools. Then open PowerShell in the project root and run:

```powershell
cd frontend
npm install
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

The `cap add android` command creates the complete native Android Studio project using the Capacitor version declared in `package.json`. If it says the Android platform already exists, skip that command and continue with `npx cap sync android`.

## 4. Build the APK
In Android Studio, wait for Gradle sync to finish. Select **Build → Build Bundle(s) / APK(s) → Build APK(s)**. The debug APK is normally generated at `android/app/build/outputs/apk/debug/app-debug.apk`. For distribution, use **Build → Generate Signed Bundle / APK** and create a signing key. Keep the signing key and password private and backed up.

## Important
- This is an online-only Android app as requested. It needs an active internet connection to load the site and fetch market/historical data.
- The mobile CSS additions apply safe-area spacing and touch-friendly controls. Existing responsive navigation and mobile breakpoints are retained.
- Backend source and trading calculation code were not modified.
- The APK binary is not included in this ZIP: this environment does not have the Android SDK/Gradle toolchain, and package installation could not complete here. The included Capacitor configuration lets your Windows machine generate the native Android project and APK with the steps above.
- Never rely on stale cached data for live trading decisions.
