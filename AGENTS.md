# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is **yishexu-designtools** — a structural engineering damper design tool with a Python Flask backend (port 8000) and React/TypeScript frontend (port 3000). The frontend proxies `/api` requests to the backend via Vite config.

### Running services

- **Backend**: `cd backend && python3 run.py` (Flask on port 8000, auto-creates SQLite DB at `backend/instance/users.db`)
- **Frontend**: `cd web-app && npm run dev` (Vite dev server on port 3000)

Both must run simultaneously for end-to-end functionality.

### Important caveats

- Use `python3` not `python` — the environment does not have a `python` symlink.
- The `requirements.txt` is incomplete: `flask-bcrypt` and `ezdxf` are also required by the backend but not listed. Install them alongside: `pip install -r requirements.txt flask-bcrypt ezdxf`
- ESLint config file (`.eslintrc.*`) is missing from the repo. Running `npm run lint` fails. TypeScript type-check (`npx tsc --noEmit`) also reports pre-existing errors that don't affect runtime.
- The app uses JWT-based auth. Register via `POST /api/auth/register` with `{"username", "password"}`. BRB/VFD design tools require admin-granted permissions (role-based access control).
- SyntaxWarnings from `brb_drawing.py` and `vfd_drawing.py` are pre-existing (unescaped backslashes in f-strings) and do not affect functionality.

### Testing

No automated test framework is configured. Verification is done via:
- Backend health check: `curl http://localhost:8000/api/health`
- Frontend proxy check: `curl http://localhost:3000/api/health`
- Auth flow: register + login via API
