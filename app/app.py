"""Gradio demo: label photos in, an editable PT/FR product catalog and a Shopify CSV out.

Run locally with `uv run --extra app python app/app.py`.

Environment variables (for hosting it as a public demo, e.g. a Hugging Face Space):
- LABELKIT_CATALOG_DIR: where the catalog is saved (default `output/catalog/`). Set it to ""
  to keep the catalog in memory, one per browser session, and to disable the response cache,
  so no visitor's data is kept on the server.
- LABELKIT_APP_PROVIDERS: comma-separated model choices offered (default "ollama,openai").
"""

import os
import sys
import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd

ROOT = Path(__file__).parents[1]
try:
    import labelkit  # noqa: F401
except ImportError:  # not pip-installed (e.g. on a Hugging Face Space): use the source tree
    sys.path.insert(0, str(ROOT / "src"))

from labelkit.catalog import Catalog
from labelkit.config import Settings
from labelkit.i18n import LANGUAGE_NAMES
from labelkit.llm import LLM
from labelkit.pipeline import process_product
from labelkit.schemas import ProductResult
from labelkit.tools.ocr import list_images
from labelkit.tools.shopify import result_fields

SAMPLES = ROOT / "samples"
PRECOMPUTED = ROOT / "eval" / "results"
# On a Hugging Face Space (SPACE_ID is set by the platform) the defaults switch to a safe public
# demo: no local model, per-session catalog, nothing written to disk.
ON_SPACE = bool(os.environ.get("SPACE_ID"))
CATALOG_DIR = os.environ.get(
    "LABELKIT_CATALOG_DIR", "" if ON_SPACE else str(ROOT / "output" / "catalog")
)
PROVIDERS = [
    p.strip()
    for p in os.environ.get(
        "LABELKIT_APP_PROVIDERS", "openai" if ON_SPACE else "ollama,openai"
    ).split(",")
]
PROVIDER_INFO = {
    "ollama": "ollama = local model (needs Ollama running)",
    "openai": "openai = gpt-4o-mini with your own API key",
}

FIELD_NAMES = {
    "legal_name": "Legal name",
    "ingredients": "Ingredients",
    "allergens": "Allergens",
    "net_quantity": "Net quantity",
    "storage": "Storage",
    "usage": "Usage",
    "responsible_operator": "Responsible operator",
    "country_of_origin": "Country of origin",
    "alcohol_by_volume": "Alcohol",
    "nutrition": "Nutrition",
}
FIELD_KEYS = {name: key for key, name in FIELD_NAMES.items()}


# -- conversions between catalog fields and the editable table ----------------------------------
def fields_to_table(fields: dict[str, dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Field": name, **{lang.upper(): fields[lang].get(key, "") for lang in fields}}
            for key, name in FIELD_NAMES.items()
        ]
    )


def fields_view(fields: dict[str, dict[str, str]] | None):
    """The fields table with one equal-width column per language, so all stay on screen."""
    if not fields:
        return gr.update(value=None)
    share = 84 / len(fields)
    widths = ["16%", *[f"{share:.0f}%" for _ in fields]]
    return gr.update(value=fields_to_table(fields), column_widths=widths)


def table_to_fields(table: pd.DataFrame) -> dict[str, dict[str, str]]:
    languages = [c for c in table.columns if c != "Field"]
    return {
        lang.lower(): {
            FIELD_KEYS[row["Field"]]: str(row[lang])
            for _, row in table.iterrows()
            if row["Field"] in FIELD_KEYS
        }
        for lang in languages
    }


def catalog_overview(catalog: Catalog) -> pd.DataFrame:
    rows = [
        {
            "Product ID": item.product_id,
            "Name": next(iter(item.fields.values()), {}).get("legal_name", ""),
            "Languages": ", ".join(lang.upper() for lang in item.fields),
            "Edited": "✓" if item.edited else "",
            "Review": "⚠" if item.source and item.source.warnings and not item.edited else "",
        }
        for item in catalog.items.values()
    ]
    return pd.DataFrame(rows, columns=["Product ID", "Name", "Languages", "Edited", "Review"])


def _catalog_views(catalog: Catalog, selected: str | None):
    """Refresh everything that shows the catalog: overview, picker, editor."""
    ids = list(catalog.items)
    selected = selected if selected in catalog.items else (ids[-1] if ids else None)
    item = catalog.items.get(selected)
    return (
        catalog,
        catalog_overview(catalog),
        gr.update(choices=ids, value=selected),
        selected or "",
        fields_view(item.fields if item else None),
        f"**{len(ids)} product(s) in the catalog.**",
    )


# -- actions -------------------------------------------------------------------------------------
def new_catalog() -> Catalog:
    return Catalog(CATALOG_DIR or None)


def _llm(provider, api_key, languages) -> LLM:
    if provider == "openai" and not api_key:
        raise gr.Error("Paste an OpenAI API key, or switch to the local model.")
    if not languages:
        raise gr.Error("Choose at least one target language.")
    # The key only lives in this request's settings; it is never logged or stored.
    settings = Settings(provider=provider, api_key=api_key or None, languages=languages)
    if not CATALOG_DIR:  # public demo: keep nothing on disk
        settings.cache_dir = None
    return LLM(settings)


