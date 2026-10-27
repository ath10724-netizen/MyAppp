"""쇼핑 리스트 Streamlit 앱."""

import html
import re
import uuid
from datetime import datetime

import streamlit as st

from storage import MAX_QUANTITY, load_items, update_items

MAX_NAME_LENGTH = 100

FILTER_ALL = "전체"
FILTER_TODO = "미구매"
FILTER_DONE = "구매 완료"

# 화면에 보이지 않는 문자(Word Joiner). URL·이메일이 자동 링크로 바뀌는 것을 막는 데 쓴다.
WORD_JOINER = "⁠"


# ---------------------------------------------------------------------------
# 데이터 모델 (PRD 5.1)
# ---------------------------------------------------------------------------
def new_item(name: str, quantity: int = 1) -> dict:
    """새 항목 딕셔너리를 만든다."""
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# 상태 초기화
# ---------------------------------------------------------------------------
# st.session_state.items는 dict의 .items() 메서드와 이름이 겹치므로 별도 키를 사용한다.
ITEMS_KEY = "shopping_items"


def init_state() -> None:
    """매 실행마다 저장소에서 최신 목록을 읽는다 (다른 사람이 바꾼 내용도 반영)."""
    st.session_state[ITEMS_KEY] = load_items()
    st.session_state.setdefault("add_error", None)  # 추가 실패 메시지
    st.session_state.setdefault("editing_id", None)  # 수정 중인 항목 id
    st.session_state.setdefault("edit_error", None)  # 수정 저장 실패 메시지
    st.session_state.setdefault("confirm_delete_all", False)  # 전체 삭제 확인 대기 여부
    st.session_state.setdefault("notices", [])  # 이번 화면에 띄울 알림

    # 다른 곳에서 삭제된 항목을 수정 중이었다면 수정 모드를 해제한다.
    if find_item(st.session_state.editing_id) is None:
        st.session_state.editing_id = None
    # 지울 항목이 없으면 전체 삭제 확인 대기도 해제한다.
    if not get_items():
        st.session_state.confirm_delete_all = False


def get_items() -> list[dict]:
    """현재 실행에서 읽은 항목 목록을 반환한다."""
    return st.session_state[ITEMS_KEY]


def find_item(item_id: str | None, items: list[dict] | None = None) -> dict | None:
    """id로 항목을 찾는다. 없으면 None."""
    items = get_items() if items is None else items
    return next((item for item in items if item["id"] == item_id), None)


def mutate(mutator):
    """저장소의 최신 데이터에 변경을 적용한다.

    다른 조작을 하면 전체 삭제 확인 대기는 해제한다 (확인 창이 남아 실수로 지우는 것 방지).
    """
    st.session_state.confirm_delete_all = False
    return update_items(mutator)


# ---------------------------------------------------------------------------
# 항목 조작 (모든 조작은 index가 아닌 id 기준)
# ---------------------------------------------------------------------------
def add_item(name: str, quantity: int = 1) -> bool:
    """항목 추가 (F-01 ~ F-04). 빈 이름이면 추가하지 않고 False를 반환한다."""
    name = name.strip()
    if not name:
        return False
    mutate(lambda items: items.append(new_item(name, quantity)))
    return True


def update_item(item_id: str, name: str, quantity: int) -> bool:
    """항목 이름/수량 수정 (F-10 ~ F-12). 항목이 이미 삭제되었으면 False를 반환한다."""

    def apply(items: list[dict]) -> bool:
        item = find_item(item_id, items)
        if item is None:
            return False
        item["name"] = name.strip()
        item["quantity"] = quantity
        return True

    return mutate(apply)


def delete_item(item_id: str) -> dict | None:
    """항목 개별 삭제 (F-13). 삭제한 항목을 반환한다."""

    def apply(items: list[dict]) -> dict | None:
        removed = find_item(item_id, items)
        items[:] = [item for item in items if item["id"] != item_id]
        return removed

    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    return mutate(apply)


def delete_checked_items() -> int:
    """체크된 항목 일괄 삭제 (F-14). 삭제한 개수를 반환한다."""

    def apply(items: list[dict]) -> int:
        before = len(items)
        items[:] = [item for item in items if not item["checked"]]
        return before - len(items)

    return mutate(apply)


def delete_all_items() -> None:
    """전체 삭제 (F-15)."""
    st.session_state.editing_id = None
    mutate(lambda items: items.clear())


