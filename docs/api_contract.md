# API Contract (teeno members ye pehle fix karein)
POST /api/v1/auth/login/            -> JWT token
POST /api/v1/data/upload/{entity}/  -> xlsx/csv upload (course|faculty|room|student)
POST /api/v1/timetable/generate/    -> solver run (input: contracts/sample_input.json)
GET  /api/v1/timetable/             -> latest timetable
PUT  /api/v1/timetable/move/        -> drag-drop move + re-validate
GET  /api/v1/timetable/me/          -> faculty/student personal view
GET  /api/v1/ml/predictions/        -> demand + workload risk