def extract_products(cards, provider, api_key, languages, catalog):
    """Extract every product card, one by one, streaming a status table.

    `cards` is a list of (card_key, product_id, photos). Yields (status, cards_left, *views);
    at the end only the cards that failed are left on the page, so they can be retried.
    """
    cards = [(key, (pid or "").strip(), photos) for key, pid, photos in cards if photos]
    if not cards:
        raise gr.Error("Add at least one product with photos.")
    llm = _llm(provider, api_key, languages)
    next_number = len(catalog.items) + 1
    named = []
    for key, pid, photos in cards:
        if not pid:
            while f"product-{next_number}" in catalog.items:
                next_number += 1
            pid, next_number = f"product-{next_number}", next_number + 1
        named.append((key, pid, photos))
    ids = [pid for _, pid, _ in named]
    if duplicates := sorted({pid for pid in ids if ids.count(pid) > 1}):
        raise gr.Error(f"Each product needs its own ID. Repeated: {', '.join(duplicates)}")

    status = {pid: "waiting" for pid in ids}
    failed = []

    def table():
        return pd.DataFrame({"Product ID": list(status), "Status": list(status.values())})

    for key, pid, photos in named:
        status[pid] = f"running ({len(photos)} photo(s))…"
        yield table(), gr.skip(), *_catalog_views(catalog, None)
        try:
            result = process_product(llm, [Path(p) for p in photos], pid, llm.settings.languages)
            catalog.add(result, pid)
            status[pid] = "⚠ added, needs review" if result.warnings else "✓ added"
        except Exception as error:  # keep going with the next product
            status[pid] = f"✗ failed: {str(error).splitlines()[0]}"[:200]
            failed.append(key)
        yield table(), gr.skip(), *_catalog_views(catalog, None)
    gr.Info(f"Done: {len(ids) - len(failed)}/{len(ids)} product(s) added to the catalog.")
    cards_left = failed or [max(key for key, _, _ in cards) + 1]
    yield table(), cards_left, *_catalog_views(catalog, None)


def show_example(name):
    if not name:
        return [], None, ""
    images = [str(p) for p in list_images(SAMPLES / name)]
    result = load_example(name)
    ocr = "\n\n".join(f"### {file}\n{text}" for file, text in result.ocr.items())
    return images, fields_view(result_fields(result)), ocr


def load_example(name) -> ProductResult:
    return ProductResult.model_validate_json((PRECOMPUTED / f"{name}.json").read_text("utf-8"))


def add_example(name, catalog):
    if not name:
        raise gr.Error("Pick an example first.")
    catalog.add(load_example(name), name)
    gr.Info(f"Added {name} to the catalog.")
    return _catalog_views(catalog, name)


def select_product(product_id, catalog):
    return _catalog_views(catalog, product_id)


def save_edits(selected, new_id, table, catalog):
    if not selected:
        raise gr.Error("No product selected.")
    if not (new_id or "").strip():
        raise gr.Error("The product ID can't be empty.")
    catalog.update(selected, table_to_fields(pd.DataFrame(table)), new_id)
    gr.Info("Saved.")
    return _catalog_views(catalog, new_id.strip())


def delete_product(selected, catalog):
    if not selected:
        raise gr.Error("No product selected.")
    catalog.delete(selected)
    gr.Info(f"Deleted {selected}.")
    return _catalog_views(catalog, None)


def generate_csv(catalog):
    if not catalog.items:
        raise gr.Error("The catalog is empty: extract or add a product first.")
    path = Path(tempfile.mkdtemp()) / f"shopify_import_{len(catalog.items)}_products.csv"
    catalog.to_dataframe().to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


# -- layout --------------------------------------------------------------------------------------
# Best results first; anything else (e.g. newly added results) after, alphabetically.
EXAMPLE_ORDER = ["toscana-sausage", "coxinha", "strawberry-pulp", "cassava"]
examples = sorted(
    (p.stem for p in PRECOMPUTED.glob("*.json")),
    key=lambda name: (EXAMPLE_ORDER.index(name) if name in EXAMPLE_ORDER else 99, name),
)
LANGUAGE_CHOICES = [(f"{name} ({code})", code) for code, name in LANGUAGE_NAMES.items()]

