---
title: Label Extractor
emoji: 🏷️
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.29.0
python_version: "3.12"
app_file: app/app.py
pinned: false
license: mit
short_description: Food-label photos to EU product data in PT and FR
---

# Label extractor

Photos of a food label → EU label fields (legal name, ingredients, allergens, nutrition…)
in Portuguese and French, collected in an editable catalog and exported as a Shopify import CSV.

- **Examples** tab: results precomputed with small local models (Qwen2.5-VL 3B + Qwen2.5 3B
  running on a laptop CPU), so they load instantly.
- **Extract** tab: runs live with **your own OpenAI API key**. The key is used for that
  request only and is never stored. Your catalog lives in your browser session only.

The full project, including the local-model setup, the CLI and the evaluation, runs on a laptop
without any API key.
