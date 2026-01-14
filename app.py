import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
import streamlit as st


# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="인천제2교회 성경읽기표", layout="wide")

YOUTUBE_URL = "https://www.youtube.com/@%EC%9D%B8%EC%B2%9C%EC%A0%9C2%EA%B5%90%ED%9A%8C-che2"
LOCAL_BIBLE_BOOKS_DIR = Path("bible_books_json")

BIBLE_BOOKS_DIR = st.secrets.get("GITHUB_BIBLE_BOOKS_DIR", "bible_books_json")
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

BOOKS = {
    "창세기": "gen", "출애굽기": "exo", "레위기": "lev", "민수기": "num", "신명기": "deu",
    "여호수아": "jos", "사사기": "jdg", "룻기": "rut", "사무엘상": "1sa", "사무엘하": "2sa",
    "열왕기상": "1ki", "열왕기하": "2ki", "역대상": "1ch", "역대하": "2ch", "에스라": "ezr",
    "느헤미야": "neh", "에스더": "est", "욥기": "job", "시편": "psa", "잠언": "pro",
    "전도서": "ecc", "아가": "sng", "이사야": "isa", "예레미야": "jer", "예레미야애가": "lam",
    "에스겔": "ezk", "다니엘": "dan", "호세아": "hos", "요엘": "jol", "아모스": "amo",
    "오바댜": "oba", "요나": "jnh", "미가": "mic", "나훔": "nam", "하박국": "hab",
    "스바냐": "zep", "학개": "hag", "스가랴": "zec", "말라기": "mal",
    "마태복음": "mat", "마가복음": "mrk", "누가복음": "luk", "요한복음": "jhn", "사도행전": "act",
    "로마서": "rom", "고린도전서": "1co", "고린도후서": "2co", "갈라디아서": "gal", "에베소서": "eph",
    "빌립보서": "php", "골로새서": "col", "데살로니가전서": "1th", "데살로니가후서": "2th",
    "디모데전서": "1ti", "디모데후서": "2ti", "디도서": "tit", "빌레몬서": "phm",
    "히브리서": "heb", "야고보서": "jas", "베드로전서": "1pe", "베드로후서": "2pe",
    "요한1서": "1jn", "요한2서": "2jn", "요한3서": "3jn", "유다서": "jud", "요한계시록": "rev",
}

CHAPTER_COUNT = {
    "창세기":50,"출애굽기":40,"레위기":27,"민수기":36,"신명기":34,"여호수아":24,"사사기":21,"룻기":4,"사무엘상":31,"사무엘하":24,
    "열왕기상":22,"열왕기하":25,"역대상":29,"역대하":36,"에스라":10,"느헤미야":13,"에스더":10,"욥기":42,"시편":150,"잠언":31,
    "전도서":12,"아가":8,"이사야":66,"예레미야":52,"예레미야애가":5,"에스겔":48,"다니엘":12,"호세아":14,"요엘":3,"아모스":9,
    "오바댜":1,"요나":4,"미가":7,"나훔":3,"하박국":3,"스바냐":3,"학개":2,"스가랴":14,"말라기":4,
    "마태복음":28,"마가복음":16,"누가복음":24,"요한복음":21,"사도행전":28,"로마서":16,"고린도전서":16,"고린도후서":13,"갈라디아서":6,"에베소서":6,
    "빌립보서":4,"골로새서":4,"데살로니가전서":5,"데살로니가후서":3,"디모데전서":6,"디모데후서":4,"디도서":3,"빌레몬서":1,"히브리서":13,"야고보서":5,
    "베드로전서":5,"베드로후서":3,"요한1서":5,"요한2서":1,"요한3서":1,"유다서":1,"요한계시록":22
}
BOOK_ORDER = list(CHAPTER_COUNT.keys())

st.title("성경읽기표")
st.caption("모바일 최적: 읽기표 화면 ↔ 본문 화면 전환")

# =========================================================
# 세션 상태
# =========================================================
if "checked" not in st.session_state:
    st.session_state.checked = {}  # { "gen:001": True, ... }
if "view" not in st.session_state:
    st.session_state.view = "plan"  # "plan" | "read"
if "selected_day" not in st.session_state:
    st.session_state.selected_day = None
if "selected_chapter" not in st.session_state:
    st.session_state.selected_chapter = None  # (book, ch)

def key_for(book_name: str, chapter: int) -> str:
    return f"{BOOKS.get(book_name, book_name)}:{chapter:03d}"

