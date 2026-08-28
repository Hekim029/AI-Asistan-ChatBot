"""Heko davranışlarını ağ bağlantısı olmadan ölçen senaryo çalıştırıcısı."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re

from core.local_intents import clarification_for, detect_local_tool, pending_slot_for
from services.llm_client import LLMClient
from services.local_model import LocalModelClient
from services.security import bounded_json_load, redact_sensitive_data
import utils.config as config


DEFAULT_SUITE_PATH = Path(__file__).with_name("scenarios.json")
MAX_SCENARIOS = 200


@dataclass(frozen=True)
class EvaluationResult:
    scenario_id: str
    category: str
    kind: str
    passed: bool
    skipped: bool
    detail: str
    actual: str = ""

    def safe_dict(self) -> dict:
        data = asdict(self)
        data["detail"] = redact_sensitive_data(data["detail"])[:2000]
        data["actual"] = redact_sensitive_data(data["actual"])[:4000]
        return data


def load_suite(path: str | Path = DEFAULT_SUITE_PATH) -> list[dict]:
    payload = bounded_json_load(path, max_bytes=512_000)
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("Değerlendirme paketi sürümü desteklenmiyor.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("Değerlendirme paketi senaryo içermiyor.")
    if len(scenarios) > MAX_SCENARIOS:
        raise ValueError("Değerlendirme paketi senaryo sınırını aşıyor.")
    seen = set()
    clean = []
    for item in scenarios:
        if not isinstance(item, dict):
            raise ValueError("Geçersiz değerlendirme senaryosu bulundu.")
        scenario_id = str(item.get("id", "")).strip()
        kind = str(item.get("kind", "")).strip()
        category = str(item.get("category", "")).strip()
        if not scenario_id or len(scenario_id) > 120 or scenario_id in seen:
            raise ValueError("Senaryo kimliği eksik, yinelenmiş veya çok uzun.")
        if not kind or not category:
            raise ValueError(f"{scenario_id}: tür veya kategori eksik.")
        seen.add(scenario_id)
        clean.append(dict(item))
    return clean


def _contains_all(text: str, values: list[object]) -> tuple[bool, list[str]]:
    folded = text.casefold()
    missing = [str(value) for value in values if str(value).casefold() not in folded]
    return not missing, missing


def _evaluate_text_contract(text: str, scenario: dict) -> tuple[bool, str]:
    required_ok, missing = _contains_all(text, scenario.get("required_all", []))
    forbidden = [
        str(value) for value in scenario.get("forbidden_all", [])
        if str(value).casefold() in text.casefold()
    ]
    passed = required_ok and not forbidden
    details = []
    if missing:
        details.append("eksik: " + ", ".join(missing))
    if forbidden:
        details.append("yasak ifade: " + ", ".join(forbidden))
    return passed, "; ".join(details) or "metin sözleşmesi karşılandı"


def _evaluate_offline(scenario: dict) -> EvaluationResult:
    scenario_id = scenario["id"]
    category = scenario["category"]
    kind = scenario["kind"]
    actual = ""
    passed = False
    detail = ""

    if kind == "local_route":
        detected = detect_local_tool(str(scenario.get("message", "")))
        expected_tool = scenario.get("expected_tool")
        actual_tool = detected[0] if detected else None
        actual_args = detected[1] if detected else None
        args_ok = (
            "expected_args" not in scenario
            or actual_args == scenario.get("expected_args")
        )
        passed = actual_tool == expected_tool and args_ok
        actual = repr(detected)
        detail = (
            "yerel yönlendirme doğru"
            if passed else f"beklenen={expected_tool!r}, gerçekleşen={actual!r}"
        )
    elif kind == "clarification":
        message = str(scenario.get("message", ""))
        response = clarification_for(message) or ""
        slot = pending_slot_for(message)
        text_ok, text_detail = _evaluate_text_contract(response, scenario)
        passed = text_ok and slot == scenario.get("expected_slot")
        actual = f"slot={slot!r}; yanıt={response}"
        detail = (
            "netleştirme doğru"
            if passed else f"{text_detail}; beklenen slot={scenario.get('expected_slot')!r}"
        )
    elif kind == "tool_candidates":
        tools = LLMClient._relevant_tools([
            {"role": "user", "content": str(scenario.get("message", ""))}
        ])
        names = {item.get("function", {}).get("name", "") for item in tools}
        missing = sorted(set(scenario.get("expected_in", [])) - names)
        forbidden = sorted(set(scenario.get("expected_not_in", [])) & names)
        passed = not missing and not forbidden
        actual = ", ".join(sorted(names)) or "araç yok"
        detail = "araç kümesi doğru" if passed else (
            f"eksik={missing or '-'}, gereksiz={forbidden or '-'}"
        )
    elif kind == "forced_tool":
        tool = LLMClient._forced_tool_for_first_turn([
            {"role": "user", "content": str(scenario.get("message", ""))}
        ])
        passed = tool == scenario.get("expected_tool")
        actual = repr(tool)
        detail = "zorunlu güvenlik aracı doğru" if passed else (
            f"beklenen={scenario.get('expected_tool')!r}, gerçekleşen={tool!r}"
        )
    elif kind == "display_safety":
        # UI modülünü yalnızca bu senaryo çalışırken yüklemek, tanılama ekranıyla
        # olası modül döngülerini önler.
        from ui.chat_window import response_for_display
        pending = (
            {"tool_name": scenario["pending_tool"]}
            if scenario.get("pending_tool") else None
        )
        actual = response_for_display(str(scenario.get("response", "")), pending)
        passed, detail = _evaluate_text_contract(actual, scenario)
    elif kind == "mode_contract":
        actual = config.MODES.get(str(scenario.get("mode", "")), "")
        passed, detail = _evaluate_text_contract(actual, scenario)
    elif kind == "system_contract":
        actual = LLMClient()._system_prompt("")
        passed, detail = _evaluate_text_contract(actual, scenario)
    elif kind == "response_quality":
        return EvaluationResult(
            scenario_id, category, kind, False, True,
            "yerel model testi istenmedi; --live-local ile çalıştırılabilir",
        )
    else:
        detail = f"desteklenmeyen senaryo türü: {kind}"

    return EvaluationResult(
        scenario_id, category, kind, passed, False, detail, str(actual)[:4000]
    )


def run_offline_suite(path: str | Path = DEFAULT_SUITE_PATH) -> list[EvaluationResult]:
    return [_evaluate_offline(item) for item in load_suite(path)]


def _clean_local_answer(text: str) -> str:
    value = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.I | re.S)
    return value.strip()


def _score_response(answer: str, rules: dict) -> tuple[bool, str]:
    clean = _clean_local_answer(answer)
    folded = clean.casefold()
    failures = []
    min_chars = max(0, int(rules.get("min_chars", 0)))
    max_chars = max(min_chars, int(rules.get("max_chars", 10_000)))
    if len(clean) < min_chars:
        failures.append(f"çok kısa ({len(clean)} < {min_chars})")
    if len(clean) > max_chars:
        failures.append(f"çok uzun ({len(clean)} > {max_chars})")
    missing_all = [
        str(value) for value in rules.get("required_all", [])
        if str(value).casefold() not in folded
    ]
    if missing_all:
        failures.append("eksik: " + ", ".join(missing_all))
    required_any = [str(value) for value in rules.get("required_any", [])]
    if required_any and not any(value.casefold() in folded for value in required_any):
        failures.append("beklenen ifadelerden hiçbiri yok: " + ", ".join(required_any))
    forbidden = [
        str(value) for value in rules.get("forbidden_all", [])
        if str(value).casefold() in folded
    ]
    if forbidden:
        failures.append("yasak ifade: " + ", ".join(forbidden))
    return not failures, "; ".join(failures) or "yanıt kalite kurallarını karşıladı"


def run_live_local_suite(
    path: str | Path = DEFAULT_SUITE_PATH,
) -> list[EvaluationResult]:
    scenarios = [item for item in load_suite(path) if item["kind"] == "response_quality"]
    client = LocalModelClient(
        getattr(config, "OLLAMA_MODEL", ""),
        getattr(config, "OLLAMA_URL", "http://127.0.0.1:11434"),
    )
    if not client.enabled:
        return [
            EvaluationResult(
                item["id"], item["category"], item["kind"], False, True,
                "Ayarlar > Sistem > Yerel Model bölümünde Ollama modeli seçilmemiş",
            )
            for item in scenarios
        ]

    results = []
    for item in scenarios:
        mode = str(item.get("mode", "normal"))
        system_prompt = config.MODES.get(mode, config.MODES["normal"])
        answer = client.chat([
            {
                "role": "system",
                "content": system_prompt + (
                    "\n\nBu bir yanıt kalite testidir. Hiçbir araç çağırma veya "
                    "bilgisayarda işlem yaptığını iddia etme; yalnızca cevap ver."
                ),
            },
            {"role": "user", "content": str(item.get("message", ""))[:2000]},
        ])
        clean = _clean_local_answer(answer or "")
        if not clean:
            results.append(EvaluationResult(
                item["id"], item["category"], item["kind"], False, False,
                "Ollama yanıt üretmedi; servis veya model çalışmıyor olabilir",
            ))
            continue
        passed, detail = _score_response(clean, item.get("rules", {}))
        results.append(EvaluationResult(
            item["id"], item["category"], item["kind"], passed, False,
            detail, clean[:4000],
        ))
    return results


def summarize_results(results: list[EvaluationResult]) -> dict:
    passed = sum(1 for item in results if item.passed and not item.skipped)
    failed = sum(1 for item in results if not item.passed and not item.skipped)
    skipped = sum(1 for item in results if item.skipped)
    measured = passed + failed
    categories = {}
    for item in results:
        row = categories.setdefault(item.category, {"passed": 0, "failed": 0, "skipped": 0})
        key = "skipped" if item.skipped else ("passed" if item.passed else "failed")
        row[key] += 1
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "measured": measured,
        "score": round((passed / measured) * 100, 1) if measured else 0.0,
        "categories": categories,
    }

