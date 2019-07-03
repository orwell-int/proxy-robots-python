import os

from pathlib import Path

proto_files = " ".join([str(p) for p in (Path(".").glob("messages/*.proto"))])

os.popen('protoc -I=messages --python_out=orwell/messages/ ' + proto_files)
