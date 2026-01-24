# Deployment Guide (The "Exact UI Steps" Version)

## Part 1: Backend (Google Cloud Run)

**Goal**: Connect your GitHub Repo so Cloud Run builds the `/linewatch-ai-backend` folder automatically.

1.  **Go to Console**: [https://console.cloud.google.com/run/create](https://console.cloud.google.com/run/create)
2.  **Select Source**:
    *   Radio Button: **"Continuously deploy new revisions from a source repository"**
    *   Click **"SET UP CLOUD BUILD"**.
3.  **Cloud Build Setup (The Popup)**:
    *   **Repository Provider**: GitHub.
    *   **Repository**: Select your repo (`shift-intelligence-system` etc).
    *   **Click Next**.
4.  **Build Configuration**:
    - **Build Type**: Select **"Cloud Build configuration file (yaml or json)"**.
    - **File location**: `/cloudbuild.yaml` (Default).
    - **Note**: I put this file in the very top folder so Google will find it automatically. No paths to type!
    - Click **Save**.
4.  **Service Settings**:
    *   **Service Name**: `linewatch-backend` (or whatever you want).
    *   **Region**: `us-central1`.
    *   **Authentication**: Allow unauthenticated invocations (Check this box).
5.  **Environment Variables**:
    *   Expand **"Container, Networking, Security"**.
    *   Click **"Variables & Secrets"** tab.
    *   Click **"Add Variable"**.
    *   Name: `GOOGLE_API_KEY`  Value: `your_gemini_key`.
6.  **Create**:
    *   Click **Create**.
    *   Wait ~2-3 minutes for the build to finish.
    *   **Copy the URL** at the top (e.g., `https://linewatch-backend-xyz.run.app`).

---

## Part 2: Frontend (GitHub Pages Auto-Deploy)

I created a GitHub Action (`.github/workflows/deploy_frontend.yml`) that does this for you automatically when you push.

1.  **Configure Backend URL**:
    *   In your local `linewatch-ai` folder, create `.env.production`:
        ```env
        VITE_API_URL=https://YOUR_BACKEND_URL_FROM_PART_1
        ```
    *   *Note*: Since the action builds on GitHub, you should actually add this as a Secret on GitHub (`Settings` -> `Secrets` -> `Actions` -> `New Repository Secret` -> `VITE_API_URL`) OR just commit the `.env.production` file if you don't mind exposing the URL (it's public anyway).
    *   **Simplest way**: Commit `.env.production` to the repo.

2.  **Push to GitHub**:
    ```bash
    git add .
    git commit -m "Configure deployment"
    git push origin main
    ```

3.  **Enable Pages**:
    *   Go to GitHub Repo **Settings** -> **Pages**.
    *   **Source**: Deploy from a branch.
    *   **Branch**: Select `gh-pages` (This branch will appear AFTER the Action finishes running ~1 min after push).
    *   Click **Save**.

**Done!** Your site will be live at `https://yourusername.github.io/repo-name/`.
