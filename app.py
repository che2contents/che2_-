import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="인천제2교회 성경읽기표", layout="wide")

YOUTUBE_URL = "https://www.youtube.com/@%EC%9D%B8%EC%B2%9C%EC%A0%9C2%EA%B5%90%ED%9A%8C-che2"

# ✅ repo 안에 포함된 bible_books_json 폴더를 기본으로 사용
# (로컬 파일이 없을 때만 GitHub Raw로 fallback)
LOCAL_BIBLE_BOOKS_DIR = Path("bible_books_json")

# (선택) GitHub Raw fallback (public repo면 토큰 없어도 됨)
BIBLE_BOOKS_DIR = st.secrets.get("GITHUB_BIBLE_BOOKS_DIR", "bible_books_json")
GITHUB_OWNER = st.secrets.get("GITHUB_OWNER", "")
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")

# 책 코드 매핑
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

# =========================================================
# 스타일(명조) + 배너
# =========================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Nanum Myeongjo', serif !important; }
    .banner-wrap img { border-radius: 14px; }
    .muted { color:#666; font-size:0.95rem; }
    .card { border:1px solid #e6e6e6; border-radius:14px; padding:14px; background:#fff; margin-bottom:12px; }
    .pill { display:inline-block; padding:4px 10px; border-radius:999px; border:1px solid #ddd; font-size:0.9rem; margin-right:6px; background:#fafafa; }
    </style>
    """,
    unsafe_allow_html=True
)

# 배너 (assets/banner.jpg)
try:
    st.markdown('<div class="banner-wrap">', unsafe_allow_html=True)
    st.image("assets/banner.jpg", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    st.warning("1) assets/banner.jpg 배너 파일을 repo에 추가해 주세요.")

st.title("성경읽기표 (2월~12월 · 월~토 5장 · 주일 영상)")
st.caption("프로토타입: 코드 입력/백업 기능 숨김 · 바로 사용 가능")

st.info(
    "📌 사용 방법\n"
    "- 날짜를 선택하면 그날 읽을 5장이 자동으로 나옵니다.\n"
    "- [📖 성경 읽기] 버튼을 누르면 본문이 로드됩니다.\n"
    "- 주일은 유튜브 영상만 시청합니다."
)

# =========================================================
# 진행 상태(프로토타입: 세션에만 저장)
# =========================================================
if "checked" not in st.session_state:
    st.session_state.checked: Dict[str, bool] = {}  # {"gen:001": True, ...}
if "selected_reading" not in st.session_state:
    st.session_state.selected_reading: Optional[List[Tuple[str, int]]] = None

def key_for(book_name: str, chapter: int) -> str:
    return f"{BOOKS.get(book_name, book_name)}:{chapter:03d}"

# =========================================================
# 2월~12월 스케줄 생성 (주일 제외, 월~토 하루 5장)
# =========================================================
@dataclass
class ReadingDay:
    d: date
    is_sunday: bool
    chapters: List[Tuple[str, int]]
    label: str

def iter_bible_chapters() -> List[Tuple[str, int]]:
    out: List[Tuple[str, int]] = []
    for book in BOOK_ORDER:
        for ch in range(1, CHAPTER_COUNT[book] + 1):
            out.append((book, ch))
    return out

ALL_CHAPTERS = iter_bible_chapters()  # 총 1189장

def build_schedule(year: int) -> List[ReadingDay]:
    start = date(year, 2, 1)
    end = date(year, 12, 31)

    days: List[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    idx = 0
    schedule: List[ReadingDay] = []

    for d in days:
        is_sun = (d.weekday() == 6)  # 일요일
        if is_sun:
            schedule.append(ReadingDay(d=d, is_sunday=True, chapters=[], label="주일: 영상 시청"))
            continue

        todays: List[Tuple[str, int]] = []
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
# 본문 로드 (1) 로컬 파일 우선 (2) GitHub Raw fallback
# =========================================================
@st.cache_data(show_spinner=False)
def load_book_json_local(book_code: str) -> Optional[Dict[str, Any]]:
    fp = LOCAL_BIBLE_BOOKS_DIR / f"{book_code}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None

def github_raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"

@st.cache_data(show_spinner=False)
def load_book_json_github(book_code: str) -> Optional[Dict[str, Any]]:
    if not (GITHUB_OWNER and GITHUB_REPO):
        return None
    url = github_raw_url(f"{BIBLE_BOOKS_DIR}/{book_code}.json")
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

def sort_verse_items(d: Dict[Any, Any]) -> List[Tuple[str, Any]]:
    items = list(d.items())
    def to_int(x):
        s = re.sub(r"\\D", "", str(x))
        return int(s) if s else 0
    try:
        items.sort(key=lambda kv: to_int(kv[0]))
    except Exception:
        pass
    return items

def get_chapter_node(book_json: Dict[str, Any], chapter: int) -> Optional[Any]:
    ch_key = str(chapter)
    candidates = [
        ("chapters", ch_key),
        (None, ch_key),
        ("data", ch_key),
    ]
    for root, ck in candidates:
        try:
            return book_json[ck] if root is None else book_json[root][ck]
        except Exception:
            continue
    return None

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
                vv = v.get("v") or v.get("verse") or i
                tt = v.get("t") or v.get("text") or json.dumps(v, ensure_ascii=False)
                lines.append(f"{vv}. {tt}")
            else:
                lines.append(str(v))
        return "\n".join(lines)
    if isinstance(node, dict):
        if "text" in node and isinstance(node["text"], str):
            return node["text"]
        if "verses" in node and isinstance(node["verses"], (dict, list, str)):
            return chapter_to_text(node["verses"])
        items = sort_verse_items(node)
        return "\n".join([f"{k}. {v}" for k, v in items])
    return str(node)

def load_chapter_text(book_name: str, chapter: int) -> Optional[str]:
    book_code = BOOKS.get(book_name)
    if not book_code:
        return None

    # 1) 로컬
    bj = load_book_json_local(book_code)
    # 2) GitHub fallback
    if bj is None:
        bj = load_book_json_github(book_code)
    if bj is None:
        return None

    node = get_chapter_node(bj, chapter)
    if node is None:
        return None
    text = chapter_to_text(node)
    return text if text.strip() else None

# =========================================================
# 메인 UI: 바로 읽기표 사용
# =========================================================
today = date.today()
year = st.sidebar.selectbox("연도", [today.year - 1, today.year, today.year + 1], index=1)

schedule = build_schedule(year)
min_day = date(year, 2, 1)
max_day = date(year, 12, 31)
default_day = today if (min_day <= today <= max_day) else min_day

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("주일 영상")
st.link_button("▶️ 주일 유튜브 시청하기", YOUTUBE_URL)
st.markdown("</div>", unsafe_allow_html=True)

sel_day = st.date_input("날짜 선택", value=default_day, min_value=min_day, max_value=max_day)
day_obj = next((x for x in schedule if x.d == sel_day), None)
if not day_obj:
    st.error("선택한 날짜 데이터를 찾지 못했습니다.")
    st.stop()

# 오늘 카드
weekday_kor = ["월", "화", "수", "목", "금", "토", "일"][sel_day.weekday()]
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"## {sel_day.isoformat()} ({weekday_kor})")

if day_obj.is_sunday:
    st.markdown("**주일:** 성경 읽기 없음 · 영상만 시청합니다.")
    st.link_button("▶️ 유튜브 바로가기", YOUTUBE_URL)
    st.session_state.selected_reading = None
else:
    st.markdown(f"**오늘 읽기:** {day_obj.label}")

    # 장별 체크(5장)
    cols = st.columns(5)
    for i, (book, ch) in enumerate(day_obj.chapters):
        k = key_for(book, ch)
        st.session_state.checked[k] = cols[i].checkbox(
            f"{book} {ch}장",
            value=bool(st.session_state.checked.get(k, False)),
            key=f"chk_{sel_day}_{k}",
        )

    if st.button("📖 성경 읽기 (본문 로드)", use_container_width=True):
        st.session_state.selected_reading = day_obj.chapters

st.markdown("</div>", unsafe_allow_html=True)

# 진행률(세션 기준)
total_ch = len(ALL_CHAPTERS)
done_ch = sum(1 for v in st.session_state.checked.values() if v)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"### 진행 현황: {done_ch} / {total_ch}장")
st.progress(min(1.0, done_ch / total_ch))
st.markdown("</div>", unsafe_allow_html=True)

# 본문 영역
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("본문")

sel_reading = st.session_state.get("selected_reading")
if not sel_reading:
    st.markdown('<div class="muted">위에서 <b>📖 성경 읽기</b> 버튼을 누르면, 오늘 분량(5장)이 여기에 표시됩니다.</div>', unsafe_allow_html=True)
else:
    # 로컬 폴더 체크 안내
    if not LOCAL_BIBLE_BOOKS_DIR.exists():
        st.warning("bible_books_json 폴더가 repo 루트에 있어야 합니다. (예: bible_books_json/gen.json)")
    with st.spinner("bible_books_json에서 본문을 불러오는 중..."):
        for (book, ch) in sel_reading:
            st.markdown(f"### {book} {ch}장")
            text = load_chapter_text(book, ch)
            if not text:
                st.warning(f"{book} {ch}장 본문을 불러오지 못했습니다. (로컬 파일/JSON 구조/경로 확인 필요)")
            else:
                st.text_area(f"{book} {ch}장", value=text, height=260)

st.markdown("</div>", unsafe_allow_html=True)
