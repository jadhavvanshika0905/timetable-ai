"""Mock data load karne ki script - sab members isi dataset pe test karein."""
import json, pathlib
print(json.loads(pathlib.Path("contracts/sample_input.json").read_text())["courses"])
