from __future__ import annotations

import argparse
import json
import mimetypes
import statistics
import sys
import time
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.v2.dependencies import get_llm, get_ocr  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.workers.extraction.pipeline import (  # noqa: E402
    DocumentExtractionPipeline,
    ExtractedQuestion,
    ExtractionResult,
)


def _guess_content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _normalize_text(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _label_to_int(label: str | None) -> int | None:
    if not label:
        return None
    digits = []
    for ch in str(label).strip():
        if ch.isdigit():
            digits.append(ch)
        elif digits:
            break
    if not digits:
        return None
    try:
        return int("".join(digits))
    except ValueError:
        return None


def _question_to_dict(item: ExtractedQuestion) -> dict[str, Any]:
    return {
        "orderIndex": item.order_index,
        "numberLabel": item.number_label,
        "confidence": item.confidence,
        "text": item.text,
        "metadata": dict(item.metadata or {}),
        "structure": dict(item.structure or {}),
    }


def _question_metrics(questions: list[ExtractedQuestion]) -> dict[str, Any]:
    if not questions:
        return {
            "questionCount": 0,
            "avgConfidence": 0.0,
            "emptyTextCount": 0,
            "emptyTextRatio": 0.0,
            "labeledCount": 0,
            "labeledRatio": 0.0,
            "uniqueLabelCount": 0,
            "duplicateLabelCount": 0,
            "monotonicNumberRatio": 0.0,
            "avgTextChars": 0.0,
            "avgChoiceCount": 0.0,
            "cropHintCoverage": 0.0,
            "overlapViolations": 0,
        }

    text_lengths = [len(_normalize_text(q.text)) for q in questions]
    empty_text_count = sum(1 for n in text_lengths if n == 0)
    labeled = [q.number_label for q in questions if _normalize_text(str(q.number_label or ""))]
    labels = [str(x).strip() for x in labeled]
    label_counter = Counter(labels)
    duplicate_label_count = sum(1 for _, c in label_counter.items() if c > 1)

    parsed_numbers = [_label_to_int(q.number_label) for q in questions]
    numeric = [n for n in parsed_numbers if n is not None]
    if len(numeric) >= 2:
        monotonic = sum(1 for i in range(len(numeric) - 1) if numeric[i + 1] > numeric[i])
        monotonic_ratio = monotonic / (len(numeric) - 1)
    else:
        monotonic_ratio = 0.0

    choice_counts = []
    crop_hint_count = 0
    overlap_violations = 0

    by_page: dict[int, list[dict[str, float]]] = defaultdict(list)
    for q in questions:
        structure = q.structure if isinstance(q.structure, dict) else {}
        parsed = structure.get("parsed_v1") if isinstance(structure.get("parsed_v1"), dict) else {}
        choices = parsed.get("choices") if isinstance(parsed.get("choices"), list) else []
        choice_counts.append(len(choices))

        metadata = q.metadata if isinstance(q.metadata, dict) else {}
        hint = metadata.get("cropHint") if isinstance(metadata.get("cropHint"), dict) else None
        if not hint:
            continue
        try:
            top = float(hint.get("topRatio"))
            bottom = float(hint.get("bottomRatio"))
            if not (bottom > top):
                continue
            left = float(hint.get("leftRatio")) if hint.get("leftRatio") is not None else 0.0
            right = float(hint.get("rightRatio")) if hint.get("rightRatio") is not None else 1.0
            page_index = int(hint.get("pageIndex") or metadata.get("pageIndex") or 1)
        except (TypeError, ValueError):
            continue

        crop_hint_count += 1
        by_page[page_index].append(
            {
                "top": max(0.0, min(1.0, top)),
                "bottom": max(0.0, min(1.0, bottom)),
                "left": max(0.0, min(1.0, left)),
                "right": max(0.0, min(1.0, right)),
            }
        )

    for _page, regions in by_page.items():
        for i in range(len(regions)):
            for j in range(i + 1, len(regions)):
                a = regions[i]
                b = regions[j]
                x_overlap = min(a["right"], b["right"]) - max(a["left"], b["left"])
                y_overlap = min(a["bottom"], b["bottom"]) - max(a["top"], b["top"])
                if x_overlap > 0 and y_overlap > 0:
                    overlap_violations += 1

    return {
        "questionCount": len(questions),
        "avgConfidence": round(float(statistics.fmean(q.confidence for q in questions)), 4),
        "emptyTextCount": empty_text_count,
        "emptyTextRatio": round(empty_text_count / len(questions), 4),
        "labeledCount": len(labels),
        "labeledRatio": round(len(labels) / len(questions), 4),
        "uniqueLabelCount": len(label_counter),
        "duplicateLabelCount": duplicate_label_count,
        "monotonicNumberRatio": round(monotonic_ratio, 4),
        "avgTextChars": round(float(statistics.fmean(text_lengths)), 2),
        "avgChoiceCount": round(float(statistics.fmean(choice_counts)), 3) if choice_counts else 0.0,
        "cropHintCoverage": round(crop_hint_count / len(questions), 4),
        "overlapViolations": overlap_violations,
    }


def _build_alignment(mode_a: list[ExtractedQuestion], mode_b: list[ExtractedQuestion]) -> dict[str, Any]:
    by_label_a = {
        str(q.number_label).strip(): q
        for q in mode_a
        if q.number_label is not None and str(q.number_label).strip()
    }
    by_label_b = {
        str(q.number_label).strip(): q
        for q in mode_b
        if q.number_label is not None and str(q.number_label).strip()
    }

    labels_a = set(by_label_a.keys())
    labels_b = set(by_label_b.keys())
    intersection = sorted(labels_a & labels_b, key=lambda x: (_label_to_int(x) or 10**9, x))
    union = labels_a | labels_b

    sims: list[float] = []
    for label in intersection:
        qa = _normalize_text(by_label_a[label].text)
        qb = _normalize_text(by_label_b[label].text)
        sims.append(SequenceMatcher(a=qa, b=qb).ratio())

    return {
        "countDelta": len(mode_a) - len(mode_b),
        "labelIntersectionCount": len(intersection),
        "labelUnionCount": len(union),
        "labelJaccard": round(len(intersection) / len(union), 4) if union else 1.0,
        "avgTextSimilarityOnMatchedLabels": round(float(statistics.fmean(sims)), 4) if sims else 0.0,
        "matchedLabelsPreview": intersection[:20],
    }


def _extract_once(
    *,
    mode: str,
    payload: bytes,
    content_type: str,
    filename: str,
) -> tuple[ExtractionResult | None, dict[str, Any]]:
    settings = get_settings()
    pipeline = DocumentExtractionPipeline(
        ocr_fallback=get_ocr(),
        ocr_lang=settings.ocr_lang,
        llm=get_llm(),
        llm_enabled=settings.extraction_llm_enabled,
        llm_model=settings.gemini_model,
        extraction_mode=mode,
    )

    started = time.perf_counter()
    try:
        result = pipeline.extract(payload=payload, content_type=content_type, filename=filename)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        metrics = _question_metrics(result.questions)
        metrics["elapsedMs"] = elapsed_ms
        metrics["engine"] = result.engine
        metrics["sourceType"] = result.source_type
        metrics["rawTextChars"] = len(_normalize_text(result.raw_text))
        return result, metrics
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return None, {"elapsedMs": elapsed_ms, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare extraction quality between two modes "
            "(default: hybrid vs gemini_full) on the same document."
        )
    )
    parser.add_argument("input", type=Path, help="Input PDF or image path")
    parser.add_argument("--mode-a", default="hybrid", help="First extraction mode")
    parser.add_argument("--mode-b", default="gemini_full", help="Second extraction mode")
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Number of question previews to include per mode",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to save JSON report",
    )
    args = parser.parse_args()

    input_path = args.input.expanduser().resolve()
    if not input_path.exists() or not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    payload = input_path.read_bytes()
    content_type = _guess_content_type(input_path)
    filename = input_path.name

    report: dict[str, Any] = {
        "input": {
            "path": str(input_path),
            "filename": filename,
            "contentType": content_type,
            "sizeBytes": len(payload),
        },
        "settings": {
            "modeA": args.mode_a,
            "modeB": args.mode_b,
            "ocrBackend": get_settings().ocr_backend,
            "llmBackend": get_settings().llm_backend,
            "ocrLang": get_settings().ocr_lang,
            "geminiModel": get_settings().gemini_model,
        },
    }

    result_a, metrics_a = _extract_once(
        mode=args.mode_a,
        payload=payload,
        content_type=content_type,
        filename=filename,
    )
    result_b, metrics_b = _extract_once(
        mode=args.mode_b,
        payload=payload,
        content_type=content_type,
        filename=filename,
    )

    mode_a_questions = result_a.questions if result_a else []
    mode_b_questions = result_b.questions if result_b else []

    report["modeA"] = {
        "metrics": metrics_a,
        "questionsPreview": [_question_to_dict(q) for q in mode_a_questions[: max(0, args.preview)]],
    }
    report["modeB"] = {
        "metrics": metrics_b,
        "questionsPreview": [_question_to_dict(q) for q in mode_b_questions[: max(0, args.preview)]],
    }
    report["comparison"] = _build_alignment(mode_a_questions, mode_b_questions)

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output is not None:
        output_path = args.output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
