import os
import json
import asyncio
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from playwright.async_api import async_playwright

# 수집 결과는 저장소의 jobs.json에 저장하고, 커밋되면 GitHub Pages가 서빙한다
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
# 마감되어 jobs.json에서 사라진 공고까지 누적 보존 (기관별 아카이브 페이지 원본)
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")
KST = timezone(timedelta(hours=9))

def extract_dates(text, current_year):
    # 년, 월, 일 한글 표기 및 -, ., / 모두 지원
    pattern = r'(?:((?:20)?\d{2})\s*(?:[-./]|년)\s*)?(\d{1,2})\s*(?:[-./]|월)\s*(\d{1,2})\s*일?(?!\d)'
    matches = list(re.finditer(pattern, text))
    
    parsed_dates = []
    last_year = current_year
    
    for m in matches:
        y_str, mo_str, d_str = m.groups()
        if y_str:
            last_year = int(y_str)
            if last_year < 100: last_year += 2000
        
        mo = int(mo_str)
        d = int(d_str)
        
        if not (1 <= mo <= 12 and 1 <= d <= 31): continue
        
        end_idx = m.end()
        lookahead = text[end_idx:end_idx+25]
        time_m = re.search(r'(\d{1,2})\s*:\s*(\d{2})', lookahead)
        
        hour, minute = 0, 0
        has_time = False
        if time_m:
            hour = int(time_m.group(1))
            minute = int(time_m.group(2))
            if hour >= 24: hour, minute = 23, 59
            has_time = True
            
        try:
            dt_obj = datetime(last_year, mo, d, hour, minute)
            # 연도 없는 날짜가 직전 날짜보다 한참 이전이면 해 넘김으로 간주 (ex. 12.20 ~ 01.05)
            if not y_str and parsed_dates:
                prev_dt = parsed_dates[-1]['dt']
                if dt_obj < prev_dt and (prev_dt - dt_obj).days > 180:
                    dt_obj = dt_obj.replace(year=dt_obj.year + 1)

            if current_year - 2 <= dt_obj.year <= current_year + 2:
                parsed_dates.append({'dt': dt_obj, 'has_time': has_time})
        except Exception:
            pass
            
    parsed_dates.sort(key=lambda x: x['dt'])
    return parsed_dates

def now_kst_naive():
    return datetime.now(KST).replace(tzinfo=None)

def parse_end_date(value):
    """jobs.json에 저장된 "yy.mm.dd" 또는 "yy.mm.dd HH:MM" 형식을 datetime으로 되돌린다.
    읽을 수 없으면 None (= 마감 여부를 판단하지 않음)."""
    m = re.match(r'\s*(\d{2})\.(\d{1,2})\.(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?', str(value or ""))
    if not m:
        return None
    try:
        return datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4) or 18), int(m.group(5) or 0))
    except ValueError:
        return None

# 국립중앙의료원(병원)에서 제외할 임상 포지션 — 직역·근무 장소 기준
NMC_CLINICAL = [
    "전공의", "전임의", "레지던트", "인턴의", "임상강사", "촉탁의",
    "병동", "수술실", "중환자실", "응급실", "분만", "마취",
    "간호조무", "임상", "진료", "병리사", "방사선사", "물리치료",
    "작업치료", "임상병리", "치과위생",
    "간호부", "외래", "투석", "검진센터", "외상센터",
    # 진료과 기준 — 제목이 "계약직 간호사(간호부-소화기내과)"처럼 배치 부서로만
    # 임상 여부가 드러나는 공고가 많아 진료과명을 별도로 걸러낸다.
    # ("내과"는 감염내과·소화기내과 등 세부 분과를 부분 문자열로 함께 잡는다.)
    "내과", "외과", "소아과", "소아청소년과", "산부인과", "부인과",
    "신경과", "신경외과", "정형외과", "흉부외과", "성형외과",
    "정신건강의학과", "피부과", "안과", "이비인후과", "비뇨의학과",
    "비뇨기과", "재활의학과", "영상의학과", "핵의학과",
    "마취통증의학과", "진단검사의학과", "응급의학과", "가정의학과",
    "직업환경의학과", "예방의학과", "병리과", "치과", "한방",
]

# 의사 면허가 필요한 직무 제외.
#
# 【수집 정책】이 사이트의 독자는 탈임상을 준비하는 간호사·보건직 취업준비생이다.
# 의사 면허가 있어야 지원할 수 있는 공고는 임상이든 정책연구직이든 이들이 지원할 수
# 없으므로 일괄 제외한다. (예: "의사직(응급의료정책연구팀)"은 비임상이지만 제외 대상)
# 반대로 면허 요건이 간호사·응급구조사인 비병동 직무는 수집한다.
#
# ⚠️ \b 를 쓰면 안 된다. 파이썬 유니코드 정규식에서 한글은 워드 문자라
#    '의사직'의 '의사'와 '직' 사이에 단어 경계가 성립하지 않아 매치되지 않는다.
#    (이 때문에 "의사직(응급의료정책연구팀) 채용 재공고"가 그대로 수집됐다)
#    앞뒤 한글 여부를 직접 확인해 '의사소통' 같은 단어와만 구분한다.
DOCTOR_RE = re.compile(r'(?<![가-힣])(?:의사직|의사|전문의|수련의|전공의)(?![가-힣])')


# 신규 채용이 아닌 공고 제외.
#
# 【수집 정책】아래는 형식만 '모집 공고'일 뿐 이 사이트 독자가 지원할 수 있는
# 신규 채용이 아니다. 지원 자격 자체가 '현직자'이거나 임원·기관장급이다.
#   · 전입·전출·파견 — 현직 공무원 대상 인사 이동 (예: "지방직 7급 공무원 전입희망자 모집")
#   · 초빙·이사장 — 임원 공모 (예: "국민건강보험공단 이사장 초빙")
#   · 위원장 — 심사·평가 위원회 위원장, 사실상 의사 등 전문가 위촉 (예: "진료심사평가위원장 채용")
#   · 연구소장·연구원장·병원장 — 기관장급 보직 공모
#       (예: "심사평가정책연구소장(개방형 직위) 채용", "경북대학교병원장 공개모집 공고")
#   · 개방형 — 개방형직위 및 그와 함께 뽑는 전문인력. 둘 다 현직 고위직 대상이다.
#
# ⚠️ '개방형직위 및 전문인력 채용'은 '전문인력'이라는 말 때문에 일반 채용으로 보이지만,
#    실제 자격요건은 아래와 같이 전부 현직·고위 경력자로 한정된다.
#      · 개방형직위(건강보험연구원장) — 박사학위 취득 후 관련분야 연구경력 8년 이상
#      · 전문인력(보건·의료정책)     — 국가·지방공무원 5급 이상 1년 / 6급 5년 이상 재직,
#                                     또는 공기업·준정부기관 2급 이상 1년 이상 재직
#    취업준비생·탈임상 간호사는 지원 자체가 불가능하므로 '개방형'이 붙으면 제외한다.
#    (띄어쓰기가 '개방형직위'·'개방형 직위' 양쪽으로 쓰여 '개방형'만으로 잡는다)
NON_HIRING = ["전입", "전출", "초빙", "이사장", "위원장",
              "연구소장", "연구원장", "병원장", "의료원장", "개방형"]

