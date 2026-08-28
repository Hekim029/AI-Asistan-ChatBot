"""Komut satırından Heko kalite senaryolarını çalıştırır."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from evals.evaluator import (
    DEFAULT_SUITE_PATH,
    run_live_local_suite,
    run_offline_suite,
    summarize_results,
)
from services.security import secure_write_json


def _print_results(title: str, results) -> dict:
    summary = summarize_results(results)
    print(f"\n{title}")
    print("=" * len(title))
    for item in results:
        icon = "ATLA" if item.skipped else ("GEÇTİ" if item.passed else "KALDI")
        print(f"[{icon:5}] {item.scenario_id} — {item.detail}")
    print(
        f"\nPuan: %{summary['score']:.1f} | "
        f"Geçti: {summary['passed']} | Kaldı: {summary['failed']} | "
        f"Atlandı: {summary['skipped']}"
    )
    return summary


def main() -> int:
    # VS Code/PowerShell yönlendirmelerinde Türkçe raporun bozulmaması için
    # mümkün olduğunda çıktıyı açıkça UTF-8 üret.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(
        description="Heko'nun yönlendirme, güvenlik ve kişilik kalite testleri."
    )
    parser.add_argument(
        "--suite", type=Path, default=DEFAULT_SUITE_PATH,
        help="Kullanılacak scenarios.json yolu.",
    )
    parser.add_argument(
        "--live-local", action="store_true",
        help="Ayrıca seçili Ollama modeliyle dört kişilik yanıtı üretir.",
    )
    parser.add_argument(
        "--json-report", type=Path,
        help="Sonuçları hassas verileri maskelenmiş JSON raporuna yazar.",
    )
    args = parser.parse_args()

    offline_results = run_offline_suite(args.suite)
    offline_summary = _print_results("Çevrimdışı Heko değerlendirmesi", offline_results)
    live_results = []
    live_summary = None
    if args.live_local:
        live_results = run_live_local_suite(args.suite)
        live_summary = _print_results("Ollama kişilik değerlendirmesi", live_results)

    if args.json_report:
        report = {
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "suite": str(args.suite),
            "offline_summary": offline_summary,
            "offline_results": [item.safe_dict() for item in offline_results],
            "live_summary": live_summary,
            "live_results": [item.safe_dict() for item in live_results],
        }
        secure_write_json(args.json_report, report)
        print(f"\nRapor kaydedildi: {args.json_report}")

    failed = offline_summary["failed"] + ((live_summary or {}).get("failed", 0))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