def toggle_item(item_id: str) -> None:
    """구매 완료 체크 토글 (F-16, F-17). 체크박스 위젯 값을 항목에 반영한다."""
    checked = st.session_state[f"check_{item_id}"]

    def apply(items: list[dict]) -> None:
        item = find_item(item_id, items)
        if item is not None:
            item["checked"] = checked

    mutate(apply)


# ---------------------------------------------------------------------------
# 위젯 콜백
# ---------------------------------------------------------------------------
def notify(message: str, icon: str) -> None:
    """이번 화면 갱신 때 띄울 알림을 예약한다 (render_notices에서 표시)."""
    st.session_state.notices.append(f"{icon} {message}")


def start_edit(item_id: str) -> None:
    """수정 모드로 전환하고 입력창에 현재 값을 채운다."""
    item = find_item(item_id)
    if item is None:
        return
    st.session_state.editing_id = item_id
    st.session_state.edit_error = None
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = item["quantity"]


def save_edit(item_id: str) -> None:
    name = st.session_state[f"edit_name_{item_id}"]
    quantity = st.session_state[f"edit_qty_{item_id}"]
    if not name.strip():
        st.session_state.edit_error = "품목명을 입력해 주세요."
        return
    if not update_item(item_id, name, quantity):
        notify("다른 곳에서 이미 삭제된 항목이에요", "⚠️")
    st.session_state.editing_id = None
    st.session_state.edit_error = None


def cancel_edit() -> None:
    st.session_state.editing_id = None
    st.session_state.edit_error = None


def submit_add() -> None:
    """추가 폼 제출 콜백. 화면을 그리기 전에 실행되므로 진행 현황에 바로 반영된다."""
    name = st.session_state["new_name"]
    added = add_item(name, int(st.session_state["new_qty"]))
    st.session_state.add_error = None if added else "품목명을 입력해 주세요."
    if added:
        notify(f"'{name.strip()}' 추가했어요", "🛒")


def on_delete(item_id: str) -> None:
    removed = delete_item(item_id)
    if removed is not None:
        notify(f"'{removed['name']}' 삭제했어요", "🗑️")


def on_delete_checked() -> None:
    count = delete_checked_items()
    if count:
        notify(f"구매 완료 항목 {count}개를 삭제했어요", "🧹")


def on_delete_all() -> None:
    delete_all_items()
    notify("모든 항목을 삭제했어요", "🗑️")


def set_confirm_delete_all(value: bool) -> None:
    st.session_state.confirm_delete_all = value


# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
def escape_markdown(text: str) -> str:
    """사용자 입력이 마크다운 서식이나 링크로 해석되지 않도록 바꾼다."""
    text = re.sub(r"([\\`*_{}\[\]()#+\-.!|~<>$:@])", r"\\\1", text)
    # 'http://', 'www.', 'a@b.com' 같은 자동 링크는 이스케이프로 막히지 않으므로
    # ':' 와 '@' 뒤, '.' 앞에 보이지 않는 문자를 넣어 링크 패턴을 끊는다.
    return (
        text.replace("\\:", "\\:" + WORD_JOINER)
        .replace("\\@", "\\@" + WORD_JOINER)
        .replace("\\.", WORD_JOINER + "\\.")
    )


