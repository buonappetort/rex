# REX

REX is an application for people to share recommended products with their friends.

## Features

- Share Your Rex: post a photo or video of a product (Restaurant, Beauty, Clothing, etc.)
- Search Rex: ask "What are my friends recommending for \_\_?". Uses LLM (LangChain) to extract keywords (optional) and searches the JSON store.

## Tech

- Frontend: Pure HTML + JavaScript (no frameworks), served by Nginx, proxies `/api` to backend
- Backend: Python Flask + CORS
- Data: JSON file stored at `data/rex.json`
- Optional: LangChain + OpenAI for keyword extraction
- Docker: separate Dockerfiles and `docker-compose.yml`

## Project Structure

```
backend/
  app.py
  requirements.txt
  Dockerfile
frontend/
  index.html
  app.js
  styles.css
  nginx.conf
  Dockerfile
data/
  rex.json
docker-compose.yml
```

## Running with Docker

1. Optional: export your OpenAI key to enable LLM-assisted search
   - macOS/Linux:
     ```bash
     export OPENAI_API_KEY=sk-...
     export OPENAI_MODEL=gpt-4o-mini
     ```
2. Build and start services:
   ```bash
   docker compose up --build
   ```
3. Open the app:
   - Frontend: `http://localhost:8080`
   - Backend API: `http://localhost:5000/api/health`

Data persists in `./data/rex.json` on your host.

## Local Development (without Docker)

- Backend:

  ```bash
  cd backend
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  FLASK_DEBUG=1 python app.py
  ```

  API available at `http://localhost:5000`

- Frontend:
  Open `frontend/index.html` with a static server that supports proxying `/api` to `http://localhost:5000` or run via Docker for simplicity.

## API

- POST `/api/rex` create a rex
  - body: `{ userId, title, category, description?, mediaUrl?, tags?[] }`
- GET `/api/rex` list rex (optional `?userId=`)
- GET `/api/rex/{id}` get a rex
- POST `/api/search` search rex
  - body: `{ query, userId?, useLLM? }`

## Notes

- LLM integration is optional. If `OPENAI_API_KEY` is not set, search falls back to simple keyword matching.

TODO:

- Create a lot of test data so we can start actually implementing cool search and recommendation features
- In order to do that we would need a lot of user profiles and for all of those user profiles to have data
