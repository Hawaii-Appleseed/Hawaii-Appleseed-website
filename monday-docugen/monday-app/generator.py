"""The document-generation step, shared by the custom action and the item view.

All of the actual work is the engine from ../docugen.py — this module only resolves
templates, names the output, and decides whether to convert and upload.
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import docugen  # noqa: E402

TEMPLATE_DIR = pathlib.Path(
    os.environ.get("DOCUGEN_TEMPLATE_DIR", pathlib.Path(__file__).parent / "templates")
)
OUTPUT_DIR = pathlib.Path(
    os.environ.get("DOCUGEN_OUTPUT_DIR", pathlib.Path(__file__).parent / "output")
)
FAKE = os.environ.get("DOCUGEN_FAKE_MONDAY") == "1"


class GenerationError(RuntimeError):
    status = 400


def list_templates() -> list[dict]:
    """Templates available to the account, in monday's remote-options shape."""
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    return [{"title": p.stem, "value": p.name}
            for p in sorted(TEMPLATE_DIR.glob("*.docx")) if not p.name.startswith("~$")]


def resolve_template(name: str | None) -> pathlib.Path:
    available = list_templates()
    if not available:
        raise GenerationError(f"No .docx templates installed in {TEMPLATE_DIR}")
    if not name:
        if len(available) > 1:
            raise GenerationError("No template specified and more than one is installed")
        name = available[0]["value"]
    # Never let a recipe value escape the template directory.
    candidate = (TEMPLATE_DIR / pathlib.Path(name).name)
    if not candidate.exists() and not candidate.suffix:
        candidate = candidate.with_suffix(".docx")
    if not candidate.exists():
        raise GenerationError(f"Template not found: {name}")
    return candidate


def _fetch_item(token: str, item_id: str) -> dict:
    if FAKE:
        from fixtures import fake_item
        return fake_item(item_id)
    return docugen.fetch_item(token, item_id)


def _upload(token: str, item_id: str, column_id: str, path: pathlib.Path) -> dict:
    if FAKE:
        return {"id": "fake-asset", "name": path.name}
    return docugen.upload_to_column(token, item_id, column_id, path)


def generate_for_item(*, token: str, item_id: str, template: str | None = None,
                      output_format: str = "docx", files_column: str | None = None,
                      filename_pattern: str | None = None) -> dict:
    """Render one item into a document. Returns a JSON-serialisable result."""
    if not item_id:
        raise GenerationError("No item id in the request")
    template_path = resolve_template(template)

    item = _fetch_item(token, item_id)
    context = docugen.base_context() | docugen.build_item_context(item)

    pattern = filename_pattern or "{{ name }}"
    stem = docugen._out_path(pattern, context).name
    out_dir = OUTPUT_DIR / str(item_id)
    docx_path = docugen.render(template_path, context, out_dir / f"{stem}.docx")

    final = docx_path
    if output_format.lower() == "pdf":
        final = docugen.to_pdf(docx_path)
        docx_path.unlink(missing_ok=True)

    result = {"item_id": str(item_id), "item_name": item.get("name"),
              "template": template_path.name, "format": output_format.lower(),
              "file": str(final), "filename": final.name,
              "size_bytes": final.stat().st_size}
    if files_column:
        asset = _upload(token, item_id, files_column, final)
        result["uploaded"] = {"column_id": files_column, "asset": asset}
    return result


def extract_item_id(payload: dict) -> str | None:
    """Dig the item id out of a custom-action payload.

    Recipes deliver it in different places depending on how the sentence is built, and a
    field can arrive as a scalar or as an object with a `value`/`id`.
    """
    def unwrap(v):
        if isinstance(v, dict):
            return v.get("value") or v.get("id") or v.get("itemId")
        return v

    for source in (payload.get("inputFields"), payload.get("inboundFieldValues")):
        if not isinstance(source, dict):
            continue
        for key in ("itemId", "item_id", "pulseId", "itemID"):
            if key in source:
                found = unwrap(source[key])
                if found:
                    return str(found)
        item = source.get("item")
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return None
