#!/usr/bin/env python3
"""Generate an HA Expense Request PDF, correcting the board's own Amount bug on the way.

Board 7290593651's Amount formula on subitems is `{Expense Amt}` only - a mileage-only
line computes $0, and the Total mirror (which sums Amount) inherits the same blind spot.
monday's API has no mutation to edit an existing formula column's expression
(change_column_metadata only covers title/description), so fixing the formula itself
means editing it by hand in the monday UI. This script fixes it in the document instead:
Amount is recomputed as Expense Amt + Miles x Mileage Rate before the template ever sees
it, so the board's own (wrong) Amount and Total values are never used.

Usage, same shape as docugen.py generate:
    ./generate_expense_request.py 12836259678 --pdf --upload-column files__1
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import docugen as D  # noqa: E402

TEMPLATE = pathlib.Path(__file__).parent / "HA Expense Request.docx"


def correct_mileage_amounts(context: dict) -> None:
    """Overwrite each subitem's Amount with Expense Amt + Miles x Mileage Rate."""
    for subitem in context.get("subitems", []):
        c = subitem.get("c", {})
        corrected = (D.as_number(c.get("expense_amt"))
                    + D.as_number(c.get("miles")) * D.as_number(c.get("mileage_rate")))
        c["amount"] = corrected


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("item", nargs="+", help="one or more monday item ids")
    parser.add_argument("--out", default=str(pathlib.Path(__file__).parent / "out" /
                                             "{{ name }}.docx"))
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--keep-docx", action="store_true")
    parser.add_argument("--upload-column")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--token")
    args = parser.parse_args(argv)

    token = D.get_token(args.token)
    for item_id in args.item:
        item = D.fetch_item(token, item_id)
        context = D.base_context() | D.build_item_context(item)
        correct_mileage_amounts(context)

        if args.dry_run:
            import json
            print(f"=== item {item_id} ===")
            print(json.dumps({s["name"]: s["c"]["amount"] for s in context["subitems"]},
                             indent=2, default=str))
            continue

        path = D._out_path(args.out, context)
        docx_path = D.render(TEMPLATE, context,
                             path if path.suffix == ".docx" else path.with_suffix(".docx"))
        final = D.to_pdf(docx_path) if args.pdf else docx_path
        if args.pdf and not args.keep_docx and final != docx_path:
            docx_path.unlink(missing_ok=True)
        print(f"Wrote {final}")

        if args.upload_column:
            info = D.upload_to_column(token, item_id, args.upload_column, final)
            print(f"  uploaded to item {item_id} column {args.upload_column} "
                 f"(asset {info['id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
