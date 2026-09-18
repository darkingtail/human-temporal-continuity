# DIFF_FILE

Changed branch/field: `main`; public history, CatPaw board, and HTC semantic ingestion.

- Public history: removes private metadata and historical object references before replacing the remote with the sanitized `main` lineage.
- CatPaw: repairs the board graph and records current verification rather than stale completion claims.
- HTC Core: splits Chinese and ASCII comma clauses, converts observation time into the declared timezone before relative-day arithmetic, and commits an observation with all of its candidates atomically.
- Regression coverage: quoted/hypothetical comma scope, cross-midnight timezone conversion, rollback after candidate insertion failure, and successful retry.
