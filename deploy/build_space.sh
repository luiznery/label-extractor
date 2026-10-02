#!/bin/bash
# Assemble the Hugging Face Space (Gradio SDK) in output/space, then upload it with:
#   hf upload <user>/label-extractor output/space . --repo-type space
set -euo pipefail
cd "$(dirname "$0")/.."
out=output/space
rm -rf "$out" && mkdir -p "$out"

cp deploy/space/README.md LICENSE "$out/"
cp -r app src "$out/"
mkdir -p "$out/eval" "$out/samples"
cp -r eval/results "$out/eval/"
for result in eval/results/*.json; do  # only the samples shown in the Examples tab
  cp -r "samples/$(basename "$result" .json)" "$out/samples/"
done

# Runtime dependencies from pyproject.toml; gradio itself is installed by the Space SDK.
python3 - > "$out/requirements.txt" <<'PY'
import tomllib
deps = tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]
print("\n".join(deps))
PY

find "$out" -name "__pycache__" -prune -exec rm -rf {} +
echo "Space ready in $out:" && find "$out" -type f | sort
