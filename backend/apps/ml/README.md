# Member 2 - ML part (demand predictor + faculty workload risk)

Folder layout (put `ml/` next to `scheduler/`):
    backend/apps/scheduler/   (Member 1)
    backend/apps/ml/          (this folder)

## 1. Install
    pip install -r ml/requirements-ml.txt

## 2. Run the tests (no Django, no DB)
    cd <folder that contains ml/ and scheduler/>
    python -m unittest ml.test_ml -v          # expect: Ran 17 tests ... OK

## 3. Train + demo
    python -m ml.cli train                    # saves ml/models_store/*.joblib
    python -m ml.cli demo --courses 30 --seconds 15

## 4. Use from code
    from ml.pipeline import train_all, build_ml_hints, hints_for_solver
    demand, risk, history = train_all(data)               # dummy history if none
    hints = build_ml_hints(data, demand, risk, history)   # + overrides={...}
    result = generate_timetable(data, ml_hints=hints_for_solver(hints))

## 5. Admin override
    overrides = {"faculty_risk": {"F3": "LOW"}, "predicted_demand": {"C7": 45},
                 "weights": {"idle_gap": 9}}

## 6. Django (untested here - needs your DB)
    from apps.ml.service import generate_with_ml
    generate_with_ml(term_id=1)               # python manage.py shell
Terms are ordered by AcademicTerm pk; change db.py if you have a date field.

## Known limits
* Training history is DUMMY (generated). Numbers shown are on that data.
* Risk labels come from a formula + noise, not real burnout data.
* Replace history with real past terms and retrain; code stays the same.
