# Persistent state format

The current state format is revision 7. The supported floor is revision
6, so an older revision-5 store is rejected before any migration code runs.
This is intentional: revision 6 retires the one-shot research-index upgrade
ledger and the compatibility decoder that existed only to bring revision-3
and revision-4 data forward.

To move data from a revision-5 store, export the records through a compatible
older checkout, create a fresh state directory with the current Jacobian
version, and import the exported records through the public persistence
workflow. Do not edit `metadata.sqlite3` to change its revision; the migration
ledger and state-format record are integrity boundaries.

Migration definitions through revision 5 remain in the source because the
SQLite ledger is immutable historical evidence. They are not an indication
that the retired workspace schema or data-upgrade bridge is still supported.
New stores apply revision 6, which removes the completed
`jacobian_data_upgrades` table and records the current format.

Revision 7 adds the reasoning-log tables `reasoning_runs` and
`reasoning_events` for the bounded external reasoning-log protocol. This
migration is additive: it creates the new tables, their indices, and
no-update/no-delete triggers without modifying existing records. Stores at
revision 6 are upgraded automatically on first open with the current
version; no manual intervention is required.
