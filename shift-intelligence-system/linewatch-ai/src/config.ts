/**
 * Global Configuration
 * 
 * Handles switching between Localhost (Dev) and Cloud Run (Prod).
 * 
 * VITE_API_URL can be set in .env or GitHub Secrets.
 * If not set, it falls back to localhost.
 */

// Function to determine API URL dynamically
const getApiUrl = () => {
    // 1. Check for Environment Variable (Vite Build)
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
    }

    // 2. Localhost check
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
        return "http://localhost:8000";
    }

    // 3. Fallback to Production (Cloud Run)
    return "https://google-deepmind-hackathon-523034828734.europe-west1.run.app";
};

export const config = {
    API_URL: getApiUrl(),
    // WebSocket URL (replace http/https with ws/wss)
    WS_URL: getApiUrl().replace(/^http/, "ws"),
    
    // Add other constants here
    REFRESH_RATE: 1000,
};