# =========================================================
# 스케줄
# =========================================================
@dataclass
class ReadingDay:
    d: date
    is_sunday: bool
    chapters: List[Tuple[str, int]]
    label: str

def iter_bible_chapters() -> List[Tuple[str, int]]:
    out = []
    for book in BOOK_ORDER:
        for ch in range(1, CHAPTER_COUNT[book] + 1):
            out.append((book, ch))
    return out

ALL_CHAPTERS = iter_bible_chapters()

def build_schedule(year: int) -> List[ReadingDay]:
    start = date(year, 2, 1)
    end = date(year, 12, 31)
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    idx = 0
    schedule = []
    for d in days:
        if d.weekday() == 6:
            schedule.append(ReadingDay(d=d, is_sunday=True, chapters=[], label="주일: 영상 시청"))
            continue

        todays = []
        for _ in range(5):
            if idx < len(ALL_CHAPTERS):
                todays.append(ALL_CHAPTERS[idx])
                idx += 1

        if todays:
            b1, c1 = todays[0]
            b2, c2 = todays[-1]
            label = f"{b1} {c1}–{c2}장" if b1 == b2 else f"{b1} {c1}장 ~ {b2} {c2}장"
        else:
            label = "완독 이후(읽기 없음)"

        schedule.append(ReadingDay(d=d, is_sunday=False, chapters=todays, label=label))
    return schedule

# =========================================================
# 본문 로드 (한글 파일명 우선)
# =========================================================
def github_raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"

@st.cache_data(show_spinner=False)
def load_book_json_local(book_name: str) -> Optional[Dict[str, Any]]:
    book_code = BOOKS.get(book_name)
    candidates = [LOCAL_BIBLE_BOOKS_DIR / f"{book_name}.json"]
    if book_code:
        candidates.append(LOCAL_BIBLE_BOOKS_DIR / f"{book_code}.json")
    for fp in candidates:
        if fp.exists():
            try:
                return json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None

@st.cache_data(show_spinner=False)
def load_book_json_github(book_name: str) -> Optional[Dict[str, Any]]:
    if not (GITHUB_OWNER and GITHUB_REPO):
        return None
    book_code = BOOKS.get(book_name)
    candidates = [f"{BIBLE_BOOKS_DIR}/{book_name}.json"]
    if book_code:
        candidates.append(f"{BIBLE_BOOKS_DIR}/{book_code}.json")
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    for rel in candidates:
        try:
            r = requests.get(github_raw_url(rel), headers=headers, timeout=25)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None

def sort_verse_items(d: Dict[Any, Any]) -> List[Tuple[str, Any]]:
    items = list(d.items())
    def to_int(x):
        s = re.sub(r"\D", "", str(x))
        return int(s) if s else 0
    try:
        items.sort(key=lambda kv: to_int(kv[0]))
    except Exception:
        pass
    return items

def chapter_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        lines = []
        for i, v in enumerate(node, start=1):
            if isinstance(v, str):
                lines.append(v)
            elif isinstance(v, dict):
                vv = v.get("v") or v.get("verse") or v.get("no") or i
                tt = v.get("t") or v.get("text") or v.get("value") or json.dumps(v, ensure_ascii=False)
                lines.append(f"{vv}. {tt}")
            else:
                lines.append(str(v))
        return "\n".join(lines)
    if isinstance(node, dict):
        if "text" in node and isinstance(node["text"], str):
            return node["text"]
        if "verses" in node:
            return chapter_to_text(node["verses"])
        items = sort_verse_items(node)
        return "\n".join([f"{k}. {v}" for k, v in items])
    return str(node)

def find_chapter_anywhere(obj: Any, chapter: int) -> Optional[Any]:
    ch_str = str(chapter)
    if isinstance(obj, list):
        idx = chapter - 1
        if 0 <= idx < len(obj):
            return obj[idx]
        for v in obj:
            found = find_chapter_anywhere(v, chapter)
            if found is not None:
                return found
        return None
    if isinstance(obj, dict):
        for k in [ch_str, chapter, f"chapter{ch_str}", f"ch{ch_str}", f"{ch_str}장"]:
            if k in obj:
                return obj[k]
        for wrapper in ["chapters", "chapter", "data", "items", "content", "book"]:
            if wrapper in obj:
                found = find_chapter_anywhere(obj[wrapper], chapter)
                if found is not None:
                    return found
        for _, v in obj.items():
            found = find_chapter_anywhere(v, chapter)
            if found is not None:
                return found
    return None