with gr.Blocks(title="Label extractor") as demo:
    catalog = gr.State(new_catalog)
    gr.Markdown(
        "# Label extractor\nPhotos of a product label → EU label fields in the languages you "
        "choose. Every product goes into an editable catalog, exported as one Shopify import CSV. "
        "[Source code](https://github.com/luiznery/label-extractor)"
    )

    with gr.Tab("Extract"):
        with gr.Row():
            provider = gr.Radio(
                PROVIDERS,
                value=PROVIDERS[0],
                label="Model",
                interactive=True,  # only used by listeners created in render_cards
                info="; ".join(PROVIDER_INFO.get(p, p) for p in PROVIDERS),
            )
            api_key = gr.Textbox(
                label="OpenAI API key (only for openai)",
                type="password",
                interactive=True,
                placeholder="sk-…  used for this request only, never stored",
            )
        languages = gr.CheckboxGroup(
            LANGUAGE_CHOICES,
            value=Settings.model_fields["languages"].default,
            label="Target languages",
            interactive=True,
            info="The fields are translated into each language checked (first one = main).",
        )
        gr.Markdown(
            "Add one card per product, each with its own photos (front, back, nutrition "
            "table…). Re-using an ID that is already in the catalog replaces that product."
        )
        # The cards are redrawn only when one is added or removed (card_keys changes). What the
        # user typed or uploaded is kept in card_data and set explicitly on every redraw, and each
        # card's components have their own `key`, so a redraw never loses, shifts or reuses values.
        card_keys = gr.State([0])
        card_data = gr.State({})  # card key -> {"id": str, "photos": list of paths}

        def _set(field):
            def setter(value, data, key):
                data.setdefault(key, {})[field] = value
                return data

            return setter

        @gr.render(inputs=[card_keys, card_data], triggers=[card_keys.change, demo.load])
        def render_cards(keys, data):
            id_boxes, uploads = [], []
            for number, key in enumerate(keys, 1):
                saved = data.get(key, {})
                with gr.Group():
                    with gr.Row(equal_height=True):
                        id_box = gr.Textbox(
                            value=saved.get("id", ""),
                            label=f"Product {number}: ID",
                            placeholder="Shopify product ID (optional)",
                            scale=5,
                            key=f"id-{key}",
                        )
                        remove_btn = gr.Button("Remove", scale=1, key=f"remove-{key}")
                    upload = gr.File(
                        value=saved.get("photos"),
                        file_count="multiple",
                        file_types=["image"],
                        label="Photos of this product",
                        key=f"photos-{key}",
                    )
                key_state = gr.State(key)
                id_box.change(_set("id"), [id_box, card_data, key_state], card_data)
                upload.change(_set("photos"), [upload, card_data, key_state], card_data)
                remove_btn.click(
                    lambda ks, k=key: [x for x in ks if x != k] or [max(ks) + 1],
                    card_keys,
                    card_keys,
                )
                id_boxes.append(id_box)
                uploads.append(upload)

            def run(provider, api_key, languages, catalog, *values):
                ids, photos = values[: len(keys)], values[len(keys) :]
                cards = list(zip(keys, ids, photos, strict=True))
                for status, *rest in extract_products(cards, provider, api_key, languages, catalog):
                    yield gr.update(value=status, visible=True), *rest

            extract_btn.click(
                run,
                [provider, api_key, languages, catalog, *id_boxes, *uploads],
                [extract_status, card_keys, *views],
            )

        with gr.Row():
            add_card_btn = gr.Button("+ Add product")
            extract_btn = gr.Button("Extract all and add to catalog", variant="primary")
        extract_status = gr.Dataframe(
            label="Progress",
            interactive=False,
            wrap=True,
            visible=False,
            column_widths=["25%", "75%"],
        )

    with gr.Tab("Catalog"):
        summary = gr.Markdown()
        overview = gr.Dataframe(
            label="Products",
            interactive=False,
            wrap=True,
            column_widths=["18%", "50%", "14%", "9%", "9%"],
        )
        with gr.Row():
            picker = gr.Dropdown(label="Edit product", choices=[])
            edit_id = gr.Textbox(label="Product ID")
        editor = gr.Dataframe(
            label="Fields (click a cell to edit)",
            interactive=True,
            wrap=True,
            static_columns=[0],
        )
        with gr.Row():
            save_btn = gr.Button("Save changes", variant="primary")
            delete_btn = gr.Button("Delete product", variant="stop")
        with gr.Row():
            csv_btn = gr.Button("Generate CSV with all products")
            csv_file = gr.File(label="Shopify import CSV")

    with gr.Tab("Examples"):
        gr.Markdown(
            "Precomputed with the local models, so they load instantly. Add one to the "
            "catalog to try the edit/export flow without waiting for a model."
        )
        with gr.Row():
            choice = gr.Dropdown(examples, value=examples[0] if examples else None, label="Product")
            add_example_btn = gr.Button("Add to catalog")
        gallery = gr.Gallery(label="Label photos", height=300, columns=4)
        ex_table = gr.Dataframe(label="Extracted fields", wrap=True)
        with gr.Accordion("Raw OCR text", open=False):
            ex_ocr = gr.Markdown()

    views = [catalog, overview, picker, edit_id, editor, summary]

    add_card_btn.click(lambda ks: [*ks, max(ks, default=-1) + 1], card_keys, card_keys)
    picker.input(select_product, [picker, catalog], views)
    save_btn.click(save_edits, [picker, edit_id, editor, catalog], views)
    delete_btn.click(delete_product, [picker, catalog], views)
    csv_btn.click(generate_csv, catalog, csv_file)
    choice.change(show_example, choice, [gallery, ex_table, ex_ocr])
    add_example_btn.click(add_example, [choice, catalog], views)
    demo.load(show_example, choice, [gallery, ex_table, ex_ocr])
    demo.load(select_product, [picker, catalog], views)

if __name__ == "__main__":
    demo.launch()
