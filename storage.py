"""쇼핑 리스트 데이터 저장소 (data.json 읽기/쓰기).

저장 방식을 바꿀 때(예: 외부 DB)는 이 파일의 load_items / save_items / update_items만 교체한다.
"""

import json
import threading
import uuid
from pathlib import Path
from typing import Callable, TypeVar

DATA_FILE = Path(__file__).parent / "data.json"

MAX_QUANTITY = 999

T = TypeVar("T")

# Streamlit은 한 프로세스에서 세션마다 스레드로 실행되므로, 스레드 잠금으로 동시 저장을 직렬화한다.
_lock = threading.Lock()


def _normalize(raw: object, index: int) -> dict | None:
    """저장된 항목 하나를 데이터 모델(PRD 5.1)에 맞춘다. 쓸 수 없는 항목이면 None."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    item_id = raw.get("id")
    if not isinstance(item_id, str) or not item_id:
        # id가 없으면 위치와 이름으로 고정 id를 만들어, 다음 저장 전까지 실행마다 같은 id가 나오게 한다.
        item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{index}:{name}"))

    quantity = raw.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        quantity = 1

    created_at = raw.get("created_at")
    return {
        "id": item_id,
        "name": name.strip(),
        "quantity": min(max(quantity, 1), MAX_QUANTITY),
        "checked": raw.get("checked") is True,
        "created_at": created_at if isinstance(created_at, str) else "",
    }


def load_items() -> list[dict]:
    """data.json에서 항목 목록을 읽는다.

    파일이 없거나 깨져 있으면 빈 리스트를, 형식이 틀린 항목은 건너뛰거나 기본값으로 채운다.
    """
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []

    items = []
    seen_ids = set()
    for index, raw in enumerate(data):
        item = _normalize(raw, index)
        if item is not None and item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            items.append(item)
    return items


def save_items(items: list[dict]) -> None:
    """항목 목록을 data.json에 저장한다. 임시 파일에 먼저 쓴 뒤 교체해 파일 손상을 막는다."""
    tmp_file = DATA_FILE.with_suffix(".json.tmp")
    with tmp_file.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    tmp_file.replace(DATA_FILE)


def update_items(mutator: Callable[[list[dict]], T]) -> T:
    """최신 데이터를 읽어 mutator로 바꾼 뒤 저장한다 (읽기-수정-쓰기를 잠금 안에서 수행).

    세션마다 들고 있는 목록으로 파일 전체를 덮어쓰지 않으므로,
    여러 사람이 동시에 써도 다른 사람의 변경이 사라지지 않는다.
    mutator는 전달받은 리스트를 직접 수정하고, 반환값은 그대로 돌려준다.
    """
    with _lock:
        items = load_items()
        result = mutator(items)
        save_items(items)
        return result
