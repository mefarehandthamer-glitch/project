"""Create a consistent SQLite backup using SQLite's online backup API."""
import os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
source = Path(os.environ.get("BRAIN_SOURCE_DB", str(Path(__file__).resolve().parent.parent / "data" / "brain_source.sqlite3")))
dest = Path(sys.argv[1]) if len(sys.argv) > 1 else source.with_name(source.stem + "-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + source.suffix)
if not source.exists():
    raise SystemExit(f"Database not found: {source}")
dest.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source) as src, sqlite3.connect(dest) as dst:
    src.backup(dst)
print(dest)
