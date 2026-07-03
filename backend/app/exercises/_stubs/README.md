# Exercise config stubs

This directory is the staging area for exercises that aren't yet activated. All
of the originally-stubbed exercises (chest_press, shoulder_press, lat_pulldown,
cable_row, tricep_pushdown) have been promoted to full configs in the parent
`app/exercises/` directory, so it is currently empty.

To add a new exercise: drop a `<key>.yaml` here following the same schema as the
implemented exercises (`squat`, `bicep_curl`, `pushup`, …), tune its thresholds
against real footage, then move it up one directory into `app/exercises/`.
**No engine code changes are required** — the analysis pipeline is fully
config-driven, and `available_exercises()` only lists top-level YAMLs.