CUSTOM_CSS = """
<style>
/* 항목 행·하단 버튼은 모바일(좁은 화면)에서도 열이 세로로 쌓이지 않게 한 줄 유지 */
[class*="st-key-row_"] [data-testid="stHorizontalBlock"],
.st-key-bulk_actions [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.25rem;
}
[class*="st-key-row_"] [data-testid="stColumn"],
.st-key-bulk_actions [data-testid="stColumn"] {
    min-width: 0 !important;
}
/* 긴 품목명은 잘리지 않고 줄바꿈 */
[class*="st-key-row_"] [data-testid="stCheckbox"] label,
[class*="st-key-row_"] [data-testid="stCheckbox"] label * {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    overflow-wrap: anywhere;
}
/* 수정·삭제 아이콘 버튼의 터치 영역 확보 (최소 40px) */
[class*="st-key-row_"] [class*="st-key-edit_"] button,
[class*="st-key-row_"] [class*="st-key-delete_"] button {
    min-width: 40px;
    min-height: 40px;
    justify-content: center;
}
/* 입력창의 영어 안내("Press Enter to submit form")는 숨기고 한국어 안내로 대체 */
[data-testid="InputInstructions"] {
    display: none;
}
/* 알림: 오른쪽 위에 잠깐 떴다가 사라짐 */
.notice {
    position: fixed;
    top: 4rem;
    right: 1rem;
    z-index: 1000;
    max-width: min(360px, calc(100vw - 2rem));
    padding: 0.75rem 1rem;
    background: #FFFFFF;
    border: 1px solid #E0E0E0;
    border-left: 4px solid #2E7D32;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    overflow-wrap: anywhere;
    pointer-events: none;
    animation: notice-fade 3.5s ease forwards;
}
@keyframes notice-fade {
    0% { opacity: 0; transform: translateY(-8px); }
    8% { opacity: 1; transform: none; }
    85% { opacity: 1; }
    100% { opacity: 0; visibility: hidden; }
}
/* 상단 빈 여백 축소 */
[data-testid="stMainBlockContainer"] {
    padding-top: 2.5rem;
}
/* 항목 카드 안쪽 여백 축소 */
[class*="st-key-row_"] {
    padding: 0.35rem 0.75rem !important;
}
/* 수량 배지 */
.qty-badge {
    display: inline-block;
    padding: 0.05rem 0.5rem;
    border-radius: 999px;
    background: #E8F5E9;
    color: #2E7D32;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
}
/* 전체 삭제: 위험 동작임을 빨간색으로 표시 */
.st-key-delete_all button,
.st-key-confirm_delete_all_yes button {
    color: #D32F2F !important;
    border-color: #D32F2F !important;
}
.st-key-confirm_delete_all_yes button {
    background: #D32F2F !important;
    color: #FFFFFF !important;
}
</style>
"""


def render_header() -> None:
    """제목과 진행 현황 (F-07)."""
    st.title("🛒 쇼핑 리스트")
    items = get_items()
    total = len(items)
    done = sum(item["checked"] for item in items)
    ratio = done / total if total else 0.0
    st.progress(ratio, text=f"**{done} / {total}** 구매 완료 ({ratio:.0%})")
    if total and done == total:
        st.success("모두 구매했어요! 장보기 끝 🎉")


def render_add_form() -> None:
    """항목 추가 폼 (F-01 ~ F-04)."""
    with st.form("add_form", clear_on_submit=True, border=True):
        name_col, qty_col = st.columns([3, 1.3])
        name_col.text_input(
            "품목명", key="new_name", max_chars=MAX_NAME_LENGTH, placeholder="예: 우유"
        )
        qty_col.number_input(
            "수량", key="new_qty", min_value=1, max_value=MAX_QUANTITY, value=1, step=1,
            help=f"1부터 {MAX_QUANTITY}까지 입력할 수 있어요.",
        )
        st.caption(
            f"Enter 키로도 추가할 수 있어요 · 품목명 최대 {MAX_NAME_LENGTH}자 · "
            f"수량 1~{MAX_QUANTITY} (범위를 벗어나면 추가되지 않아요)"
        )
        st.form_submit_button(
            "추가", type="primary", icon=":material/add:", on_click=submit_add, use_container_width=True
        )

    if st.session_state.add_error:
        st.warning(st.session_state.add_error, icon="⚠️")
        st.session_state.add_error = None


def render_item_row(item: dict) -> None:
    """항목 한 줄(카드): 보기 모드 또는 수정 모드."""
    item_id = item["id"]

    with st.container(border=True, key=f"row_{item_id}"):
        if st.session_state.editing_id == item_id:
            name_col, qty_col = st.columns([3, 1.3])
            name_col.text_input("품목명", key=f"edit_name_{item_id}", max_chars=MAX_NAME_LENGTH)
            qty_col.number_input(
                "수량", key=f"edit_qty_{item_id}", min_value=1, max_value=MAX_QUANTITY, step=1,
                help=f"1부터 {MAX_QUANTITY}까지 입력할 수 있어요.",
            )
            save_col, cancel_col = st.columns(2)
            save_col.button(
                "저장", key=f"save_{item_id}", type="primary", on_click=save_edit,
                args=(item_id,), use_container_width=True,
            )
            cancel_col.button(
                "취소", key=f"cancel_{item_id}", on_click=cancel_edit, use_container_width=True
            )
            if st.session_state.edit_error:
                st.warning(st.session_state.edit_error, icon="⚠️")
            return

        name = escape_markdown(item["name"])
        label = f":gray[~~{name}~~]" if item["checked"] else name  # F-06: 체크 시 취소선 + 회색

        # 저장된 값으로 체크박스를 맞춘다 (다른 사람이 바꾼 체크 상태도 반영).
        st.session_state[f"check_{item_id}"] = item["checked"]

        check_col, qty_col, edit_col, delete_col = st.columns(
            [0.56, 0.14, 0.15, 0.15], vertical_alignment="center"
        )
        check_col.checkbox(label, key=f"check_{item_id}", on_change=toggle_item, args=(item_id,))
        qty_col.markdown(f'<span class="qty-badge">x{item["quantity"]}</span>', unsafe_allow_html=True)
        edit_col.button(
            "✏️", key=f"edit_{item_id}", type="tertiary", help="수정",
            on_click=start_edit, args=(item_id,),
        )
        delete_col.button(
            "🗑️", key=f"delete_{item_id}", type="tertiary", help="삭제",
            on_click=on_delete, args=(item_id,),
        )


