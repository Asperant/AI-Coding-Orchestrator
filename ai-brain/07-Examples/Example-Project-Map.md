# Example Project Map: React + Express + AI Service App

This is a filled example of [[Project-Map-Template]].

---

## 1. Project overview

```text
A web application that guides users through a multi-step flow, processes their responses using an AI service, and displays personalized results. The app has a React frontend served by Vite and an Express backend that manages AI job queuing and result generation.
```

---

## 2. Tech stack

Frontend:

```text
React 19, Vite, react-router-dom, recharts (reporting)
```

Backend:

```text
Express (Node.js), runs in server/ directory
```

Database / storage:

```text
Firebase / Firestore for user data persistence
```

AI / ML:

```text
Local LLM via Ollama (primary), with OpenRouter API as remote fallback
```

Other tools:

```text
face-api.js (client-side signal processing), dotenv (config)
```

---

## 3. Main folders

```text
src/pages        -> app screens and routes
src/components   -> reusable UI components
src/services     -> external services and API clients (AI, analytics)
src/context      -> global state providers (React context)
src/data         -> static data, question banks, scoring tables
server           -> Express backend, AI job queue, API routes
public           -> static assets
docs             -> project documentation
```

---

## 4. Key files by task

### Feature work

```text
src/pages/          -> screen logic
src/components/     -> UI building blocks
src/context/        -> global state if needed
src/data/           -> static content, scoring
```

### Bug fixing

```text
Start with the relevant screen in src/pages/
Check src/services/ for API-related bugs
Check server/index.js for backend bugs
Check browser console and server logs
```

### AI pipeline

```text
src/services/aiService.js     -> client-side AI request and fallback logic
server/index.js               -> /api/ai-jobs endpoint, queue management
server/prompts/               -> AI prompt templates (if separated)
src/services/localFallback.js -> deterministic fallback generation
```

### Auth / user data

```text
src/context/AuthContext.jsx   -> auth state
firebase.json                 -> Firestore rules
src/services/firebaseService.js -> data read/write
```

### Database / storage

```text
firebase.json                 -> security rules
src/services/firebaseService.js -> Firestore operations
```

### State management

```text
src/context/AppContext.jsx    -> main app state
src/context/AuthContext.jsx   -> auth state
```

### UI / screens

```text
src/pages/         -> all screens
src/components/    -> shared components
src/index.css      -> global styles
```

### Testing

```text
src/__tests__/     -> unit tests (if present)
docs/test-scenarios.md -> manual test registry
```

### Setup / operations

```text
.env.example       -> required environment variables
server/index.js    -> server startup
package.json       -> scripts, dependencies
vite.config.js     -> build config
```

---

## 5. Active flows

```text
Home -> Permission -> Questions -> Analysis -> Result
```

---

## 6. Legacy or confusing areas

```text
src/services/geminiService.js -> misleading name; this file originally called Gemini API but now calls the local AI backend. Do not assume it connects to Google Gemini.
/api/ai-json                  -> old endpoint, no longer active. Current active path is /api/ai-jobs.
```

---

## 7. High-risk areas

```text
AI fallback     -> result flow breaks if both AI service and fallback fail -> src/services/aiService.js, server/index.js
camera permission -> privacy and user trust risk -> src/context/FaceTrackingContext.jsx
Firebase rules  -> user data exposure risk -> firebase.json
AI prompt       -> output quality and safety risk -> server/prompts/
```

---

## 8. Do not change casually

```text
firebase.json               -> security rules, affects all user data access
server/index.js /api/ai-jobs -> active AI endpoint, queue behavior is part of product
src/context/FaceTrackingContext.jsx -> camera access, privacy-critical
.env / .env.example          -> secrets and config
```

---

## 9. Test focus

```text
1. Full user flow: Home -> Permission -> Questions -> Analysis -> Result
2. AI service unavailable: fallback must work
3. AI service returns empty/malformed response: fallback must activate
4. Camera permission denied: app should continue safely
5. Firebase config missing: app should show clear error
6. Rapid repeated submissions: no duplicate results
```

---

## 10. Notes for AI

```text
- Current active AI endpoint is /api/ai-jobs. Do not use /api/ai-json.
- geminiService.js is misleadingly named. It calls the local backend, not Google Gemini.
- The app is a personal awareness tool, not a clinical/diagnostic tool. Never use diagnostic or pathology language in user-facing text.
- Queue and rate-limit behavior is intentional product behavior, not a bug.
```
