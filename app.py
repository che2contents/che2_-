import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st

# =========================================================
# 0) 기본 설정
# =========================================================
st.set_page_config(page_title="인천제2교회 성경읽기표", layout="wide")

YOUTUBE_URL = "https://www.youtube.com/@%EC%9D%B8%EC%B2%9C%EC%A0%9C2%EA%B5%90%ED%9A%8C-che2"

# ✅ 권별 JSON 폴더 (사용)
BIBLE_BOOKS_DIR = st.secrets.get("GITHUB_BIBLE_BOOKS_DIR", "bible_books_json")

# GitHub Raw 로딩을 위한 정보 (public repo면 토큰 없어도 됨)
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
# 1) 스타일(명조) + 배너
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

try:
    st.markdown('<div class="banner-wrap">', unsafe_allow_html=True)
    st.image("assets/banner.jpg", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    st.warning("assets/banner.jpg 배너 파일을 repo에 추가해 주세요.")

st.title("성경읽기표 (2월~12월 · 월~토 5장 · 주일 영상)")
st.caption("bible_books_json에서 본문 로드 · 로그인 없이 개인코드 + 백업/복원")

# =========================================================
# 2) 개인코드 + 내보내기/가져오기(백업)
# =========================================================
def norm_code(s: str) -> str:
    return (s or "").strip()

def default_progress(code: str) -> Dict[str, Any]:
    return {
        "version": 1,
        "code": code,
        "createdAt": datetime.now().isoformat(timespec="seconds"),
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "checked": {},   # { "gen:001": true, ... }  (장 단위 체크)
    }

def key_for(book_name: str, chapter: int) -> str:
    book_code = BOOKS.get(book_name, book_name)
    return f"{book_code}:{chapter:03d}"

if "active_code" not in st.session_state:
    st.session_state.active_code = ""
if "progress" not in st.session_state:
    st.session_state.progress = None
if "selected_day" not in st.session_state:
    st.session_state.selected_day = None  # date
if "selected_reading" not in st.session_state:
    st.session_state.selected_reading = None  # List[(book, ch)]

st.markdown('<div class="card">', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
code_in = c1.text_input("개인코드", value=st.session_state.active_code, placeholder="예: ABCD-1234")

if c2.button("코드 적용", use_container_width=True):
    cc = norm_code(code_in)
    if not cc:
        st.error("개인코드를 입력하세요.")
    else:
        st.session_state.active_code = cc
        st.session_state.progress = default_progress(cc)
        st.success("코드 적용 완료!")

if st.session_state.progress and st.session_state.active_code:
    payload = dict(st.session_state.progress)
    payload["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    export_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    c3.download_button(
        "⬇️ 내보내기(백업)",
        data=export_bytes,
        file_name=f"성경읽기표_{st.session_state.active_code}_backup.json",
        mime="application/json",
        use_container_width=True
    )

uploaded = c4.file_uploader("⬆️ 가져오기", type=["json"], label_visibility="collapsed")
if uploaded is not None:
    try:
        obj = json.loads(uploaded.read().decode("utf-8"))
        cc = norm_code(code_in)
        if not cc:
            st.error("먼저 개인코드를 입력한 뒤 업로드하세요(코드 확인용).")
        elif obj.get("code") != cc:
            st.error("업로드 파일의 코드와 현재 개인코드가 다릅니다.")
        else:
            st.session_state.active_code = cc
            st.session_state.progress = obj
            st.success("복원 완료! 진행상황을 불러왔습니다.")
    except Exception as e:
        st.error(f"업로드 실패: {e}")

if st.session_state.progress and st.button("초기화(현재 코드 체크 전부 해제)"):
    cc = st.session_state.active_code
    st.session_state.progress = default_progress(cc)
    st.success("초기화 완료")

st.markdown(
    '<div class="muted">• 기기 변경 시: 기존 폰에서 <b>내보내기</b> → 새 폰에서 <b>가져오기</b><br/>'
    '• 서버 저장이 없어서, 백업 없이 폰을 잃어버리면 복구가 어렵습니다.</div>',
    unsafe_allow_html=True
)
st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.progress:
    st.info("상단에서 개인코드를 입력하고 ‘코드 적용’을 눌러주세요.")
    st.stop()

checked_map: Dict[str, bool] = st.session_state.progress.get("checked", {})

# =========================================================
# 3) 스케줄 생성 (2월~12월, 주일=영상 / 월~토=5장)
# =========================================================
@dataclass
class ReadingDay:
    d: date
    is_sunday: bool
    chapters: List[Tuple[str, int]]  # [(book_name, chapter), ...] length=5 for weekdays, [] for sunday
    label: str

def iter_bible_chapters() -> List[Tuple[str, int]]:
    out = []
    for book in BOOK_ORDER:
        for ch in range(1, CHAPTER_COUNT[book] + 1):
            out.append((book, ch))
    return out

ALL_CHAPTERS = iter_bible_chapters()  # 총 1189장

def build_schedule(year: int) -> List[ReadingDay]:
    start = date(year, 2, 1)
    end = date(year, 12, 31)

    # 날짜 목록
    days: List[date] = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)

    # 주일 제외한 "읽는 날" 개수
    reading_dates = [d for d in days if d.weekday() != 6]  # Python: 월0 ... 일6
    # 하루 5장씩 할당
    idx = 0
    schedule: List[ReadingDay] = []

    for d in days:
        is_sun = (d.weekday() == 6)
        if is_sun:
            schedule.append(ReadingDay(d=d, is_sunday=True, chapters=[], label="주일: 영상 시청"))
            continue

        # 5장 뽑기 (성경 끝나면 남는 날은 빈칸 처리)
        todays: List[Tuple[str, int]] = []
        for _ in range(5):
            if idx < len(ALL_CHAPTERS):
                todays.append(ALL_CHAPTERS[idx])
                idx += 1
        if todays:
            # 라벨: "창세기 1장 ~ 5장" 같은 형태로 묶어 표기 (연속일 때만 보기 좋게)
            b1, c1 = todays[0]
            b2, c2 = todays[-1]
            if b1 == b2:
                label = f"{b1} {c1}–{c2}장"
            else:
                label = f"{b1} {c1}장 ~ {b2} {c2}장"
        else:
            label = "완독 이후(읽기 없음)"
        schedule.append(ReadingDay(d=d, is_sunday=False, chapters=todays, label=label))

    return schedule

# 연도 선택(배포용)
today = date.today()
default_year = today.year
year = st.sidebar.selectbox("연도", [default_year - 1, default_year, default_year + 1], index=1)

schedule = build_schedule(year)

# =========================================================
# 4) GitHub에서 bible_books_json/{book_code}.json 로드
# =========================================================
def github_raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"

@st.cache_data(show_spinner=False)
def fetch_book_json(book_code: str) -> Optional[Dict[str, Any]]:
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

def get_chapter_from_book_json(book_json: Dict[str, Any], chapter: int) -> Optional[Any]:
    """
    가능한 구조들을 넓게 지원:
    - book_json["chapters"]["1"]
    - book_json["1"]
    - book_json["data"]["1"]
    """
    ch_key = str(chapter)
    candidates = [
        ("chapters", ch_key),
        (None, ch_key),
        ("data", ch_key),
    ]
    for root, ck in candidates:
        try:
            node = book_json[ck] if root is None else book_json[root][ck]
            return node
        except Exception:
            continue
    return None

def chapter_to_text(node: Any) -> str:
    """
    node가 string/list/dict 등 어떤 형태든 보기 좋게 변환
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        # [ "1절 ...", "2절 ..."] 또는 [{"v":1,"t":"..."}] 같은 경우도 대비
        lines = []
        for i, v in enumerate(node, start=1):
            if isinstance(v, str):
                lines.append(v)
            elif isinstance(v, dict):
                # 흔한 키 후보
                vv = v.get("v") or v.get("verse") or i
                tt = v.get("t") or v.get("text") or json.dumps(v, ensure_ascii=False)
                lines.append(f"{vv}. {tt}")
            else:
                lines.append(str(v))
        return "\n".join(lines)

    if isinstance(node, dict):
        # dict of verses: {"1":"...", "2":"..."} or {"verses": {...}}
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
    book_json = fetch_book_json(book_code)
    if not book_json:
        return None
    node = get_chapter_from_book_json(book_json, chapter)
    if node is None:
        return None
    text = chapter_to_text(node)
    return text if text.strip() else None

# =========================================================
# 5) UI: 날짜별 표 + 읽기 버튼 + 체크 + 본문 표시
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("주일 영상")
st.link_button("▶️ 주일 유튜브 시청하기", YOUTUBE_URL)
st.markdown("</div>", unsafe_allow_html=True)

# 선택된 날짜(기본: 오늘이 기간 안이면 오늘, 아니면 2/1)
min_day = date(year, 2, 1)
max_day = date(year, 12, 31)
default_day = today if (min_day <= today <= max_day) else min_day

sel = st.date_input("날짜 선택", value=default_day, min_value=min_day, max_value=max_day)
st.session_state.selected_day = sel

# 해당 날짜 찾기
day_obj = next((x for x in schedule if x.d == sel), None)

# 상단 요약
total_chapters = len(ALL_CHAPTERS)  # 1189
done_chapters = sum(1 for k, v in checked_map.items() if v)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"### 진행 현황")
st.markdown(f"- 체크한 장: **{done_chapters} / {total_chapters}장**")
st.progress(min(1.0, done_chapters / total_chapters))
st.markdown("</div>", unsafe_allow_html=True)

if not day_obj:
    st.error("선택한 날짜 데이터를 찾지 못했습니다.")
    st.stop()

# 오늘(선택한 날짜) 카드
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown(f"## {day_obj.d.isoformat()}  ({['월','화','수','목','금','토','일'][day_obj.d.weekday()]})")

if day_obj.is_sunday:
    st.markdown("**주일:** 영상 시청")
    st.link_button("▶️ 유튜브 바로가기", YOUTUBE_URL)
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown(f"**오늘 읽기:** {day_obj.label}")
    # 장별 체크(5장)
    cols = st.columns(5)
    for i, (book, ch) in enumerate(day_obj.chapters):
        k = key_for(book, ch)
        default_checked = bool(checked_map.get(k, False))
        new_val = cols[i].checkbox(f"{book} {ch}장", value=default_checked, key=f"chk_{day_obj.d}_{k}")
        checked_map[k] = new_val

    # 읽기 버튼: 눌렀을 때 본문 로드 대상으로 설정
    if st.button("📖 성경 읽기(본문 로드)", use_container_width=True):
        st.session_state.selected_reading = day_obj.chapters

    st.markdown("</div>", unsafe_allow_html=True)

# 진행 상태 저장(세션)
st.session_state.progress["checked"] = checked_map
st.session_state.progress["updatedAt"] = datetime.now().isoformat(timespec="seconds")

# =========================================================
# 6) 본문 표시 영역 (읽기 버튼 눌렀을 때만)
# =========================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("본문")

sel_reading: Optional[List[Tuple[str, int]]] = st.session_state.get("selected_reading")

if not sel_reading:
    st.markdown('<div class="muted">위에서 <b>성경 읽기(본문 로드)</b> 버튼을 누르면, 그날 5장 본문이 여기 표시됩니다.</div>', unsafe_allow_html=True)
else:
    # GitHub 연결 점검
    if not (GITHUB_OWNER and GITHUB_REPO):
        st.warning("secrets.toml에 GITHUB_OWNER / GITHUB_REPO를 설정해야 본문을 로드할 수 있습니다.")
    else:
        with st.spinner("bible_books_json에서 본문을 불러오는 중..."):
            for (book, ch) in sel_reading:
                st.markdown(f"### {book} {ch}장")
                text = load_chapter_text(book, ch)
                if not text:
                    st.warning(f"{book} {ch}장 본문을 불러오지 못했습니다. (JSON 구조/경로 확인 필요)")
                else:
                    st.text_area(f"{book} {ch}장", value=text, height=260)

st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 7) (선택) 전체 일정 간단 리스트(스크롤)
# =========================================================
with st.expander("전체 일정 보기(요약)"):
    st.caption("2월 1일 ~ 12월 31일 / 주일은 영상, 월~토는 5장")
    for rd in schedule[:60]:
        # 너무 길어지니 앞부분만 기본 표시 (원하면 전체도 가능)
        dow = ['월','화','수','목','금','토','일'][rd.d.weekday()]
        if rd.is_sunday:
            st.write(f"{rd.d.isoformat()} ({dow}) - 주일: 영상")
        else:
            st.write(f"{rd.d.isoformat()} ({dow}) - {rd.label}")
    st.caption("※ 전체 출력이 필요하면 이 expander를 전체로 확장하도록 수정해드릴 수 있어요.")
