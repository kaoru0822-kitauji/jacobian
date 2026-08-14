# Persistent state format

The current state format is revision 12. Revision 11 is the minimum supported
update source; older stores are rejected before any migration code runs.

To recover data from an older store, keep that directory unchanged and open it
with a compatible older checkout. Create a fresh state directory for the
current version; Jacobian provides no cross-revision import bridge. Do not edit
`metadata.sqlite3` to change its revision—the migration ledger and state-format
record are integrity boundaries.

Earlier migration definitions remain in source because migration ledgers bind
their checksums. They do not define supported runtime services or an in-place
upgrade path. Revisions 9 and 10 replace the broad checker-package digest with
a versioned per-checker manifest that separates checker and worker source,
records exact Python distributions, and produces one implementation digest;
existing checker authorization rows are deliberately not reinterpreted. The
operation-catalog boundary in revision 12 retires the generic experiment,
search, installed-plugin, and reasoning-log tables. New stores apply the
complete ordered schema and record revision 12.

Verification records are immutable artifacts rather than state-table rows.
Record schema v4 payloads snapshot the accepting checker's full manifest.
Revision 11 is the minimum accepted migration source: revision-10 stores and
their v3 records remain readable with a matching older checkout, but are not
reinterpreted by the current runtime. Revision-11 stores must be updated to
revision 12 before serving. There is no legacy checker-authorization or record
import path.