def get_chapter_node(book_json: Dict[str, Any], chapter: int) -> Optional[Any]:
    ch_key = str(chapter)
    for root, ck in [("chapters", ch_key), (None, ch_key), ("data", ch_key)]:
        try:
            return book_json[ck] if root is None else book_json[root][ck]
        except Exception:
            pass
    return find_chapter_anywhere(book_json, chapter)

def load_chapter_text(book_name: str, chapter: int) -> Optional[str]:
    bj = load_book_json_local(book_name)
    if bj is None:
        bj = load_book_json_github(book_name)
    if bj is None:
        return None
    node = get_chapter_node(bj, chapter)
    if node is None:
        return None
    txt = chapter_to_text(node)
    return txt if txt.strip() else None

# =========================================================
# View: PLAN (읽기표 화면)
# =========================================================
def render_plan_view():
    today = date.today()
    year = today.year
    schedule = build_schedule(year)

    min_day = date(year, 2, 1)
    max_day = date(year, 12, 31)
    default_day = today if (min_day <= today <= max_day) else min_day

    if st.session_state.selected_day:
        default_day = st.session_state.selected_day

    st.info("📌 날짜를 선택하면 ‘오늘 분량’이 보입니다. 읽을 장에서 **📖 읽기**를 누르면 본문 화면으로 이동합니다.")

    sel_day = st.date_input("날짜 선택", value=default_day, min_value=min_day, max_value=max_day)
    st.session_state.selected_day = sel_day

    day_obj = next((x for x in schedule if x.d == sel_day), None)
    if not day_obj:
        st.error("선택한 날짜 데이터를 찾지 못했습니다.")
        return

    weekday_kor = ["월","화","수","목","금","토","일"][sel_day.weekday()]
    st.markdown(f"### {sel_day.isoformat()} ({weekday_kor})")

    if day_obj.is_sunday:
        st.markdown("**오늘 읽기:** 주일은 영상 시청")
        st.link_button("▶️ 유튜브 시청하기", YOUTUBE_URL)
        return

    st.markdown(f"**오늘 읽기:** {day_obj.label}")

    # 모바일 최적: 각 장은 세로로 한 줄씩 (체크 + 읽기 버튼)
    for (book, ch) in day_obj.chapters:
        k = key_for(book, ch)
        row = st.columns([2.0, 1.2])
        row[0].checkbox(
            f"{book} {ch}장",
            value=bool(st.session_state.checked.get(k, False)),
            key=f"chk_{sel_day}_{k}"
        )
        if row[1].button("📖 읽기", key=f"read_{sel_day}_{k}", use_container_width=True):
            st.session_state.selected_chapter = (book, ch)
            st.session_state.view = "read"
            st.rerun()

    # 진행률은 plan 화면 맨 아래에만 간단히
    total_ch = len(ALL_CHAPTERS)
    done_ch = sum(1 for v in st.session_state.checked.values() if v)
    st.caption(f"진행 현황: {done_ch}/{total_ch}장")

# =========================================================
# View: READ (본문 화면)
# =========================================================
def render_read_view():
    # 상단 "뒤로가기"
    top = st.columns([1.0, 2.0])
    if top[0].button("← 뒤로가기", use_container_width=True):
        st.session_state.view = "plan"
        st.rerun()

    sel = st.session_state.get("selected_chapter")
    if not sel:
        st.session_state.view = "plan"
        st.rerun()
        return

    book, ch = sel
    st.markdown(f"## {book} {ch}장")

    with st.spinner("본문을 불러오는 중..."):
        txt = load_chapter_text(book, ch)

    if not txt:
        st.warning(f"{book} {ch}장 본문을 불러오지 못했습니다. (JSON 구조 확인 필요)")
        return

    # 모바일에서 text_area는 스크롤이 길어져서 불편할 수 있어
    # 본문은 markdown으로 출력(절 번호가 있으면 그대로 보이게)
    st.markdown("----")
    st.markdown(
        "<div style='white-space:pre-wrap; line-height:1.8; font-size:1.05rem;'>"
        + (txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        + "</div>",
        unsafe_allow_html=True
    )

# =========================================================
# 렌더링
# =========================================================
if st.session_state.view == "read":
    render_read_view()
else:
    render_plan_view()
