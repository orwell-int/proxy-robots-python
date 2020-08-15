from pathlib import Path

import importlib.util
spec = importlib.util.spec_from_file_location("messages", Path(".") / "messages" / "generate.py")
foo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foo)
foo.main(Path("."))
