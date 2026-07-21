import os
import json
import asyncio
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from playwright.async_api import async_playwright

# 수집 결과는 저장소의 jobs.json에 저장하고, 커밋되면 GitHub Pages가 서빙한다
JOBS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
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

GENERAL_REGIONS = ["서울", "부산", "대구", "인천", "광주", "울산", "경기", "강원", "충북", "전북", "전남", "경북", "경남", "제주"]

# 기관명 → 소재지 매핑. 공고에서 기관명이 확인되면 본문 주소보다 우선 적용한다.
# (보건복지부 게시판에는 소속·산하기관 공고가 섞여 있어 페이지 주소(세종)로 오탐이 발생)
KNOWN_ORG_REGIONS = {
    "사회보장정보원": "서울",     # 한국사회보장정보원 (마포)
    "국립중앙의료원": "서울",
    "국립정신건강센터": "서울",
    "국립재활원": "서울",
    "건강증진개발원": "서울",     # 한국건강증진개발원 (중구)
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
    # 1) 알려진 기관명이 보이면 소재지 확정
    for org, reg in KNOWN_ORG_REGIONS.items():
        if org in title or org in row_text:
            return reg
    for org, reg in KNOWN_ORG_REGIONS.items():
        if org in combined_text:
            return reg

    # 2) 근무지/근무장소가 명시된 줄에서만 추출 (본문 전체 스캔보다 정확)
    region_set = set()
    for line in combined_text.split('\n'):
        if any(k in line for k in ['근무지', '근무장소', '근무 장소', '근무예정지', '소재지']):
            region_set |= regions_in_text(line)

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
    if inst_id in ["neca", "kuksiwon", "koiha"]: return "서울(본부·공고확인)"
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
        if re.search(r'(?:의사|전문의|수련의|전공의)', title):
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
        job_type = "정규직"
        if "무기계약직" in title: job_type = "무기계약직"
        elif "공무직" in title: job_type = "공무직"
        elif any(k in title for k in ["기간제", "계약직", "촉탁직", "휴직", "대체"]): job_type = "계약직/기간제"
        elif "비정규직" in title: job_type = "비정규직"
        elif "인턴" in title: job_type = "인턴"
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
            row_limit = 60

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

                clean_title = raw_title
                
                # 🔥 제목에 붙어있는 날짜 꼬리표 깔끔하게 날리기 (ex. 2026-03-11(수) 17:00 ~ ...)
                date_suffix_pattern = r'\s*\(?(?:(?:20)?\d{2}[-./]\d{1,2}[-./]\d{1,2}).*$'
                date_match = re.search(date_suffix_pattern, clean_title)
                if date_match and date_match.start() > 5: # 제목 전체가 지워지는 것 방지
                    clean_title = clean_title[:date_match.start()]
                    
                clean_title = clean_title.replace('[마감]', '').replace('[새글]', '').replace('새글', '').replace('~', '').strip()
                clean_title = re.sub(r'\s+', ' ', clean_title)

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
                
                # 의사/전문의 정밀 제외
                clean_title_for_regex = clean_title.replace('[', ' ').replace(']', ' ')
                if re.search(r'\b(?:의사|전문의|수련의|전공의)\b', clean_title_for_regex):
                    continue

                # 고용 형태 분류
                job_type = "정규직"
                if "무기계약직" in clean_title: job_type = "무기계약직"
                elif "공무직" in clean_title: job_type = "공무직"
                elif any(k in clean_title for k in ["기간제", "계약직", "촉탁직", "휴직", "대체"]): job_type = "계약직/기간제"
                elif "비정규직" in clean_title: job_type = "비정규직"
                elif "인턴" in clean_title: job_type = "인턴"

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
                    await asyncio.sleep(1.5)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " \n" + body_text

                    current_url = detail_page.url
                    if job['instId'] != 'nhis' and current_url and current_url != job['list_url']:
                        safe_link = current_url

                elif job['raw_href'] and job['raw_href'] != "#" and not job['raw_href'].startswith("javascript"):
                    detail_page = await browser.new_page()
                    await detail_page.goto(safe_link, wait_until="domcontentloaded", timeout=10000)
                    await asyncio.sleep(1.5)  # SPA(careeron 등) 렌더링 대기
                    body_text = await detail_page.inner_text("body")
                    combined_text += " \n" + body_text
            except Exception:
                pass
            finally:
                if detail_page:
                    try:
                        await detail_page.close()
                    except Exception:
                        pass

            # 맞춤형 지역(시/도) 추출
            detected_region = detect_region(job['instId'], job['title'], job['row_text'], combined_text)

            # 🔥 기간 탐색 키워드 확대 (지원, 기간, 기한 등 추가)
            start_item = None
            end_item = None
            now_kst = now.replace(tzinfo=None)
            
            lines = combined_text.split('\n')
            for i, line in enumerate(lines):
                if any(k in line for k in ['접수', '지원', '기간', '기한', '모집', '일정']) and any(c in line for c in ['~', '-', '부터', '까지']):
                    context = line
                    if i + 1 < len(lines): context += " " + lines[i+1] 
                    dates = extract_dates(context, now.year)
                    if len(dates) >= 2:
                        start_item, end_item = dates[0], dates[-1] # 여러 날짜가 나와도 첫날과 마지막 날만 잡음
                        break
                    elif len(dates) == 1:
                        if any(c in line for c in ['까지', '~', '마감']): end_item = dates[0]
                        else: start_item = dates[0]
                        break

            if not start_item and not end_item:
                match = re.search(r'((?:(?:20)?\d{2})\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*?(?:~|-|부터).*?\d{1,2}\s*[-./]\s*\d{1,2}(?:.*?\d{1,2}:\d{2})?)', combined_text.replace('\n', ' '))
                if match:
                    dates = extract_dates(match.group(1), now.year)
                    if len(dates) >= 2: start_item, end_item = dates[0], dates[-1]

            if not start_item and not end_item:
                dates = extract_dates(combined_text[:500], now.year)
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

            if start_item and not end_item:
                if (now_kst - start_item['dt']).days > 90:
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
            {"id": "kuksiwon", "url": "https://dware.intojob.co.kr/main/kuksiwon.jsp"},
            {"id": "koiha", "url": "https://koiha.recruiter.co.kr/career/job"},
            {"id": "nps", "url": "https://www.nps.or.kr/pnsgdnc/hiregdnc/getOHAE0004M0List.do"},
            {"id": "comwel", "url": "https://www.comwel.or.kr/recruit/hp/pblanc/pblancList.do"},
            {"id": "redcross", "url": "https://www.redcross.or.kr/recruit/"},
            {"id": "redcross", "url": "https://bloodinfo.careeron.co.kr/#/recruitment/list"},
            {"id": "mohw", "url": "https://www.mohw.go.kr/board.es?mid=a10501010400&bid=0003"}
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

        # 같은 기관을 여러 사이트에서 수집하는 경우(적십자사 본사 + 혈액관리본부) 중복 제거
        deduped_jobs = []
        seen_keys = set()
        for job in all_jobs:
            key = (job['instId'], job['title'].replace(" ", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_jobs.append(job)
        all_jobs = deduped_jobs

        payload = {"lastSync": datetime.now(KST).isoformat(), "jobs": all_jobs}
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"🚀 성공: {len(succeeded)}개 기관, 총 {len(all_jobs)}개의 공고를 jobs.json에 저장!")

if __name__ == "__main__":
    asyncio.run(main())