# 신규 채용이 맞지만 이 사이트 독자를 대상으로 하지 않는 공고.
#
# 【수집 정책】채용은 채용이지만 응시 대상이 취업준비생·탈임상 간호사가
# 아니라서 목록에 섞이면 노이즈가 되는 공고들이다. 두 갈래가 있다.
#
#   1) 퇴직자·고령자 재취업 지원 사업
#      예) "베테랑 시니어지원단(기간제근로자) 공개채용", "시니어인턴십"
#      (기존 exclude_words 의 '고령'과 같은 취지다)
#
#   2) 국민연금공단 기금운용본부(전주)의 투자 전문직
#      예) "기금운용본부 자산운용전문가 채용공고", "기금운용직 채용 공고"
#      국민연금 산하지만 실제로는 금융·투자 조직이라, 요구 경력이
#      운용역·애널리스트·CFA 등 자산운용 경력이다. 보건의료 직무와 무관하다.
#
# ⚠️ '운용'만으로 잡으면 안 된다. "전산 운용", "시스템 운용" 같은 실제 채용이
#    함께 사라진다. '기금운용'·'자산운용'·'운용역'으로 좁혀 잡는다.
OFF_TARGET = ["시니어", "베테랑", "신중년",
              "기금운용", "자산운용", "운용역"]

# ⚠️ '파견'은 통째로 막으면 안 된다. "파견직·파견근로자"는 현직자 인사 이동이 아니라
#    엄연한 고용형태라서, 그런 공고까지 사라지면 진짜 채용을 놓친다.
#    현직자 대상 파견(= 파견근무자/파견자 모집)만 골라낸다.
DISPATCH_RE = re.compile(r'파견\s*(?:근무자|자|근무)')
EMPLOYMENT_DISPATCH_RE = re.compile(r'파견\s*(?:직|근로자|사원)')


# 접수기간을 가리키는 키워드. 강할수록 먼저 채택한다.
#
# ⚠️ '일정'은 넣지 않는다. "전형일정" 표가 걸려 서류발표·필기·면접·임용 날짜를
#    접수기간으로 잘못 읽어오기 때문이다. "접수일정"은 '접수'로 이미 잡힌다.
PERIOD_KW_STRONG = ['접수기간', '접수 기간', '원서접수', '지원기간', '신청기간',
                    '공고기간', '모집기간']
PERIOD_KW_WEAK = ['접수', '지원', '기간', '기한', '모집', '신청', '마감']

# 전형 일정 표를 접수기간으로 오인하지 않기 위한 신호
SCHEDULE_KW = ['전형일정', '서류전형', '필기시험', '면접시험', '합격자', '발표',
               '임용', '교육']


def is_excluded_title(inst_id, title):
    """현재 수집 정책상 제외 대상인 제목인지 판정한다.

    수집 단계와, 과거 데이터(history/직전 jobs)에서 공고를 되살릴 때 **같은 기준**을
    적용하기 위해 함수로 분리했다. 이게 없으면 제외 규칙을 강화해도 예전에 수집된
    공고가 복원 경로로 되살아난다.
    """
    t = (title or "").replace('[', ' ').replace(']', ' ')
    if DOCTOR_RE.search(t):
        return True
    if any(k in t for k in NON_HIRING):
        return True
    if any(k in t for k in OFF_TARGET):
        return True
    if DISPATCH_RE.search(t) and not EMPLOYMENT_DISPATCH_RE.search(t):
        return True
    if inst_id == 'nmc' and any(k in title for k in NMC_CLINICAL):
        return True
    return False


def classify_job_type(title):
    """공고 제목에서 고용형태를 판정한다.

    현직자 대상 전입·파견이나 임원 공모는 여기서 분류하지 않는다. 애초에
    is_excluded_title() 에서 수집 자체를 막기 때문이다.
    반면 '파견직·파견근로자'는 실재하는 고용형태이므로 계약직으로 분류한다.
    """
    if "무기계약직" in title:
        return "무기계약직"
    if "공무직" in title:
        return "공무직"
    if any(k in title for k in ["기간제", "계약직", "촉탁직", "휴직", "대체", "임시직",
                                "파견직", "파견근로자"]):
        return "계약직/기간제"
    if "비정규직" in title:
        return "비정규직"
    if "인턴" in title:
        return "인턴"
    return "정규직"

GENERAL_REGIONS = ["서울", "부산", "대구", "인천", "광주", "울산", "경기", "강원", "충북", "전북", "전남", "경북", "경남", "제주"]

# 기관명 → 소재지 매핑. 공고에서 기관명이 확인되면 본문 주소보다 우선 적용한다.
# (보건복지부 게시판에는 소속·산하기관 공고가 섞여 있어 페이지 주소(세종)로 오탐이 발생)
KNOWN_ORG_REGIONS = {
    "사회보장정보원": "서울",     # 한국사회보장정보원 (마포)
    "국립중앙의료원": "서울",
    "국립정신건강센터": "서울",
    "국립재활원": "서울",
    "건강증진개발원": "서울",     # 한국건강증진개발원 (광진구 보건복지행정타운)
    "국립암센터": "경기",         # 고양
    "국립춘천병원": "강원",
    "국립공주병원": "대전충남",
    "국립부곡병원": "경남",
    "국립마산병원": "경남",
    "국립목포병원": "전남",
    "국립나주병원": "전남",
    "국립소록도병원": "전남",
    "질병관리청": "충북",         # 오송
    "국립보건연구원": "충북",     # 오송
    "보건복지인재원": "충북",     # 오송
    "오송": "충북",
}

