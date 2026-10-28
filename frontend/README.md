# Timetable frontend (React + Vite + Tailwind)

## Run
1. Install Node.js LTS (18 or newer) from https://nodejs.org
2. In this folder:  npm install
3. Start the backend first (backend folder):  python manage.py runserver
4. Start the frontend:  npm run dev   -> open http://localhost:5173

Backend on another address? Copy .env.example to .env and edit VITE_API_URL, then restart `npm run dev`.

## Screens
- /login                 everyone
- /generate  (Admin)     pick term, time limit, ML on/off, Generate; shows result, metrics, ML hints
- /timetable (Admin)     full weekly grid, filters (faculty/room/course), by-day view, CSV
- /users     (Admin)     create Faculty / Student / Admin logins
- /my  (Faculty/Student) only your own classes, week grid or by-day list, CSV

## Tests
  npm test        (grid helper functions)
  npm run build   (production build into dist/)

## Files
  src/api/client.js     every backend call + token refresh + error messages
  src/auth.jsx          login state
  src/lib/grid.js       timetable grid helpers (tested)
  src/pages/*           the 5 screens
  src/components/*      layout, weekly grid, small shared pieces
