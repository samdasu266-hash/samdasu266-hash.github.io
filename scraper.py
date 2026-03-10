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
    """ 본문 텍스트에서 연도가 생략된 날짜와 시간까지 모두 찾아내는 초정밀 판독기 """
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
        
        # 날짜 주변 25글자 이내에 HH:MM 형식의 시간이 있는지 탐색
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

        # 1차: 목록에서 기본 정보와 Javascript 접속 링크 수집
        for row in rows[:15]: 
            try:
                row_text = (await row.inner_text()).strip()
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A": link_el = row
                    else: continue
                        
                raw_title = (await link_el.inner_text()).strip()
                if len(raw_title) < 5: continue

                # 제목 청소 및 필터링
                clean_title = raw_title
                date_match = re.search(r'(?:(?:20)?\d{2}\s*[-./]\s*)?\d{1,2}\s*[-./]\s*\d{1,2}', clean_title)
                if date_match and date_match.start() > len(clean_title) / 2:
                    clean_title = clean_title[:date_match.start()]
                clean_title = re.sub(r'\[.*?\]', '', clean_title).replace('~', '').replace('새글', '').strip()
                clean_title = re.sub(r'\s+', ' ', clean_title)

                if "채용" not in clean_title or "공고" not in clean_title: continue

                exclude_words = ["발표", "변호사", "합격자", "면접", "약사", "약무직", "의사", "의무직", "사전공개", "채용계획", "계획", "안내"]
                if any(ex in clean_title for ex in exclude_words): continue

                job_type = "정규직"
                if "무기계약직" in clean_title: job_type = "무기계약직"
                elif "공무직" in clean_title: job_type = "공무직"
                elif "기간제" in clean_title or "계약직" in clean_title or "촉탁직" in clean_title: job_type = "계약직/기간제"
                elif "비정규직" in clean_title: job_type = "비정규직"
                elif "인턴" in clean_title: job_type = "인턴"

                raw_href = await link_el.get_attribute("href")
                if not raw_href or raw_href == "#": continue

                job_candidates.append({
                    "instId": inst_id,
                    "title": clean_title,
                    "raw_title": raw_title,
                    "row_text": row_text,
                    "jobType": job_type,
                    "raw_href": raw_href, # 본문 접속용 (Javascript 포함)
                    "base_url": url # 사용자 제공용 안전 링크
                })
            except: continue

        found_jobs = []
        
        # 🔥 2차: 딥 스크래핑 (본문 잠입 및 날짜 추출)
        for job in job_candidates:
            combined_text = job['raw_title'] + " " + job['row_text']
            href_val = job['raw_href']
            safe_link = job['base_url'] # 유저에게는 무조건 안전한 게시판 링크 제공

            try:
                # 🛡️ Javascript 링크인 경우 (건보 등) 가상 클릭으로 본문 진입
                if "javascript:" in href_val:
                    js_code = href_val.replace("javascript:", "")
                    detail_page = await browser.new_page()
                    await detail_page.goto(job['base_url'], wait_until="domcontentloaded", timeout=10000)
                    await detail_page.evaluate(js_code) # 스크립트 강제 실행
                    await detail_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    await asyncio.sleep(1.5)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " " + body_text
                    await detail_page.close()
                
                # 일반 HTTP 링크인 경우 직접 진입
                elif href_val.startswith("http") or href_val.startswith("/"):
                    if href_val.startswith("/"):
                        target_url = job['base_url'].split("/")[0] + "//" + job['base_url'].split("/")[2] + href_val
                    else:
                        target_url = href_val
                    safe_link = target_url # 일반 링크는 유저에게 직접 제공해도 안전함
                    
                    detail_page = await browser.new_page()
                    await detail_page.goto(target_url, wait_until="domcontentloaded", timeout=10000)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " " + body_text
                    await detail_page.close()
            except Exception as e:
                # 본문 접근 실패 시 목록 텍스트만 사용 (에러로 멈추지 않음)
                pass

            # 수집된 모든 텍스트에서 날짜 정밀 분석
            parsed_dates = extract_dates(combined_text, now.year)

            start_str, end_str = "상세참조", "상세참조"
            status = "진행중"
            is_too_old = False
            now_kst = now.replace(tzinfo=None)

            if len(parsed_dates) == 1:
                start_item = parsed_dates[0]
                if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                start_str = start_item['dt'].strftime("%y.%m.%d")
                
                if (now_kst - start_item['dt']).days > 30:
                    status = "마감"
                    is_too_old = True

            elif len(parsed_dates) >= 2:
                start_item = parsed_dates[0]
                end_item = parsed_dates[-1]
                
                if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                if not end_item['has_time']: end_item['dt'] = end_item['dt'].replace(hour=18, minute=0)
                    
                start_str = start_item['dt'].strftime("%y.%m.%d %H:%M")
                end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                
                # 마감일과 현재 시간 정밀 비교
                if now_kst > end_item['dt']: 
                    status = "마감"
                    if (now_kst - end_item['dt']).days > 30:
                        is_too_old = True

            # 대놓고 마감이라고 적힌 경우
            if "[마감]" in job['raw_title'] or "접수마감" in combined_text or "접수종료" in combined_text:
                status = "마감"
                if parsed_dates and (now_kst - parsed_dates[-1]['dt']).days > 30:
                    is_too_old = True

            # 30일 지난 공고 스킵
            if not is_too_old:
                found_jobs.append({
                    "instId": job['instId'],
                    "title": job['title'],
                    "startDate": start_str,
                    "endDate": end_str,
                    "status": status,
                    "jobType": job['jobType'],
                    "link": safe_link # 🔥 유저용 안전 링크 적용
                })
        
        # 중복 제거
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