def regions_in_text(text):
    found = set()
    if "거창" in text: found.add("경남")
    if "상주" in text: found.add("경북")
    if "남부혈액검사센터" in text: found.add("부산")
    if "혈액관리본부" in text: found.add("강원")
    if "경인" in text: found.update(["경기", "인천"])
    if any(k in text for k in ["대전", "세종", "충남"]): found.add("대전충남")
    for r in GENERAL_REGIONS:
        if r in text: found.add(r)
    return found

def detect_region(inst_id, title, row_text, combined_text):
    # 1) 알려진 기관명이 보이면 소재지 확정 (제목·목록행 우선)
    for org, reg in KNOWN_ORG_REGIONS.items():
        if org in title or org in row_text:
            return reg
    # 본문 전체(combined_text) 기관명 매칭은 오탐 위험이 있어 mohw는 제외한다.
    # (보건복지부 게시판/상세는 인접 공고·타 기관명이 섞여 들어와, 예: '첨단재생'
    #  공고가 인접한 '국립소록도병원'을 잡아 전남으로 오인식되는 문제가 있었음)
    if inst_id != 'mohw':
        for org, reg in KNOWN_ORG_REGIONS.items():
            if org in combined_text:
                return reg

    # 2) 근무지/근무장소가 명시된 줄에서만 추출 (본문 전체 스캔보다 정확)
    #    표 형태(라벨 줄과 값 줄이 분리)를 대비해 해당 줄 + 다음 줄까지 함께 본다.
    region_set = set()
    ctx_lines = combined_text.split('\n')
    for i, line in enumerate(ctx_lines):
        if any(k in line for k in ['근무지', '근무장소', '근무 장소', '근무예정지', '근무예정부서', '소재지']):
            region_set |= regions_in_text(" ".join(ctx_lines[i:i+2]))

    # 3) 제목에서 추출
    if not region_set:
        region_set = regions_in_text(title)

    # 4) 본문 전체 스캔 — 마지막 수단.
    #    mohw는 게시판/본문에 세종 주소가 항상 포함되어 오탐이 심하므로 제외
    if not region_set and inst_id != 'mohw':
        region_set = regions_in_text(combined_text)

    if region_set:
        return ", ".join(sorted(region_set))

    # 5) 공고에 근무지가 명시되지 않은 경우: 본부 소재지 + 짧은 확인 안내 표시
    #    (필터는 문자열 포함 매칭이라 꼬리표가 붙어도 그대로 동작)
    if inst_id in ["neca", "kuksiwon", "koiha", "khepi", "nmc"]: return "서울(본부·공고확인)"
    if inst_id == "kac": return "서울(본사·공고확인)"
    if inst_id in ["hira", "nhis", "redcross"]: return "강원(본부·공고확인)"
    if inst_id == "nps": return "전북(본부·공고확인)"
    if inst_id == "comwel": return "울산(본부·공고확인)"
    return "전국(공고확인)"

def _careeron_iso_to_dot(s):
    # "2026-07-20", "2026-07-20T18:00:00", "2026.07.20 18:00" → "yy.mm.dd [HH:MM]"
    m = re.search(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?', str(s))
    if not m:
        return None
    base = f"{int(m.group(1)) % 100:02d}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"
    if m.group(4) is not None:
        return base + f" {int(m.group(4)):02d}:{m.group(5)}"
    return base

def build_careeron_jobs(payload, inst_id):
    # careeron SPA의 목록 API(JSON)에서 공고를 직접 추출한다.
    if not payload:
        return []
    def find_list(obj, depth=0):
        if isinstance(obj, list):
            return obj if (obj and isinstance(obj[0], dict)) else None
        if isinstance(obj, dict) and depth < 5:
            for key in ['list', 'items', 'content', 'rows', 'recruitments',
                        'data', 'result', 'resultList', 'dataList']:
                if key in obj:
                    r = find_list(obj[key], depth + 1)
                    if r:
                        return r
            for v in obj.values():
                r = find_list(v, depth + 1)
                if r:
                    return r
        return None

    items = find_list(payload) or []
    now = datetime.now(KST).replace(tzinfo=None)
    exclude_words = ["발표", "합격", "면접", "약사", "약무", "의무직", "사전공개", "채용계획",
                     "공시송달", "서류전형", "참여기관", "공모", "재직", "상임", "고령", "친인척",
                     "계획 공고", "실습 인정", "교육훈련기관", "등록폐지", "윤리위원회",
                     "기준보험료", "심사위원", "변호사"]
    jobs = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = None
        for k, v in it.items():
            if any(t in k.lower() for t in ['title', 'subject']) and isinstance(v, str) and v.strip():
                title = re.sub(r'\s+', ' ', v).strip()
                break
        if not title or len(title) < 3:
            continue
        if any(ex in title for ex in exclude_words):
            continue
        # 의사 면허 필요 직무·전입·파견·임원 공모 제외 (다른 수집 경로와 같은 기준)
        if is_excluded_title(inst_id, title):
            continue
        rid = None
        for k, v in it.items():
            lk = k.lower()
            if (lk in ('id', 'seq', 'no', 'idx') or lk.endswith('id') or lk.endswith('seq') or lk.endswith('idx')) \
               and isinstance(v, (int, str)) and str(v).strip() and str(v).strip() != '0':
                rid = str(v).strip()
                break
        link = f"https://bloodinfo.careeron.co.kr/#/recruitment/detail/{rid}" if rid else "https://bloodinfo.careeron.co.kr/#/recruitment/list"
        start_str, end_str = "상세참조", "상세참조"
        for k, v in it.items():
            lk = k.lower()
            if start_str == "상세참조" and any(x in lk for x in ['start', 'begin', 'apply', 'open', 'reg']) and v:
                dv = _careeron_iso_to_dot(v)
                if dv:
                    start_str = dv
            if end_str == "상세참조" and any(x in lk for x in ['end', 'close', 'deadline', 'expire', 'fin']) and v:
                dv = _careeron_iso_to_dot(v)
                if dv:
                    end_str = dv
        status = "진행중"
        m = re.match(r'(\d{2})\.(\d{2})\.(\d{2})(?:\s+(\d{1,2}):(\d{2}))?', end_str)
        if m:
            try:
                end_dt = datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                  int(m.group(4) or 18), int(m.group(5) or 0))
                if now > end_dt:
                    status = "마감"
            except Exception:
                pass
        if status == "마감":
            continue
        job_type = classify_job_type(title)
        jobs.append({
            "instId": inst_id, "title": title,
            "startDate": start_str, "endDate": end_str, "status": status,
            "jobType": job_type, "region": detect_region(inst_id, title, title, title),
            "link": link,
        })
    return jobs