def render_list() -> None:
    """필터 + 항목 목록 (F-05, F-08, F-09)."""
    items = get_items()
    if not items:
        st.info("리스트가 비어 있습니다. 위에서 살 물건을 추가해 보세요.", icon="📝")
        return

    counts = {
        FILTER_ALL: len(items),
        FILTER_TODO: sum(not item["checked"] for item in items),
        FILTER_DONE: sum(item["checked"] for item in items),
    }
    # 선택지 문구에 개수를 넣으면 개수가 바뀔 때 라디오 선택 표시가 풀리므로(Streamlit 동작),
    # 선택지는 고정하고 개수는 옆에 따로 표시한다.
    filter_col, count_col = st.columns([3, 2], vertical_alignment="center")
    selected = filter_col.radio(
        "필터", list(counts), horizontal=True, key="filter", label_visibility="collapsed"
    )
    count_col.caption(f"미구매 {counts[FILTER_TODO]} · 구매 완료 {counts[FILTER_DONE]}")
    if selected == FILTER_TODO:
        visible = [item for item in items if not item["checked"]]
    elif selected == FILTER_DONE:
        visible = [item for item in items if item["checked"]]
    else:
        visible = items

    if not visible:
        st.caption(f"'{selected}' 항목이 없습니다.")
    # 미구매 항목이 위, 구매 완료 항목이 아래 (같은 그룹 안에서는 추가한 순서 유지)
    for item in sorted(visible, key=lambda item: item["checked"]):
        render_item_row(item)


def render_bulk_actions() -> None:
    """체크된 항목 일괄 삭제 (F-14), 전체 삭제 (F-15)."""
    items = get_items()
    if not items:
        return

    st.divider()
    has_checked = any(item["checked"] for item in items)
    with st.container(key="bulk_actions"):
        left, right = st.columns(2)
        left.button(
            "체크된 항목 삭제", icon=":material/done_all:", on_click=on_delete_checked,
            disabled=not has_checked, use_container_width=True,
        )
        right.button(
            "전체 삭제", key="delete_all", icon=":material/delete_forever:",
            on_click=set_confirm_delete_all, args=(True,), use_container_width=True,
        )

    if st.session_state.confirm_delete_all:
        with st.container(border=True):
            st.warning(f"항목 {len(items)}개를 모두 삭제할까요? 되돌릴 수 없습니다.", icon="⚠️")
            yes_col, no_col = st.columns(2)
            yes_col.button(
                "모두 삭제", key="confirm_delete_all_yes", on_click=on_delete_all,
                use_container_width=True,
            )
            no_col.button(
                "취소", key="confirm_delete_all_no", on_click=set_confirm_delete_all,
                args=(False,), use_container_width=True,
            )


def render_notices() -> str:
    """예약된 알림을 HTML로 만든다.

    st.toast는 앞 알림이 떠 있는 동안 다음 실행의 알림을 띄우지 않아(Streamlit 동작)
    연속 추가 시 알림이 빠지므로, CSS 애니메이션으로 사라지는 알림을 직접 그린다.
    매번 다른 data-id를 넣어 같은 문구가 연달아 와도 새 요소로 그려지게 한다.
    """
    notices, st.session_state.notices = st.session_state.notices, []
    if not notices:
        return ""
    body = "<br>".join(html.escape(notice) for notice in notices)
    return f'<div class="notice" role="status" data-id="{uuid.uuid4().hex}">{body}</div>'


def main() -> None:
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    init_state()
    # CSS와 알림을 한 요소에 담아, 알림 유무에 따라 화면 간격이 달라지지 않게 한다.
    st.markdown(CUSTOM_CSS + render_notices(), unsafe_allow_html=True)

    render_header()
    render_add_form()
    render_list()
    render_bulk_actions()


main()
