"""Read a Brain through its REST API using a dedicated scoped token file."""

import argparse
import json
from pathlib import Path

from atmet_brain.client import Client

parser = argparse.ArgumentParser()
parser.add_argument("--endpoint", default="http://127.0.0.1:7310")
parser.add_argument("--token-file", type=Path, required=True)
parser.add_argument("--space", required=True)
parser.add_argument("--query", default="Prepare a quotation")
args = parser.parse_args()
client = Client(args.endpoint, args.token_file.read_text().strip())
print(json.dumps(client.call("context.get", space_id=args.space, query=args.query), indent=2))
