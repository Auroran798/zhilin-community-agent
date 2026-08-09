from __future__ import annotations

import json
import random
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_pipeline.config import DOWNLOAD_PAGE_SIZE, DOWNLOAD_RETRIES, DOWNLOAD_TIMEOUT_SECONDS, USER_AGENT
from data_pipeline.types import DatasetSpec


class SocrataDownloader:
    """Small SODA client using documented GET endpoints and cooperative pagination.

    It deliberately does not authenticate, scrape HTML, or attempt to work around
    a 403/CAPTCHA. Resuming only appends complete JSONL pages.
    """
    def __init__(self, page_size: int = DOWNLOAD_PAGE_SIZE, timeout: int = DOWNLOAD_TIMEOUT_SECONDS, retries: int = DOWNLOAD_RETRIES):
        self.page_size, self.timeout, self.retries = page_size, timeout, retries

    def _request_json(self, endpoint: str, params: dict[str, str | int]) -> list[dict]:
        url = endpoint + "?" + urlencode(params)
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                rows = payload.get("value", payload) if isinstance(payload, dict) else payload
                if not isinstance(rows, list):
                    raise ValueError("Socrata response is not an array")
                return rows
            except Exception as exc:  # caller receives the final original context
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(1.2 * (attempt + 1))
        raise RuntimeError(f"Official SODA request failed for {endpoint}; no fallback source used") from last_error

    @staticmethod
    def _completed_keys(destination: Path, id_field: str) -> set[str]:
        if not destination.exists():
            return set()
        keys: set[str] = set()
        with destination.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line).get(id_field)
                    if value is not None:
                        keys.add(str(value))
                except json.JSONDecodeError:
                    continue
        return keys

    def download_stratified(self, spec: DatasetSpec, destination: Path, target_rows: int) -> dict[str, int]:
        """Deterministic random-offset sampling avoids a first-N extraction.

        The official service's filtered queries may time out for very large live
        tables. This algorithm samples pages across the full published row range,
        then the profile verifies category coverage. It keeps the raw response
        intact and is reproducible from the manifest's fixed algorithm/version.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        seen = self._completed_keys(destination, spec.source_id_field)
        before = len(seen)
        needed = max(0, target_rows - before)
        rng = random.Random(f"stage6-reservoir-v1:{spec.dataset_id}")
        pages = 0
        select = ",".join(spec.selected_fields)
        with destination.open("a", encoding="utf-8", newline="\n") as output:
            while needed > 0:
                limit = min(self.page_size, needed)
                max_offset = max(0, spec.source_row_count - limit)
                offset = rng.randrange(max_offset + 1) if max_offset else 0
                page = self._request_json(spec.api_url, {"$select": select, "$limit": limit, "$offset": offset})
                pages += 1
                if not page:
                    raise RuntimeError("Official SODA API returned an empty sampled page")
                added = 0
                for item in page:
                    key = str(item.get(spec.source_id_field, ""))
                    if key and key not in seen:
                        output.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
                        seen.add(key); added += 1
                output.flush(); needed = max(0, target_rows - len(seen))
                if added == 0 and pages > 5:
                    raise RuntimeError("Repeated sampled pages produced no new source records")
                time.sleep(0.08)
        return {"existing_rows": before, "downloaded_rows": len(seen) - before, "total_rows": len(seen), "sample_pages": pages, "sampling_method": "deterministic_random_offset"}
