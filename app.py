"""Command-line interface for comparing kW data in two engineering PDFs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kw_compare import compare_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare kW values between two engineering PDFs")
    parser.add_argument("pdf_a", type=Path, help="First/reference PDF")
    parser.add_argument("pdf_b", type=Path, help="Second/verification PDF")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Allowed difference in kW (default: 0.01)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    results = compare_pdfs(args.pdf_a, args.pdf_b, tolerance_kw=args.tolerance)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
        return

    print("PDF kW DOĞRULAMA")
    print("=" * 72)
    for item in results:
        left = "-" if item.pdf_a_kw is None else f"{item.pdf_a_kw:g} kW"
        right = "-" if item.pdf_b_kw is None else f"{item.pdf_b_kw:g} kW"
        symbol = {"MATCH": "✓", "MISMATCH": "✗", "ONLY_IN_PDF_A": "⚠", "ONLY_IN_PDF_B": "⚠"}[item.status]
        print(f"{symbol} {item.equipment:12} {item.field:20} {left:>10}  ↔  {right:<10} {item.status}")
        if item.status == "MISMATCH":
            print(f"    Fark: {item.difference_kw:g} kW")


if __name__ == "__main__":
    main()
