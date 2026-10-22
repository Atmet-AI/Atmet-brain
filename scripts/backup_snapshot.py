"""Create one encrypted snapshot for an operator-managed scheduler."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from atmet_brain import Brain
from atmet_brain.util import uid

parser = argparse.ArgumentParser()
parser.add_argument("--home", type=Path, required=True)
parser.add_argument("--destination", type=Path, required=True)
parser.add_argument("--key-file", type=Path, required=True)
parser.add_argument("--journal-destination", type=Path, required=True)
args = parser.parse_args()
args.destination.mkdir(parents=True, exist_ok=True, mode=0o700)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
brain = Brain(args.home)
result = brain.create_backup(args.destination / (stamp + "-" + uid("snapshot") + ".atmet"), args.key_file)
brain.flush_recovery_journal(args.journal_destination)
print(result["path"])
