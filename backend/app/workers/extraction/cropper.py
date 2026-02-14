from __future__ import annotations

import io
import re
from collections import defaultdict, deque

from app.infra.ports.ocr import OCRPort
from app.infra.ports.storage import StoragePort

_QNO_TOKEN = re.compile(r"^(\d{1,3})(?:[.)]|번)?$")


class QuestionCropper:
    def __init__(
        self,
        *,
        storage: StoragePort,
        ocr_lang: str = "kor+eng",
        secondary_ocr: OCRPort | None = None,
    ):
        self.storage = storage
        self.ocr_lang = ocr_lang.strip() if ocr_lang and ocr_lang.strip() else "kor+eng"
        self.secondary_ocr = secondary_ocr

    @staticmethod
    def _ranges_from_hints(
        *,
        height: int,
        count: int,
        hints: list[dict | None] | None,
    ) -> list[tuple[int, int]] | None:
        if height <= 0 or count <= 0 or not hints:
            return None

        ranges: list[tuple[int, int]] = []
        last_end = 0
        for idx in range(count):
            hint = hints[idx] if idx < len(hints) else None
            if not isinstance(hint, dict):
                return None

            top_raw = hint.get("topRatio")
            bottom_raw = hint.get("bottomRatio")
            try:
                top = float(top_raw)
                bottom = float(bottom_raw)
            except Exception:
                return None

            top = max(0.0, min(1.0, top))
            bottom = max(0.0, min(1.0, bottom))
            if bottom <= top:
                return None

            y1 = max(last_end, int(top * height))
            y2 = int(bottom * height)
            if idx == count - 1:
                y2 = max(y2, height)
            if y2 <= y1 + 10:
                y2 = min(height, y1 + 30)
            if y2 <= y1:
                return None

            ranges.append((y1, y2))
            last_end = y2

        return ranges if len(ranges) == count else None

    @staticmethod
    def _ranges_from_page_hints(
        *,
        page_heights: list[int],
        page_widths: list[int] | None = None,
        question_count: int,
        hints: list[dict | None] | None,
    ) -> list[tuple[int, int, int, int, int, str]] | None:
        if question_count <= 0:
            return []
        if not page_heights or not hints or len(hints) < question_count:
            return None

        widths = page_widths or [0] * len(page_heights)

        parsed: list[dict] = []
        for idx in range(question_count):
            hint = hints[idx]
            if not isinstance(hint, dict):
                return None

            page_raw = hint.get("pageIndex")
            try:
                page_index = int(page_raw)
            except Exception:
                return None
            if page_index < 1 or page_index > len(page_heights):
                return None

            top = hint.get("topRatio")
            bottom = hint.get("bottomRatio")
            try:
                top_ratio = float(top)
                bottom_ratio = float(bottom)
                top_ratio = max(0.0, min(1.0, top_ratio))
                bottom_ratio = max(0.0, min(1.0, bottom_ratio))
                valid = bottom_ratio > top_ratio
            except Exception:
                top_ratio = 0.0
                bottom_ratio = 0.0
                valid = False

            try:
                left_ratio = float(hint.get("leftRatio"))
                right_ratio = float(hint.get("rightRatio"))
                left_ratio = max(0.0, min(1.0, left_ratio))
                right_ratio = max(0.0, min(1.0, right_ratio))
                has_x = right_ratio > left_ratio
            except (TypeError, ValueError):
                left_ratio = 0.0
                right_ratio = 1.0
                has_x = False

            parsed.append(
                {
                    "qidx": idx,
                    "pageIndex": page_index,
                    "valid": valid,
                    "top": top_ratio,
                    "bottom": bottom_ratio,
                    "left": left_ratio,
                    "right": right_ratio,
                    "has_x": has_x,
                }
            )

        assigned: dict[int, tuple[int, int, int, int, str]] = {}
        for page_index in range(1, len(page_heights) + 1):
            locals_for_page = [item for item in parsed if item["pageIndex"] == page_index]
            if not locals_for_page:
                continue

            # Group by column to deconflict Y-axis independently per column
            col_groups: dict[str, list[tuple[int, dict]]] = {}
            for local_idx, item in enumerate(locals_for_page):
                col = "left" if item["has_x"] and item["left"] < 0.4 else (
                    "right" if item["has_x"] and item["left"] >= 0.4 else "full"
                )
                col_groups.setdefault(col, []).append((local_idx, item))

            count = len(locals_for_page)
            ratios: list[tuple[float, float] | None] = [None] * count
            sources: list[str] = ["fallback"] * count

            for _col, col_items in col_groups.items():
                col_items.sort(key=lambda pair: pair[1]["top"])
                prev_end = 0.0
                for local_idx, item in col_items:
                    if not item["valid"]:
                        continue
                    top = max(prev_end, float(item["top"]))
                    bottom = float(item["bottom"])
                    if bottom <= top:
                        continue
                    ratios[local_idx] = (top, bottom)
                    sources[local_idx] = "gemini"
                    prev_end = bottom

            cursor = 0
            while cursor < count:
                if ratios[cursor] is not None:
                    cursor += 1
                    continue
                end = cursor
                while end < count and ratios[end] is None:
                    end += 1

                left = ratios[cursor - 1][1] if cursor > 0 and ratios[cursor - 1] is not None else 0.0
                right = ratios[end][0] if end < count and ratios[end] is not None else 1.0
                if right <= left:
                    right = min(1.0, left + (0.08 * max(1, end - cursor)))

                span = max(0.001, right - left)
                step = span / max(1, end - cursor)
                for fill_idx in range(cursor, end):
                    top = left + step * (fill_idx - cursor)
                    bottom = left + step * (fill_idx - cursor + 1)
                    ratios[fill_idx] = (top, bottom)
                    sources[fill_idx] = "fallback"
                cursor = end

            page_height = max(1, int(page_heights[page_index - 1]))
            page_width = max(1, int(widths[page_index - 1])) if widths else page_height
            _MIN_CROP_PX = 60
            for local_idx, item in enumerate(locals_for_page):
                top, bottom = ratios[local_idx] or (0.0, 1.0)
                y1 = max(0, min(page_height - 1, int(top * page_height)))
                y2 = max(y1 + 12, min(page_height, int(bottom * page_height)))
                if y2 - y1 < _MIN_CROP_PX:
                    expansion = (_MIN_CROP_PX - (y2 - y1)) // 2
                    y1 = max(0, y1 - expansion)
                    y2 = min(page_height, y1 + _MIN_CROP_PX)

                if item["has_x"]:
                    x1 = max(0, min(page_width - 1, int(item["left"] * page_width)))
                    x2 = max(x1 + 12, min(page_width, int(item["right"] * page_width)))
                else:
                    x1 = 0
                    x2 = page_width
                assigned[int(item["qidx"])] = (y1, y2, x1, x2, sources[local_idx])

        if len(assigned) != question_count:
            return None

        planned: list[tuple[int, int, int, int, int, str]] = []
        for qidx in range(question_count):
            item = parsed[qidx]
            y1, y2, x1, x2, source = assigned[qidx]
            planned.append((int(item["pageIndex"]) - 1, y1, y2, x1, x2, source))
        return planned

    @staticmethod
    def _normalize_ranges(height: int, count: int, starts: list[int] | None = None) -> list[tuple[int, int]]:
        if height <= 0 or count <= 0:
            return []

        if not starts:
            step = max(1, height // count)
            ranges = []
            for i in range(count):
                y1 = i * step
                y2 = height if i == count - 1 else min(height, (i + 1) * step)
                ranges.append((y1, y2))
            return ranges

        ordered = sorted(max(0, min(height - 1, y)) for y in starts)[:count]
        if not ordered:
            return QuestionCropper._normalize_ranges(height=height, count=count, starts=None)
        if len(ordered) < count:
            remaining = count - len(ordered)
            tail_base = ordered[-1]
            gap = max(30, (height - tail_base) // (remaining + 1))
            for i in range(remaining):
                ordered.append(min(height - 1, tail_base + gap * (i + 1)))

        ranges: list[tuple[int, int]] = []
        for idx, start in enumerate(ordered):
            end = ordered[idx + 1] if idx + 1 < len(ordered) else height
            y1 = max(0, start - 12)
            y2 = min(height, max(y1 + 30, end - 6))
            ranges.append((y1, y2))
        return ranges

    @staticmethod
    def _parse_question_no(label: str | None) -> int | None:
        if not label:
            return None
        matched = re.match(r"^\s*(\d{1,3})", str(label))
        if not matched:
            return None
        return int(matched.group(1))

    @staticmethod
    def _pick_starts_for_questions(
        *,
        height: int,
        question_labels: list[str | None],
        detected_starts: list[tuple[int, int]],
    ) -> list[int]:
        if not detected_starts:
            return []

        ordered = sorted((max(0, min(height - 1, y)), qno) for y, qno in detected_starts)
        by_qno: dict[int, deque[int]] = defaultdict(deque)
        y_list: list[int] = []
        for y, qno in ordered:
            by_qno[int(qno)].append(int(y))
            y_list.append(int(y))

        picked: list[int] = []
        cursor = 0
        for label in question_labels:
            target_qno = QuestionCropper._parse_question_no(label)
            chosen: int | None = None

            if target_qno is not None and by_qno[target_qno]:
                chosen = by_qno[target_qno].popleft()
            else:
                while cursor < len(y_list):
                    candidate = y_list[cursor]
                    cursor += 1
                    if not picked or candidate > picked[-1]:
                        chosen = candidate
                        break

            if chosen is not None:
                picked.append(chosen)

        return picked

    @staticmethod
    def _is_label_sequence_reliable(question_labels: list[str | None]) -> bool:
        parsed: list[int] = []
        for label in question_labels:
            qno = QuestionCropper._parse_question_no(label)
            if qno is not None:
                parsed.append(qno)

        if len(parsed) < 2:
            return False

        deltas = [parsed[idx + 1] - parsed[idx] for idx in range(len(parsed) - 1)]
        if not deltas:
            return False

        if any(delta <= 0 for delta in deltas):
            return False

        contiguous_ratio = sum(1 for delta in deltas if delta == 1) / len(deltas)
        return contiguous_ratio >= 0.6

    def _can_use_secondary_ocr(self) -> bool:
        provider = str(getattr(self.secondary_ocr, "provider_name", "") or "").lower()
        return provider not in {"", "mock"}

    @staticmethod
    def _starts_from_tokens(tokens: list[dict], width: int) -> list[tuple[int, int]]:
        if width <= 0 or not tokens:
            return []
        left_gate = int(width * 0.33)
        starts: list[tuple[int, int]] = []
        for token in tokens:
            if not isinstance(token, dict):
                continue
            text = str(token.get("text") or "").strip().replace(" ", "")
            if not text:
                continue
            matched = _QNO_TOKEN.match(text)
            if not matched:
                continue
            bbox = token.get("bbox")
            if not isinstance(bbox, dict):
                continue
            x = int(bbox.get("x1") or 0)
            y = int(bbox.get("y1") or 0)
            if x > left_gate:
                continue
            qno = int(matched.group(1))
            if qno <= 0 or qno > 200:
                continue
            starts.append((y, qno))
        starts.sort(key=lambda item: item[0])
        filtered: list[tuple[int, int]] = []
        last_y = -9999
        for y, qno in starts:
            if y - last_y < 18:
                continue
            filtered.append((y, qno))
            last_y = y
        return filtered

    @staticmethod
    def _render_pages(payload: bytes, content_type: str | None, filename: str | None):
        try:
            from PIL import Image
        except Exception:
            return []

        mime = (content_type or "").lower()
        lower_name = (filename or "").lower()

        if mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
            try:
                return [Image.open(io.BytesIO(payload)).convert("RGB")]
            except Exception:
                return []

        if mime.startswith("application/pdf") or lower_name.endswith(".pdf"):
            try:
                import fitz  # type: ignore
            except Exception:
                return []

            try:
                doc = fitz.open(stream=payload, filetype="pdf")
                try:
                    pages = []
                    for page in doc:
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                        pages.append(img)
                    return pages
                finally:
                    doc.close()
            except Exception:
                return []

        return []

    @staticmethod
    def _render_canvas(payload: bytes, content_type: str | None, filename: str | None):
        pages = QuestionCropper._render_pages(payload, content_type, filename)
        if not pages:
            return None
        if len(pages) == 1:
            return pages[0]
        from PIL import Image

        max_w = max(item.width for item in pages)
        total_h = sum(item.height for item in pages)
        canvas = Image.new("RGB", (max_w, total_h), "white")
        y = 0
        for page_img in pages:
            canvas.paste(page_img, (0, y))
            y += page_img.height
        return canvas

    def _detect_question_starts(self, image) -> list[tuple[int, int]]:
        if self._can_use_secondary_ocr():
            try:
                payload = self._encode_png(image)
                extracted = self.secondary_ocr.extract(payload)  # type: ignore[union-attr]
                tokens = extracted.get("tokens")
                if isinstance(tokens, list):
                    token_starts = self._starts_from_tokens(tokens, int(getattr(image, "width", 0) or 0))
                    if token_starts:
                        return token_starts
            except Exception:
                # Fall back to pytesseract-based start detection.
                pass

        try:
            import pytesseract  # type: ignore
        except Exception:
            return []

        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.ocr_lang,
                config="--oem 1 --psm 6",
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            return []

        count = len(data.get("text", []))
        starts: list[tuple[int, int]] = []
        width = max(1, int(getattr(image, "width", 1)))
        left_gate = int(width * 0.33)

        for idx in range(count):
            token = str(data["text"][idx] or "").strip()
            if not token:
                continue
            token = token.replace(" ", "")
            matched = _QNO_TOKEN.match(token)
            if not matched:
                continue
            x = int(data["left"][idx] or 0)
            y = int(data["top"][idx] or 0)
            if x > left_gate:
                continue
            qno = int(matched.group(1))
            if qno <= 0 or qno > 200:
                continue
            starts.append((y, qno))

        starts.sort(key=lambda item: item[0])
        filtered: list[tuple[int, int]] = []
        last_y = -9999
        for y, qno in starts:
            if y - last_y < 18:
                continue
            filtered.append((y, qno))
            last_y = y
        return filtered

    @staticmethod
    def _encode_png(image) -> bytes:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    def _create_and_store_traces(
        self,
        *,
        set_id: str,
        payload: bytes,
        content_type: str | None,
        filename: str | None,
        question_count: int,
        question_labels: list[str | None] | None = None,
        question_crop_hints: list[dict | None] | None = None,
    ) -> list[dict]:
        if question_count <= 0:
            return []

        pages = self._render_pages(payload=payload, content_type=content_type, filename=filename)
        if pages:
            planned = self._ranges_from_page_hints(
                page_heights=[int(page.height) for page in pages],
                page_widths=[int(page.width) for page in pages],
                question_count=question_count,
                hints=question_crop_hints,
            )
            if planned is not None and len(planned) == question_count:
                traces: list[dict] = []
                for idx, (page_zero, y1, y2, x1, x2, source) in enumerate(planned, start=1):
                    page_img = pages[page_zero]
                    if y2 <= y1:
                        traces.append({"url": None, "cropSource": source, "pageIndex": page_zero + 1})
                        continue
                    crop = page_img.crop((x1, y1, x2, y2))
                    key = f"{set_id}/questions/q_{idx:03d}.png"
                    url = self.storage.save_bytes(key, self._encode_png(crop), "image/png")
                    traces.append({"url": url, "cropSource": source, "pageIndex": page_zero + 1})
                return traces

        canvas = self._render_canvas(payload=payload, content_type=content_type, filename=filename)
        if canvas is None:
            return [{"url": None, "cropSource": "fallback"} for _ in range(question_count)]

        ranges = self._ranges_from_hints(
            height=canvas.height,
            count=question_count,
            hints=question_crop_hints,
        )
        if ranges is None:
            starts_with_qno = self._detect_question_starts(canvas)
            labels = question_labels or [None for _ in range(question_count)]
            if self._is_label_sequence_reliable(labels[:question_count]):
                picked_starts = self._pick_starts_for_questions(
                    height=canvas.height,
                    question_labels=labels[:question_count],
                    detected_starts=starts_with_qno,
                )
            else:
                picked_starts = [int(y) for y, _ in starts_with_qno[:question_count]]
            ranges = self._normalize_ranges(height=canvas.height, count=question_count, starts=picked_starts)
        if not ranges:
            return [{"url": None, "cropSource": "fallback"} for _ in range(question_count)]

        traces: list[dict] = []
        for idx, (y1, y2) in enumerate(ranges, start=1):
            if y2 <= y1:
                traces.append({"url": None, "cropSource": "fallback"})
                continue
            crop = canvas.crop((0, y1, canvas.width, y2))
            key = f"{set_id}/questions/q_{idx:03d}.png"
            url = self.storage.save_bytes(key, self._encode_png(crop), "image/png")
            traces.append({"url": url, "cropSource": "fallback"})
        return traces

    def create_and_store_with_trace(
        self,
        *,
        set_id: str,
        payload: bytes,
        content_type: str | None,
        filename: str | None,
        question_count: int,
        question_labels: list[str | None] | None = None,
        question_crop_hints: list[dict | None] | None = None,
    ) -> list[dict]:
        return self._create_and_store_traces(
            set_id=set_id,
            payload=payload,
            content_type=content_type,
            filename=filename,
            question_count=question_count,
            question_labels=question_labels,
            question_crop_hints=question_crop_hints,
        )

    def create_and_store(
        self,
        *,
        set_id: str,
        payload: bytes,
        content_type: str | None,
        filename: str | None,
        question_count: int,
        question_labels: list[str | None] | None = None,
        question_crop_hints: list[dict | None] | None = None,
    ) -> list[str | None]:
        traces = self._create_and_store_traces(
            set_id=set_id,
            payload=payload,
            content_type=content_type,
            filename=filename,
            question_count=question_count,
            question_labels=question_labels,
            question_crop_hints=question_crop_hints,
        )
        return [item.get("url") for item in traces]
