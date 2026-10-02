"""Command-line entry point: `labelkit --help`."""

import json
from pathlib import Path

import pandas as pd
import typer

from labelkit.config import Provider, Settings
from labelkit.evaluate import report, summary
from labelkit.llm import LLM
from labelkit.pipeline import process_folder
from labelkit.schemas import ProductLabel, ProductResult
from labelkit.tools import matching, shopify
from labelkit.tools.ocr import list_images, transcribe

app = typer.Typer(help="Food-label photos -> structured, translated product data.")

ProviderOpt = typer.Option(None, help="ollama (local) or openai. Default: LABELKIT_PROVIDER.")


def _llm(provider: Provider | None) -> LLM:
    settings = Settings(provider=provider) if provider else Settings()
    return LLM(settings)


def _product_folders(path: Path) -> list[Path]:
    """`path` is a product folder (contains images) or a folder of product folders."""
    if list_images(path):
        return [path]
    return sorted(p for p in path.iterdir() if p.is_dir() and list_images(p))


def _read_table(path: Path) -> pd.DataFrame:
    return pd.read_excel(path) if path.suffix in {".xlsx", ".xls"} else pd.read_csv(path)


@app.command()
def ocr(image: Path, provider: Provider | None = ProviderOpt):
    """Transcribe one label photo."""
    typer.echo(transcribe(_llm(provider), [image])[image.name])


@app.command()
def run(
    path: Path = typer.Argument(..., help="Product folder, or a folder of product folders."),
    output: Path = typer.Option(Path("output"), help="Where results are written."),
    provider: Provider | None = ProviderOpt,
    force: bool = typer.Option(False, help="Re-process products that already have results."),
):
    """Full pipeline: OCR -> extraction -> translation -> Shopify CSV."""
    llm = _llm(provider)
    typer.echo(f"Using {llm.settings.provider}: {llm.vision_model} / {llm.text_model}")
    results = []
    folders = _product_folders(path)
    for i, folder in enumerate(folders, 1):
        typer.echo(f"[{i}/{len(folders)}] {folder.name}")
        try:
            if result := process_folder(llm, folder, output / "products", force):
                results.append(result)
        except Exception as error:  # keep going: one unreadable label shouldn't stop a batch
            typer.secho(f"  failed: {error}", fg=typer.colors.RED)
    csv = output / "shopify_import.csv"
    shopify.to_rows(results).to_csv(csv, index=False, encoding="utf-8-sig")
    typer.echo(f"{len(results)} product(s) -> {csv}")


@app.command()
def export(
    results_dir: Path = typer.Argument(Path("output/products")),
    output: Path = typer.Option(Path("output/shopify_import.csv")),
    mapping: Path | None = typer.Option(None, help="Custom column mapping YAML."),
):
    """Rebuild the Shopify CSV from saved results (no LLM calls)."""
    results = [
        ProductResult.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(results_dir.glob("*.json"))
    ]
    shopify.to_rows(results, shopify.load_mapping(mapping)).to_csv(
        output, index=False, encoding="utf-8-sig"
    )
    typer.echo(f"{len(results)} product(s) -> {output}")


@app.command()
def merge(
    store_export: Path = typer.Argument(..., help="Product export from the store (CSV/XLSX)."),
    new: Path = typer.Argument(Path("output/shopify_import.csv")),
    output: Path = typer.Option(Path("output/store_import.xlsx")),
    mapping: Path | None = typer.Option(None),
):
    """Merge new label columns into a store product export, ready to re-import."""
    merged = shopify.merge_into_export(
        _read_table(store_export), pd.read_csv(new), shopify.load_mapping(mapping)
    )
    if output.suffix == ".xlsx":
        merged.to_excel(output, index=False)
    else:
        merged.to_csv(output, index=False, encoding="utf-8-sig")
    typer.echo(f"{len(merged)} product(s) -> {output}")


@app.command()
def match(
    catalog: Path = typer.Argument(..., help="CSV/XLSX with `id` and `name` columns."),
    queries: Path = typer.Argument(..., help="CSV/XLSX with a `name` column to match."),
    output: Path = typer.Option(Path("output/matches.csv")),
    use_llm: bool = typer.Option(True, help="Re-rank uncertain matches with the LLM."),
    provider: Provider | None = ProviderOpt,
):
    """Match free-text product names (e.g. invoice lines) to catalog products."""
    llm = _llm(provider) if use_llm else None
    names = _read_table(queries)["name"].astype(str).tolist()
    result = matching.match_all(names, _read_table(catalog), llm)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    typer.echo(result.to_string(index=False))


@app.command()
def evaluate(
    samples: Path = typer.Argument(Path("samples")),
    results_dir: Path = typer.Argument(Path("output/products")),
):
    """Compare results with each sample's expected.json (primary language)."""
    pairs = {}
    for expected_file in sorted(samples.glob("*/expected.json")):
        result_file = results_dir / f"{expected_file.parent.name}.json"
        if not result_file.exists():
            continue
        result = ProductResult.model_validate_json(result_file.read_text(encoding="utf-8"))
        predicted = next(iter(result.labels.values()))
        expected = ProductLabel.model_validate(json.loads(expected_file.read_text("utf-8")))
        pairs[expected_file.parent.name] = (predicted, expected)
    if not pairs:
        raise typer.Exit("No results found. Run `labelkit run samples` first.")
    table = report(pairs)
    typer.echo(table.map(lambda v: f"{v:.0%}" if isinstance(v, float) else v).to_string())
    typer.echo("")
    for name, value in summary(pairs).items():
        typer.echo(f"{name:>45}: {value:.0%}")


if __name__ == "__main__":
    app()
