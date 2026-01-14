import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import streamlit as st

# =========================================================
# 기본 설정
# =========================================================
st.set_page_config(page_title="인천제2교회 성경읽기표", layout="wide")

YOUTUBE_URL = "https://www.youtube.com/@%EC%9D%B8%EC%B2%9C%EC%A0%9C2%EA%B5%90%ED%9A%8C-che2"

# 로컬 JSON 폴더
LOCAL_BIBLE_BOOKS_DIR = Path("bible_books_json")

# (선택) GitHub Raw fallback
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
    </style>
    """,
    unsafe_allow_html=True
)

try:
    st.markdown('<div class="banner-wrap">', unsafe_allow_html=True)
    st.image("assets/banner.jpg", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    st.warning("assets/banner.jpg 배너 파일을 repo에 추가해 주세요.")

st.title("성경읽기표 (2월~12월 · 월~토 5장 · 주일 영상)")
st.caption("프로토타입: 코드/백업 숨김 · 바로 사용")

# =========================================================
# 세션 상태(프로토타입)
# =========================================================
if "checked" not in st.session_state:
    st.session_state.checked = {}
if "selected_reading" not in st.session_state:
    st.session_state.selected_reading = None

def key_for(book_name: str, chapter: int) -> str:
    return f"{BOOKS.get(book_name, book_name)}:{chapter:03d}"

# =========================================================
# 스케줄 (2월~12월 / 월~토 5장 / 주일 영상)
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

ALL_CHAPTERS = iter_bible_chapters()

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
        is_sun = (d.weekday() == 6)
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
# 본문 로드: 로컬 우선, 없으면 GitHub Raw fallback
# + JSON 구조가 달라도 장을 찾아내는 "범용 탐색" 추가
# =========================================================
def github_raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"

@st.cache_data(show_spinner=False)
def load_book_json_local(book_code: str) -> Optional[Dict[str, Any]]:
    fp = LOCAL_BIBLE_BOOKS_DIR / f"{book_code}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def load_book_json_github(book_code: str) -> Optional[Dict[str, Any]]:
    if not (GITHUB_OWNER and GITHUB_REPO):
        return None
    url = github_raw_url(f"{BIBLE_BOOKS_DIR}/{book_code}.json")
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        r = requests.get(url, headers=headers, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
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
        # list of verses / list of dicts / list of strings
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
        # common wrappers
        if "text" in node and isinstance(node["text"], str):
            return node["text"]
        if "verses" in node:
            return chapter_to_text(node["verses"])
        if "verse" in node and isinstance(node["verse"], (dict, list, str)):
            return chapter_to_text(node["verse"])

        # dict of verses
        items = sort_verse_items(node)
        return "\n".join([f"{k}. {v}" for k, v in items])

    return str(node)

def find_chapter_anywhere(obj: Any, chapter: int) -> Optional[Any]:
    """
    JSON 구조가 제각각인 경우를 대비한 범용 탐색.
    - dict에서 key가 "1", 1, "chapter1" 등으로 존재하는 경우
    - list에서 index = chapter-1 로 존재하는 경우
    """
    ch_str = str(chapter)

    # 1) list라면 chapter-1 인덱스 후보
    if isinstance(obj, list):
        idx = chapter - 1
        if 0 <= idx < len(obj):
            # 이게 "장" 단위일 가능성이 높음
            return obj[idx]
        # 내부 탐색도 수행
        for v in obj:
            found = find_chapter_anywhere(v, chapter)
            if found is not None:
                return found
        return None

    # 2) dict라면 직접 키 매칭 + 내부 탐색
    if isinstance(obj, dict):
        # 직접 키 후보들
        direct_keys = [
            ch_str, chapter,
            f"ch{ch_str}", f"chapter{ch_str}", f"chap{ch_str}",
            f"{ch_str}장", f"{ch_str}장본문"
        ]
        for k in direct_keys:
            if k in obj:
                return obj[k]

        # 흔한 래퍼 키 우선 탐색
        for wrapper in ["chapters", "chapter", "data", "items", "content", "book"]:
            if wrapper in obj:
                found = find_chapter_anywhere(obj[wrapper], chapter)
                if found is not None:
                    return found

        # 전체 key/value 순회 탐색
        for _, v in obj.items():
            found = find_chapter_anywhere(v, chapter)
            if found is not None:
                return found
        return None

    return None

def get_chapter_node(book_json: Dict[str, Any], chapter: int) -> Optional[Any]:
    """
    빠른 경로(일반 구조) 먼저 시도 후, 실패하면 범용 탐색.
    """
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
            pass

    # fallback: 어디든 찾아보기
    return find_chapter_anywhere(book_json, chapter)

def load_chapter_text(book_name: str, chapter: int) -> Tuple[Optional[str], str]:
    """
    returns (text, source)
    source: "local" | "github" | "none"
    """
    book_code = BOOKS.get(book_name)
    if not book_code:
        return None, "none"

    bj = load_book_json_local(book_code)
    source = "local" if bj is not None else "none"
    if bj is None:
        bj = load_book_json_github(book_code)
        source = "github" if bj is not None else "none"
    if bj is None:
        return None, "none"

    node = get_chapter_node(bj, chapter)
    if node is None:
        return None, source

    text = chapter_to_text(node)
    return (text if text.strip() else None), source

# =========================================================
# UI
# =========================================================
today = date.today()
year = today.year  # ✅ 연도 선택 UI 제거, 올해로 고정
schedule = build_schedule(year)

min_day = date(year, 2, 1)
max_day = date(year, 12, 31)
default_day = today if (min_day <= today <= max_day) else min_day

sel_day = st.date_input("날짜 선택", value=default_day, min_value=min_day, max_value=max_day)
day_obj = next((x for x in schedule if x.d == sel_day), None)
if not day_obj:
    st.error("선택한 날짜 데이터를 찾지 못했습니다.")
    st.stop()

weekday_kor = ["월", "화", "수", "목", "금", "토", "일"][sel_day.weekday()]

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"## {sel_day.isoformat()} ({weekday_kor})")

if day_obj.is_sunday:
    st.markdown("**주일:** 성경 읽기 대신 영상 시청입니다.")
    st.link_button("▶️ 유튜브 시청하기", YOUTUBE_URL)
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

# 진행률(세션)
total_ch = len(ALL_CHAPTERS)
done_ch = sum(1 for v in st.session_state.checked.values() if v)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"### 진행 현황: {done_ch} / {total_ch}장")
st.progress(min(1.0, done_ch / total_ch))
st.markdown("</div>", unsafe_allow_html=True)

# 본문 영역
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("본문")

sel_reading: Optional[List[Tuple[str, int]]] = st.session_state.get("selected_reading")
if not sel_reading:
    st.markdown('<div class="muted">평일에 <b>📖 성경 읽기</b> 버튼을 누르면 오늘 분량(5장)이 표시됩니다.</div>', unsafe_allow_html=True)
else:
    # 로컬 폴더 존재 안내
    if not LOCAL_BIBLE_BOOKS_DIR.exists():
        st.warning("bible_books_json 폴더가 repo 루트에 있어야 합니다. (예: bible_books_json/gen.json)")

    with st.spinner("bible_books_json에서 본문을 불러오는 중..."):
        for (book, ch) in sel_reading:
            st.markdown(f"### {book} {ch}장")
            text, src = load_chapter_text(book, ch)
            if not text:
                st.warning(f"{book} {ch}장 본문을 불러오지 못했습니다. (source={src})")
            else:
                st.caption(f"로드 소스: {src}")
                st.text_area(f"{book} {ch}장", value=text, height=260)

st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 디버그 패널 (원인 바로 확인용)
# =========================================================
with st.expander("디버그(본문 로드 문제 확인)"):
    st.write("1) 로컬 폴더 존재 여부:", LOCAL_BIBLE_BOOKS_DIR.exists())
    if LOCAL_BIBLE_BOOKS_DIR.exists():
        # 일부만 표시
        files = sorted([p.name for p in LOCAL_BIBLE_BOOKS_DIR.glob("*.json")])
        st.write("2) 로컬 json 파일 개수:", len(files))
        st.write("3) 예시 파일(앞 10개):", files[:10])

    # gen.json 키 구조 샘플 표시
    gen_path = LOCAL_BIBLE_BOOKS_DIR / "gen.json"
    if gen_path.exists():
        try:
            obj = json.loads(gen_path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                keys = list(obj.keys())
                st.write("4) gen.json 최상위 키(앞 30개):", keys[:30])
                # chapters/data wrapper가 있으면 그 안의 키도 확인
                for w in ["chapters", "data", "chapter"]:
                    if w in obj and isinstance(obj[w], dict):
                        st.write(f"5) gen.json['{w}'] 키(앞 30개):", list(obj[w].keys())[:30])
        except Exception as e:
            st.write("gen.json 파싱 오류:", e)
    else:
        st.write("gen.json 파일이 로컬에 없습니다. (bible_books_json/gen.json 확인)")