async def scrape_site(browser, inst_id, url):
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR"
    )
    
    try:
        print(f"[{inst_id}] 접속 중: {url}")

        # careeron(혈액원) SPA: 목록이 헤드리스에서 렌더링되지 않으므로, SPA가 호출하는
        # 목록 API 응답(JSON)을 가로채 직접 파싱한다. (DOM 스크래핑 불가 확인됨)
        if 'careeron' in url:
            list_json = None
            try:
                async with page.expect_response(
                    lambda r: 'recruitment/list' in r.url and 'api' in r.url, timeout=45000
                ) as ri:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                resp = await ri.value
                list_json = await resp.json()
            except Exception as e:
                print(f"[CAREERON] 목록 API 응답 캡처 실패: {e}")
            careeron_jobs = build_careeron_jobs(list_json, inst_id)
            print(f"[{inst_id}] careeron API에서 {len(careeron_jobs)}건 수집")
            return careeron_jobs[:10], True

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        job_candidates = []
        row_limit = 15
        rows = await page.query_selector_all("tbody tr, .board-list li, ul.list li, .recruitment-item")
        if not rows:
            # 링크 전체 폴백: 상단 내비게이션 링크가 많으므로 더 넓게 훑는다
            rows = await page.query_selector_all("a")
            # 링크 전체 폴백에서는 상단 내비게이션 링크가 앞부분을 차지해,
            # 한도가 낮으면 정작 뒤쪽의 실제 공고를 못 보고 잘린다. 넉넉히 잡는다.
            row_limit = 150

        now = datetime.now(KST)

        for row in rows[:row_limit]:
            try:
                row_text = (await row.inner_text()).strip()
                row_html = await row.inner_html() 
                
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A": link_el = row
                    else: continue
                        
                raw_title = (await link_el.inner_text()).strip()
                if len(raw_title) < 5: continue

                # 목록 셀이 여러 줄일 때(제목/등록일/마감일이 줄바꿈으로 분리) 아래 날짜
                # 꼬리표 정규식의 `.*$`가 줄을 넘지 못해 첫 번째 날짜만 살아남는다.
                # (예: "…공고(연구직)\n2026.07.24\n2026.08.12 18:00" → "…공고(연구직) 2026.07.24")
                # 먼저 공백을 한 칸으로 정규화해 한 줄로 만든 뒤 꼬리표를 제거한다.
                clean_title = re.sub(r'\s+', ' ', raw_title).strip()

                # 🔥 제목에 붙어있는 날짜 꼬리표 깔끔하게 날리기 (ex. 2026-03-11(수) 17:00 ~ ...)
                date_suffix_pattern = r'\s*\(?(?:(?:20)?\d{2}[-./]\d{1,2}[-./]\d{1,2}).*$'
                date_match = re.search(date_suffix_pattern, clean_title)
                if date_match and date_match.start() > 5: # 제목 전체가 지워지는 것 방지
                    clean_title = clean_title[:date_match.start()]
                    
                clean_title = clean_title.replace('[마감]', '').replace('[새글]', '').replace('새글', '').replace('~', '').strip()
                # 목록 페이지의 상태 배지·D-day 부스러기 제거
                # (예: "접수중 의료기관평가인증원 … 공고(연구직) D-17" → "의료기관평가인증원 … 공고(연구직)")
                clean_title = re.sub(r'^\s*(?:접수중|접수전|접수예정|진행중|모집중|마감임박|신규)\s+', '', clean_title)
                # 목록 배지가 제목 뒤에 붙는 경우 제거 (예: '… 공고 공채 일반채용 신입')
                clean_title = re.sub(r'(?:\s+(?:공채|일반채용|수시채용|상시채용|신입|경력|신입/경력))+\s*$', '', clean_title)
                # ⚠️ 숫자형(D-17)뿐 아니라 마감 당일 표기(D-Day)도 지워야 한다.
                #    안 지우면 같은 공고가 "…공고(연구직)"과 "…공고(연구직) D-Day"
                #    두 건으로 갈려 아카이브에 중복으로 쌓인다.
                clean_title = re.sub(r'\s*D\s*-\s*(?:\d+|[Dd][Aa][Yy])\s*', ' ', clean_title)
                # 표 형태 목록에서 셀 구분자(|)와 뒤따르는 배지가 제목에 섞여 들어오는 경우
                # (예: "… 공개채용 | 경력 | 2026.07.29 …" → 날짜 제거 후 "… 공개채용 | 경력 |")
                clean_title = re.sub(
                    r'(?:\s*\|\s*(?:경력|신입|신입/경력|공채|일반채용|수시채용|상시채용|정규직|계약직)?)+\s*$',
                    '', clean_title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()

                # 적십자사: 본문에 있는 소속기관명 낚아채기
                if inst_id == 'redcross':
                    branch_match = re.search(r'([가-힣]+(?:적십자병원|혈액원|혈액검사센터|지역본부|지사|본부|센터))', row_text)
                    if branch_match:
                        b_name = branch_match.group(1)
                        if b_name not in clean_title:
                            clean_title = f"[{b_name}] {clean_title}"


                if inst_id == 'mohw':
                    mohw_keywords = ["채용", "모집", "선발", "공무직", "기간제"]
                    if not any(k in clean_title for k in mohw_keywords):
                        continue
                elif inst_id == 'kac':
                    # 한국공항공사는 보건의료 기관이 아니므로 '보건관리자' 직무만 수집한다.
                    # 다만 공고 제목은 '2026년 하반기 경력직 등 공개채용'처럼 통합 공고명이고
                    # 보건관리자는 본문 채용분야 표에만 있는 경우가 많다.
                    # → 여기서는 공고 여부만 확인하고, 실제 '보건관리자' 판정은
                    #    상세 본문(combined_text)을 확보한 뒤 아래에서 수행한다.
                    if not any(k in clean_title for k in ["채용", "공고", "모집", "선발"]):
                        continue
                elif inst_id == 'nmc':
                    # 국립중앙의료원은 병원이라 임상 채용이 대부분 → 탈임상 사이트 성격에 맞게
                    # 진료·병동 등 임상 포지션은 제외하고 행정·연구·보건직 위주로 수집한다.
                    # (제외 목록은 NMC_CLINICAL, 복원 경로와 공유한다)
                    if is_excluded_title(inst_id, clean_title):
                        continue
                    # ⚠️ 임상 제외만 하고 끝내면 사이트 메뉴 링크까지 통과하므로,
                    #    아래 공통 키워드 검사도 반드시 함께 적용한다.
                    if not any(k in clean_title for k in
                               ["채용", "공고", "모집", "선발", "정규직", "계약직",
                                "무기계약직", "기간제", "연구원", "행정", "촉탁직"]):
                        continue
                elif inst_id not in ['redcross', 'neca']:
                    valid_keywords = ["채용", "공고", "모집", "선발", "정규직",
                                      "계약직", "무기계약직", "간호사", "보조원",
                                      "행정", "촉탁직", "기간제", "연구원"]
                    if not any(k in clean_title for k in valid_keywords):
                        continue
                    
                # 🔥 미수집 제외 키워드 대폭 강화
                exclude_words = [
                    "발표", "합격", "면접", "약사", "약무", "의무직",
                    "사전공개", "채용계획", "공시송달", "서류전형", "참여기관", "공모",
                    "재직", "상임", "고령", "친인척",
                    "계획 공고", "실습 인정", "교육훈련기관",
                    "등록폐지", "윤리위원회", "기준보험료", "심사위원", "변호사"
                ]
                if any(ex in clean_title for ex in exclude_words): continue

                # 🔥 사이트 내비게이션·안내 문구 제외 (공고가 아닌 메뉴 링크가 수집되는 것 방지)
                #    목록 선택자가 안 맞아 <a> 전체 폴백으로 갈 때 메뉴가 딸려 들어오는 문제 대응.
                #    예: '지원서 작성', '마이페이지', '채용 FAQ', '문의하기 채용관련 …', '채용공고 리스트'
                nav_words = [
                    "지원서", "마이페이지", "로그인", "회원가입", "문의하기", "채용문의",
                    "FAQ", "QnA", "Q&A", "자주묻는", "자주 묻는",
                    "비전", "미션", "인재상", "찾아오시는", "오시는 길", "이용약관",
                    "개인정보처리", "사이트맵", "바로가기", "더보기", "전체보기",
                    "리스트", "목록", "공고 검색", "채용안내", "채용 안내", "복리후생",
                    # 게시판·메뉴 이름이 공고로 잡히던 사례
                    # (예: 인증원 "채용 프로세스", "채용 공지사항")
                    "프로세스", "공지사항", "채용절차", "채용 절차", "전형절차", "전형 절차",
                ]
                if any(w in clean_title for w in nav_words): continue
                # 배너·홍보 문구 제외 (평서형 권유문은 공고 제목이 아니다)
                if re.search(r'(하세요|하십시오|해보세요|보세요|찾으세요|입니다)\s*[!.]?$', clean_title): continue
                if clean_title.endswith('!'): continue

                # 의사 면허 필요 직무 제외 (정책·근거는 is_excluded_title 참고)
                if is_excluded_title(inst_id, clean_title):
                    continue

                # 고용 형태 분류
                job_type = classify_job_type(clean_title)

                raw_href = await link_el.get_attribute("href")
                onclick_val = await link_el.get_attribute("onclick")
                
                js_code = ""
                if raw_href and "javascript:" in raw_href and "void" not in raw_href:
                    js_code = raw_href.replace("javascript:", "")
                elif onclick_val:
                    js_code = onclick_val

                safe_link = url 
                if inst_id == 'nhis':
                    safe_link = "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"
                elif raw_href and raw_href != "#" and not raw_href.startswith("javascript"):
                    safe_link = urljoin(url, raw_href)

                if (not raw_href or raw_href == "#" or "javascript:void" in raw_href) and not js_code:
                    if inst_id != 'nhis':
                        continue

                job_candidates.append({
                    "instId": inst_id,
                    "title": clean_title,
                    "raw_title": raw_title,
                    "row_text": row_text,
                    "row_html": row_html,
                    "jobType": job_type,
                    "raw_href": raw_href,
                    "js_code": js_code,
                    "base_url": safe_link,
                    "list_url": url 
                })
            except Exception as e: 
                print(f"[{inst_id}] Row parse error: {e}")
                continue

        found_jobs = []
        
        for job in job_candidates:
            combined_text = job['raw_title'] + " \n" + job['row_text']
            js_code = job['js_code']
            safe_link = job['base_url'] 

            detail_page = None
            try:
                if js_code:
                    detail_page = await browser.new_page()
                    await detail_page.goto(job['list_url'], wait_until="domcontentloaded", timeout=10000)
                    try:
                        async with detail_page.expect_navigation(timeout=5000):
                            await detail_page.evaluate(js_code)
                    except Exception:
                        await detail_page.evaluate(js_code)

                    await detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(2)
                    body_text = await detail_page.inner_text("body")
                    # 접수기간 날짜가 아직 안 보이면 렌더링을 조금 더 기다렸다가 재수집
                    if not re.search(r'\d{1,2}\s*[.\-/월]\s*\d{1,2}', body_text):
                        await asyncio.sleep(2.5)
                        try:
                            body_text = await detail_page.inner_text("body")
                        except Exception:
                            pass
                    combined_text += " \n" + body_text

                    current_url = detail_page.url
                    if job['instId'] != 'nhis' and current_url and current_url != job['list_url']:
                        safe_link = current_url

                elif job['raw_href'] and job['raw_href'] != "#" and not job['raw_href'].startswith("javascript"):
                    detail_page = await browser.new_page()
                    await detail_page.goto(safe_link, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)  # SPA(careeron 등) 렌더링 대기
                    body_text = await detail_page.inner_text("body")
                    # 접수기간 날짜가 아직 안 보이면 렌더링을 조금 더 기다렸다가 재수집
                    if not re.search(r'\d{1,2}\s*[.\-/월]\s*\d{1,2}', body_text):
                        await asyncio.sleep(2.5)
                        try:
                            body_text = await detail_page.inner_text("body")
                        except Exception:
                            pass
                    combined_text += " \n" + body_text
            except Exception:
                pass
            finally:
                if detail_page:
                    try:
                        await detail_page.close()
                    except Exception:
                        pass

            # 한국공항공사: 상세 본문까지 확보한 뒤 '보건관리자' 채용분야가 실제로 있는지 확인.
            # (통합 공개채용 공고의 본문 채용분야 표에만 등장하는 경우가 많다)
            if job['instId'] == 'kac' and not re.search(r'보건\s*관리(자|직)', combined_text):
                continue

            # 맞춤형 지역(시/도) 추출
            detected_region = detect_region(job['instId'], job['title'], job['row_text'], combined_text)

            # 🔥 접수기간 탐색 (목록 + 상세페이지 본문 combined_text 대상, 여러 형식 보강)
            start_item = None
            end_item = None
            now_kst = now.replace(tzinfo=None)

            lines = combined_text.split('\n')
            # 1) 접수기간류 키워드가 있는 문맥에서 날짜 탐색.
            #
            # ⚠️ 예전에는 키워드에 '일정'이 있었고, 조건을 만족하는 첫 문맥에서 바로
            #    break 했다. 그래서 접수기간이 표에서 여러 줄로 쪼개져 한 번에 안 잡히면,
            #    뒤에 오는 '전형일정' 표(서류발표·필기·면접·최종합격·임용)가 대신 잡혀
            #    엉뚱한 날짜가 접수기간으로 올라갔다.
            #      예) 심평원 "2026년 하반기 정규직 채용"
            #          실제 2026-08-19 17:00 ~ 2026-09-02 18:00
            #          수집 26.12.22 ~ 26.12.23  ← 최종합격 발표·임용 예정일
            #    → '일정'을 빼고, 키워드 강도로 우선순위를 매겨 가장 확실한 문맥을 고른다.
            best = None   # (우선순위, 줄번호, 시작, 마감)
            for i, line in enumerate(lines):
                if any(k in line for k in PERIOD_KW_STRONG):
                    priority, window = 2, 4   # 라벨과 값이 여러 줄로 나뉜 표까지 커버
                elif any(k in line for k in PERIOD_KW_WEAK):
                    priority, window = 1, 3
                else:
                    continue
                context = " ".join(lines[i:i + window])
                # 전형 일정만 있는 문맥은 접수기간 후보가 아니다
                if any(k in context for k in SCHEDULE_KW) \
                   and not any(k in context for k in ('접수', '원서')):
                    continue
                # 접수기간 **뒤에 이어 붙은** 전형 일정 표는 잘라낸다.
                # 안 자르면 창(window)이 일정 표까지 삼켜서 dates[-1]이
                # 최종합격자 발표일·임용일이 되어 마감일로 올라간다.
                cut = len(context)
                for kw in SCHEDULE_KW:
                    p = context.find(kw)
                    if p > 0:
                        cut = min(cut, p)
                context = context[:cut]
                dates = extract_dates(context, now.year)
                if len(dates) >= 2:
                    s_cand, e_cand = dates[0], dates[-1]
                    # 접수기간이 90일을 넘는 공고는 없다. 넘으면 서로 다른 항목의
                    # 날짜를 짝지은 것이므로 버린다.
                    if (e_cand['dt'] - s_cand['dt']).days > 90:
                        continue
                    if best is None or priority > best[0]:
                        best = (priority, i, s_cand, e_cand)
                    continue
                if len(dates) == 1:
                    d = dates[0]
                    if any(c in context for c in ['까지', '마감', '~', '-']):
                        if end_item is None or d['dt'] > end_item['dt']:
                            end_item = d  # 마감일 후보 (가장 늦은 날짜 유지)
                    elif start_item is None:
                        start_item = d   # 시작일 후보 (가장 처음 것 유지)
            if best:
                start_item, end_item = best[2], best[3]

            # 2) "YYYY.MM.DD ~ (YYYY.)MM.DD [HH:MM]" 범위 패턴 (전체 본문)
            if not (start_item and end_item):
                match = re.search(r'((?:(?:20)?\d{2})\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*?(?:~|-|부터).*?\d{1,2}\s*[-./]\s*\d{1,2}(?:.*?\d{1,2}:\d{2})?)', combined_text.replace('\n', ' '))
                if match:
                    dates = extract_dates(match.group(1), now.year)
                    if len(dates) >= 2:
                        start_item, end_item = dates[0], dates[-1]

            # 3) 마감일 단독 표기 보강 ("~ 7.27 18:00까지", "접수마감 7.27", "마감일 7.27")
            if end_item is None:
                for mk in re.finditer(r'(?:마감|까지|접수\s*종료|접수\s*마감)[^\n]{0,25}', combined_text):
                    dd = extract_dates(mk.group(0), now.year)
                    if dd:
                        cand = dd[-1]
                        if end_item is None or cand['dt'] > end_item['dt']:
                            end_item = cand

            # 4) 최후 폴백: 본문 앞부분(범위 확대)에서 날짜쌍
            if not start_item and not end_item:
                dates = extract_dates(combined_text[:900], now.year)
                if len(dates) >= 2: start_item, end_item = dates[0], dates[-1]
                elif len(dates) == 1: start_item = dates[0]

            if start_item and end_item and start_item['dt'] > end_item['dt']:
                start_item, end_item = end_item, start_item

            start_str, end_str = "상세참조", "상세참조"
            status = "진행중"

            if start_item:
                if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                start_str = start_item['dt'].strftime("%y.%m.%d")

            if end_item:
                if not end_item['has_time']: end_item['dt'] = end_item['dt'].replace(hour=18, minute=0)
                end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                if now_kst > end_item['dt']:
                    status = "마감"

            # 마감일을 못 읽은 공고는 접수 시작일 기준 15일이 지나면 자동 마감 처리
            # (대부분의 공공기관 접수기간이 2~3주 이내이므로, 오래 떠 있는 것을 방지)
            if start_item and not end_item:
                if (now_kst - start_item['dt']).days > 15:
                    status = "마감"

            # 목록에 마감 표기가 명시된 경우 ("마감연장" 공고는 진행 중으로 취급)
            if ("마감" in job['raw_title'] and "연장" not in job['raw_title']) \
               or "접수종료" in job['row_html'] or "접수마감" in job['row_html'] or "채용종료" in job['row_html']:
                status = "마감"

            # 마감된 공고는 저장하지 않음 → 사이트에 노출되지 않음
            if status != "마감":
                found_jobs.append({
                    "instId": job['instId'],
                    "title": job['title'],
                    "startDate": start_str,
                    "endDate": end_str,
                    "status": status,
                    "jobType": job['jobType'],
                    "region": detected_region,
                    "link": safe_link 
                })
        
        unique_jobs = []
        seen = set()
        for job in found_jobs:
            c = job['title'].replace(" ", "")
            if c not in seen:
                unique_jobs.append(job)
                seen.add(c)
        return unique_jobs[:10], True
    except Exception as e:
        print(f"Error in {inst_id}: {e}")
        return [], False
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        targets = [
            {"id": "hira", "url": "https://hira.recruitlab.co.kr/app/recruitment-announcement/list"},
            {"id": "nhis", "url": "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"},
            {"id": "neca", "url": "https://www.neca.re.kr/lay1/program/S1T207C209/people/index.do"},
            # 국시원은 채용 페이지를 인크루트로 옮겼다. 옛 intojob 주소는 열리지 않아
            # 수집 실적이 0건이었다(history.json 에 kuksiwon 항목이 한 건도 없었음).
            {"id": "kuksiwon", "url": "https://recruit.incruit.com/kuksiwon"},
            {"id": "koiha", "url": "https://koiha.recruiter.co.kr/career/job"},
            {"id": "nps", "url": "https://www.nps.or.kr/pnsgdnc/hiregdnc/getOHAE0004M0List.do"},
            {"id": "comwel", "url": "https://www.comwel.or.kr/recruit/hp/pblanc/pblancList.do"},
            {"id": "redcross", "url": "https://www.redcross.or.kr/recruit/"},
            {"id": "redcross", "url": "https://bloodinfo.careeron.co.kr/#/recruitment/list"},
            {"id": "mohw", "url": "https://www.mohw.go.kr/board.es?mid=a10501010400&bid=0003"},
            # 사용자 요청으로 추가된 기관 (요청 접수 시트 반영)
            {"id": "khepi", "url": "https://khepi-hr.jobnlab.co.kr/"},
            {"id": "nmc", "url": "https://nmc.recruiter.co.kr/app/jobnotice/list"},
            {"id": "kac", "url": "https://kac.careerlink.kr/jobs"}
        ]
        
        all_jobs = []
        succeeded = set()
        for t in targets:
            jobs, ok = await scrape_site(browser, t['id'], t['url'])
            if ok:
                succeeded.add(t['id'])
                all_jobs.extend(jobs)
        await browser.close()

        if not succeeded:
            print("모든 사이트 수집 실패 - 기존 데이터를 유지합니다.")
            return

        # 수집에 실패한 기관은 기존 jobs.json의 데이터를 보존
        try:
            with open(JOBS_FILE, encoding="utf-8") as f:
                old_jobs = json.load(f).get("jobs", [])
        except Exception:
            old_jobs = []
        for job in old_jobs:
            if job.get("instId") not in succeeded:
                all_jobs.append(job)

        # 이전 수집분과 대조해 이미 알아낸 정보가 후퇴하지 않게 한다.
        #  (1) 이번 회차에서 날짜 파싱에 실패해 "상세참조"가 되어도 예전에 읽어둔
        #      실제 마감일이 있으면 그대로 유지한다.
        #  (2) 마감일이 아직 남았는데 목록에서 사라진 공고(다음 페이지로 밀리거나
        #      기관이 게시판을 개편한 경우)는 마감일까지 계속 노출한다.
        #
        # 참조 대상은 직전 jobs.json 만으로는 부족하다. 이미 jobs.json 에서 사라져
        # history.json 에만 남은 공고는 직전 파일에 없어 복원되지 않기 때문에,
        # 누적 이력까지 함께 본다. 같은 공고가 양쪽에 있으면 '더 정확한 값'을 쓴다.
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                hist_jobs = json.load(f).get("jobs", [])
        except Exception:
            hist_jobs = []

        def _key(j):
            return (j.get("instId"), (j.get("title") or "").replace(" ", ""))

        def _date_rank(v):
            """마감일 값의 정확도. 실제 날짜 > 그 밖의 문자열 > 없음/상세참조"""
            if parse_end_date(v):
                return 2
            return 0 if v in (None, "", "상세참조") else 1

        prev_by_key = {}
        for j in hist_jobs + old_jobs:   # 뒤에 오는 old_jobs 가 동점일 때 우선
            k = _key(j)
            cur = prev_by_key.get(k)
            if cur is None or _date_rank(j.get("endDate")) >= _date_rank(cur.get("endDate")):
                prev_by_key[k] = j

        for job in all_jobs:
            prev = prev_by_key.get(_key(job))
            if not prev:
                continue
            # 날짜는 '더 정확한 쪽'을 남기고, 그 외 필드는 비어 있을 때만 채운다
            for fld in ("endDate", "startDate"):
                if _date_rank(job.get(fld)) < _date_rank(prev.get(fld)):
                    job[fld] = prev[fld]
            for fld in ("region", "link"):
                if job.get(fld) in (None, "", "상세참조") \
                   and prev.get(fld) not in (None, "", "상세참조"):
                    job[fld] = prev[fld]

        # 마감 전인데 이번 목록에 없는 공고 복원.
        #   · 제외 규칙이 강화된 뒤라면 되살리지 않는다(is_excluded_title).
        #   · 오래 보이지 않던 공고는 기관이 내린 것으로 보고 되살리지 않는다.
        current_keys = {_key(j) for j in all_jobs}
        now_naive = now_kst_naive()
        STALE_DAYS = 10
        held = 0
        for key, prev in prev_by_key.items():
            inst_id, _ = key
            if key in current_keys or prev.get("status") == "마감":
                continue
            if inst_id not in succeeded:
                continue   # 수집 실패 기관은 위에서 이미 통째로 보존됨
            if is_excluded_title(inst_id, prev.get("title", "")):
                continue
            last_seen = prev.get("lastSeen")
            if last_seen:
                try:
                    if (now_naive - datetime.strptime(last_seen, "%Y-%m-%d")).days > STALE_DAYS:
                        continue
                except ValueError:
                    pass
            end_dt = parse_end_date(prev.get("endDate"))
            if end_dt and end_dt > now_naive:
                rec = {k: v for k, v in prev.items() if k not in ("firstSeen", "lastSeen")}
                rec["jobType"] = classify_job_type(rec.get("title", ""))
                all_jobs.append(rec)
                held += 1
        if held:
            print(f"⏳ 목록에서 사라졌지만 마감 전인 공고 {held}건을 복원했습니다.")

        # 같은 기관을 여러 사이트에서 수집하는 경우(적십자사 본사 + 혈액관리본부) 중복 제거
        def _norm_title(t):
            return re.sub(r'[^0-9A-Za-z가-힣]', '', t or '')

        # 보건복지부 게시판은 국민연금 등 다른 기관 공고를 함께 싣는 경우가 있다.
        # 해당 기관 공고가 이미 원(原) 기관에서 수집됐다면 보건복지부 중복분은 숨긴다.
        nonmohw_norms = [_norm_title(j['title']) for j in all_jobs if j.get('instId') != 'mohw']

        deduped_jobs = []
        seen_keys = set()
        for job in all_jobs:
            key = (job['instId'], job['title'].replace(" ", ""))
            if key in seen_keys:
                continue
            if job.get('instId') == 'mohw':
                jn = _norm_title(job['title'])
                # 원 기관 제목과 정확히 일치하거나, 한쪽이 다른 쪽을 포함하면(양방향) 중복으로 간주.
                # 목록 페이지마다 배지·직렬 표기가 달라 길이가 다를 수 있으므로 양방향으로 본다.
                # (예: koiha "의료기관평가인증원 2026년 제2회 직원채용 공고(연구직)"
                #      ↔ mohw "의료기관평가인증원 2026년 제2회 직원채용 공고")
                if any(n and jn and (n == jn or
                                     (len(n) >= 10 and n in jn) or
                                     (len(jn) >= 10 and jn in n))
                       for n in nonmohw_norms):
                    continue
            seen_keys.add(key)
            deduped_jobs.append(job)
        all_jobs = deduped_jobs

        now_iso = datetime.now(KST).isoformat()
        payload = {"lastSync": now_iso, "jobs": all_jobs}
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"🚀 성공: {len(succeeded)}개 기관, 총 {len(all_jobs)}개의 공고를 jobs.json에 저장!")

        # 누적 이력(history.json) 갱신 — 마감되어 jobs.json에서 사라진 공고도 보존한다.
        # 기관별 아카이브 페이지의 원본 데이터로 쓰인다.
        today = now_iso[:10]
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                hist_doc = json.load(f)
            hist = {f"{j.get('instId')}|{(j.get('title') or '').replace(' ','')}": j
                    for j in hist_doc.get("jobs", [])}
        except Exception:
            hist = {}

        for j in all_jobs:
            key = f"{j.get('instId')}|{(j.get('title') or '').replace(' ','')}"
            if key in hist:
                hist[key]["lastSeen"] = today
                # 이번 수집값이 더 낫거나 같으면 이력을 갱신한다.
                #
                # 예전에는 이력이 비어 있을 때만 채웠는데, 그러면 한번 잘못 읽은
                # 날짜가 아카이브에 영구히 남는다. 파서를 고쳐도 기관 페이지에는
                # 옛 날짜가 그대로 보이므로, 날짜는 정확도가 떨어지지 않는 한
                # 최신 수집값으로 덮어쓴다.
                for fld in ("endDate", "startDate"):
                    v = j.get(fld)
                    if v and _date_rank(v) >= _date_rank(hist[key].get(fld)):
                        hist[key][fld] = v
                for fld in ("region", "link", "jobType"):
                    v = j.get(fld)
                    if v and v != "상세참조" and hist[key].get(fld) in (None, "", "상세참조"):
                        hist[key][fld] = v
            else:
                rec = dict(j)
                rec["firstSeen"] = today
                rec["lastSeen"] = today
                hist[key] = rec

        # 제목 정리 규칙이 바뀌어 같은 공고가 두 키로 갈려 있으면 하나로 합친다.
        # (예: "…공고(연구직)" 와 "…공고(연구직) D-Day" 가 별도 항목으로 쌓였던 건)
        # 배지 부스러기를 걷어낸 정규화 제목으로 묶고, 가장 이른 firstSeen 과
        # 가장 늦은 lastSeen 을 살린다.
        def _canon(t):
            t = re.sub(r'\s*D\s*-\s*(?:\d+|[Dd][Aa][Yy])\s*', ' ', t or '')
            return re.sub(r'[^0-9A-Za-z가-힣]', '', t)

        merged = {}
        for k, j in hist.items():
            ck = (j.get("instId"), _canon(j.get("title")))
            prev = merged.get(ck)
            if prev is None:
                merged[ck] = j
                continue
            # 더 짧은 제목(= 배지가 덜 붙은 쪽)을 대표로 삼는다
            keep, drop = (prev, j) if len(prev.get("title", "")) <= len(j.get("title", "")) else (j, prev)
            for fld in ("firstSeen",):
                a, b = keep.get(fld), drop.get(fld)
                if b and (not a or b < a):
                    keep[fld] = b
            for fld in ("lastSeen",):
                a, b = keep.get(fld), drop.get(fld)
                if b and (not a or b > a):
                    keep[fld] = b
            for fld in ("endDate", "startDate", "region", "link", "jobType"):
                if keep.get(fld) in (None, "", "상세참조") and drop.get(fld) not in (None, "", "상세참조"):
                    keep[fld] = drop[fld]
            merged[ck] = keep
        if len(merged) != len(hist):
            print(f"🔗 배지 차이로 갈려 있던 중복 이력 {len(hist) - len(merged)}건을 합쳤습니다.")
        hist = {f"{j.get('instId')}|{(j.get('title') or '').replace(' ','')}": j
                for j in merged.values()}

        # 제외 규칙이 강화되면 이미 쌓인 이력도 함께 정리한다.
        # 이게 없으면 규칙을 고쳐도 과거에 수집된 공고가 기관별 아카이브 페이지에
        # 영구히 남아, 사이트가 밝힌 수집 범위와 실제 노출이 계속 어긋난다.
        pruned = [k for k, j in hist.items()
                  if is_excluded_title(j.get("instId"), j.get("title", ""))]
        for k in pruned:
            del hist[k]
        if pruned:
            print(f"🧹 수집 제외 규칙에 걸리는 과거 이력 {len(pruned)}건을 정리했습니다.")

        hist_out = {
            "generated": now_iso,
            "jobs": sorted(hist.values(), key=lambda x: x.get("firstSeen", ""), reverse=True),
        }
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(hist_out, f, ensure_ascii=False, indent=1)
        print(f"📁 누적 이력: {len(hist_out['jobs'])}건을 history.json에 보존")

if __name__ == "__main__":
    asyncio.run(main())
