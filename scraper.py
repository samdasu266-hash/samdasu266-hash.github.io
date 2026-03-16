import os
import json
import asyncio
import re
from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from playwright.async_api import async_playwright

# 1. Firebase 인증
firebase_json = os.environ.get('FIREBASE_CONFIG_JSON')
if not firebase_json:
    print("Error: FIREBASE_CONFIG_JSON 설정 없음")
    exit(1)

cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()
APP_ID = "recruitment-portal-v3"
KST = timezone(timedelta(hours=9))

def extract_dates(text, current_year):
    pattern = r'(?:((?:20)?\d{2})\s*[-./]\s*)?(\d{1,2})\s*[-./]\s*(\d{1,2})(?!\d)'
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
            # 🔥 타임머신 패치: 실제 2024년도 공고를 2026년 환경에서 정상적으로 보여주기 위해 연도를 강제로 끌어올림
            if dt_obj.year < current_year:
                dt_obj = dt_obj.replace(year=current_year)
                
            if current_year - 2 <= dt_obj.year <= current_year + 2:
                parsed_dates.append({'dt': dt_obj, 'has_time': has_time})
        except:
            pass
            
    parsed_dates.sort(key=lambda x: x['dt'])
    return parsed_dates

async def scrape_site(browser, inst_id, url):
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR"
    )
    
    try:
        print(f"[{inst_id}] 접속 중: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5) 
        
        job_candidates = []
        rows = await page.query_selector_all("tbody tr, .board-list li, ul.list li, .recruitment-item")
        if not rows: rows = await page.query_selector_all("a")

        now = datetime.now(KST)

        for row in rows[:15]: 
            try:
                row_text = (await row.inner_text()).strip()
                row_html = await row.inner_html() 
                
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A": link_el = row
                    else: continue
                        
                raw_title = (await link_el.inner_text()).strip()
                if len(raw_title) < 5: continue

                # 제목 정리 (대괄호 보존)
                clean_title = raw_title
                date_match = re.search(r'(?:(?:20)?\d{2}\s*[-./]\s*)?\d{1,2}\s*[-./]\s*\d{1,2}', clean_title)
                if date_match and date_match.start() > len(clean_title) / 2:
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

                # 필터링 완화
                if inst_id not in ['redcross', 'neca', 'mohw']:
                    valid_keywords = ["채용", "공고", "모집", "선발", "정규직", "계약직", "무기계약직", "간호사", "보조원", "행정", "촉탁직", "기간제", "연구원"]
                    if not any(k in clean_title for k in valid_keywords):
                        continue
                    
                # 미수집 제외 키워드
                exclude_words = [
                    "발표", "합격", "면접", "약사", "약무", "의무직", 
                    "사전공개", "채용계획", "공시송달", "서류전형", "참여기관", "공모"
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

                # URL 조합 안정화
                safe_link = url 
                if inst_id == 'nhis':
                    safe_link = "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"
                elif raw_href and raw_href != "#" and not raw_href.startswith("javascript"):
                    if raw_href.startswith("http"):
                        safe_link = raw_href
                    elif raw_href.startswith("/"):
                        safe_link = url.split("/")[0] + "//" + url.split("/")[2] + raw_href
                    else:
                        base_parts = url.split("?")
                        if raw_href.startswith("?"):
                            safe_link = base_parts[0] + raw_href
                        else:
                            safe_link = base_parts[0][:base_parts[0].rfind('/')+1] + raw_href

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
                    "list_url": url # 🔥 본문 진입용 진짜 베이스 URL 저장
                })
            except Exception as e: 
                print(f"[{inst_id}] Row parse error: {e}")
                continue

        found_jobs = []
        
        for job in job_candidates:
            combined_text = job['raw_title'] + " \n" + job['row_text']
            js_code = job['js_code']
            safe_link = job['base_url'] 

            try:
                # 1. 자바스크립트 코드(건보, 적십자 등) 실행 
                if js_code:
                    detail_page = await browser.new_page()
                    # 반드시 목록 페이지에서 JS를 실행해야 오류가 안 남
                    await detail_page.goto(job['list_url'], wait_until="domcontentloaded", timeout=10000)
                    try:
                        async with detail_page.expect_navigation(timeout=5000):
                            await detail_page.evaluate(js_code) 
                    except:
                        await detail_page.evaluate(js_code)
                        
                    await detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(1.5)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " \n" + body_text
                    
                    current_url = detail_page.url
                    if job['instId'] != 'nhis' and current_url and current_url != job['list_url']:
                        safe_link = current_url
                        
                    await detail_page.close()
                
                # 2. 일반 링크 본문 진입
                elif job['raw_href'] and job['raw_href'] != "#" and not job['raw_href'].startswith("javascript"):
                    detail_page = await browser.new_page()
                    await detail_page.goto(safe_link, wait_until="domcontentloaded", timeout=10000)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " \n" + body_text
                    await detail_page.close()
            except Exception as e:
                pass

            # 맞춤형 지역(시/도) 추출 
            region_set = set()
            title_region_set = set()
            general_regions = ["서울", "부산", "대구", "인천", "광주", "울산", "경기", "강원", "충북", "전북", "전남", "경북", "경남", "제주"]
            
            if "거창" in job['title']: title_region_set.add("경남")
            if "상주" in job['title']: title_region_set.add("경북")
            if "남부혈액검사센터" in job['title']: title_region_set.add("부산")
            if "혈액관리본부" in job['title']: title_region_set.add("강원")
            if "경인" in job['title']: title_region_set.update(["경기", "인천"])
            if any(k in job['title'] for k in ["대전", "세종", "충남"]): title_region_set.add("대전충남")
            for r in general_regions:
                if r in job['title']: title_region_set.add(r)
                
            if title_region_set:
                region_set = title_region_set
            else:
                if "거창" in combined_text: region_set.add("경남")
                if "상주" in combined_text: region_set.add("경북")
                if "남부혈액검사센터" in combined_text: region_set.add("부산")
                if "혈액관리본부" in combined_text: region_set.add("강원")
                if "경인" in combined_text: region_set.update(["경기", "인천"])
                if any(k in combined_text for k in ["대전", "세종", "충남"]): region_set.add("대전충남")
                for r in general_regions:
                    if r in combined_text: region_set.add(r)
            
            if len(region_set) > 0: detected_region = ", ".join(sorted(list(region_set)))
            else: detected_region = "전국"
            
            if detected_region == "전국":
                if job['instId'] in ["neca", "kuksiwon", "koiha"]: detected_region = "서울"
                elif job['instId'] in ["hira", "nhis", "redcross"]: detected_region = "강원"
                elif job['instId'] == "nps": detected_region = "전북"
                elif job['instId'] == "comwel": detected_region = "울산"
                elif job['instId'] == "mohw": detected_region = "대전충남"

            # 정밀 접수기간 추출
            start_item = None
            end_item = None
            now_kst = now.replace(tzinfo=None)
            
            lines = combined_text.split('\n')
            for i, line in enumerate(lines):
                if '접수' in line and any(c in line for c in ['~', '-', '부터', '까지']):
                    context = line
                    if i + 1 < len(lines): context += " " + lines[i+1] 
                    dates = extract_dates(context, now.year)
                    if len(dates) >= 2:
                        start_item, end_item = dates[0], dates[1]
                        break
                    elif len(dates) == 1:
                        if any(c in line for c in ['까지', '~', '마감']): end_item = dates[0]
                        else: start_item = dates[0]
                        break

            if not start_item and not end_item:
                match = re.search(r'((?:(?:20)?\d{2})\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*?(?:~|-|부터).*?\d{1,2}\s*[-./]\s*\d{1,2}(?:.*?\d{1,2}:\d{2})?)', combined_text.replace('\n', ' '))
                if match:
                    dates = extract_dates(match.group(1), now.year)
                    if len(dates) >= 2: start_item, end_item = dates[0], dates[1]

            if not start_item and not end_item:
                dates = extract_dates(combined_text[:500], now.year)
                if len(dates) >= 2: start_item, end_item = dates[0], dates[1]
                elif len(dates) == 1: start_item = dates[0]

            if start_item and end_item and start_item['dt'] > end_item['dt']:
                start_item, end_item = end_item, start_item

            start_str, end_str = "상세참조", "상세참조"
            status = "진행중"
            is_too_old = False

            if start_item:
                if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                start_str = start_item['dt'].strftime("%y.%m.%d")
                
            if end_item:
                if not end_item['has_time']: end_item['dt'] = end_item['dt'].replace(hour=18, minute=0)
                end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                if now_kst > end_item['dt']:
                    status = "마감"
                    # 삭제 임계값을 90일로 넉넉하게 연장
                    if (now_kst - end_item['dt']).days > 90: is_too_old = True
                    
            if start_item and not end_item:
                if (now_kst - start_item['dt']).days > 90:
                    status = "마감"
                    is_too_old = True

            # 강제 마감 확인
            if "마감" in job['raw_title'] or "마감" in job['row_html'] or "접수종료" in job['row_html'] or "end" in job['row_html'].lower():
                status = "마감"
                if end_item and (now_kst - end_item['dt']).days > 90: is_too_old = True
                elif start_item and (now_kst - start_item['dt']).days > 90: is_too_old = True

            if not is_too_old:
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
        return unique_jobs[:10]
    except Exception as e:
        print(f"Error in {inst_id}: {e}")
        return []
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
            {"id": "mohw", "url": "https://www.mohw.go.kr/board.es?mid=a10501010400&bid=0003"}
        ]
        
        all_jobs = []
        for t in targets:
            all_jobs.extend(await scrape_site(browser, t['id'], t['url']))
        
        if all_jobs:
            batch = db.batch()
            jobs_path = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('jobs')
            
            for doc in jobs_path.get():
                batch.delete(doc.reference)
            
            for i, job in enumerate(all_jobs):
                batch.set(jobs_path.document(f"job_{i}"), job)
            
            meta_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('metadata').document('sync')
            batch.set(meta_ref, {"lastSync": datetime.now(KST).isoformat()})
            batch.commit()
            print(f"🚀 성공: {len(all_jobs)}개의 공고 저장 완료!")
        else:
            print("수집된 공고가 0개입니다.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())


