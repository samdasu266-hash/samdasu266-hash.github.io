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

# 한국 시간 고정
KST = timezone(timedelta(hours=9))

async def scrape_site(browser, inst_id, url):
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR"
    )
    
    try:
        print(f"[{inst_id}] 접속 중: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8) 
        
        found_jobs = []
        rows = await page.query_selector_all("tbody tr, .board-list li, ul.list li, .recruitment-item")
        if not rows: rows = await page.query_selector_all("a")

        now = datetime.now(KST)

        for row in rows:
            try:
                row_text = (await row.inner_text()).strip()
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A": link_el = row
                    else: continue
                        
                raw_title = (await link_el.inner_text()).strip()
                if len(raw_title) < 5: continue

                # 🔥 1. 제목 청소 (날짜부터 시작하는 뒷부분 문자열을 싹 다 날림)
                # EX: "자동차보험촉탁심사위원(전문계약직) 채용 2026-01-21(수)..." -> "자동차보험촉탁심사위원(전문계약직) 채용"
                clean_title = re.sub(r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*', '', raw_title)
                clean_title = clean_title.replace('~', '').replace('[마감]', '').replace('새글', '').strip()
                clean_title = re.sub(r'\s+', ' ', clean_title) # 불필요한 다중 공백 제거

                # 🔥 2. 필수 단어 필터 (AND 조건: "채용"과 "공고" 무조건 둘 다 있어야 함)
                if "채용" not in clean_title or "공고" not in clean_title:
                    continue

                # 🔥 3. 제외 단어 필터 (OR 조건: 하나라도 있으면 즉시 버림)
                # "사전공개", "계획" 추가하여 '채용계획 사전공개' 원천 차단
                exclude_words = ["발표", "변호사", "합격자", "면접", "약사", "약무직", "의사", "의무직", "사전공개", "채용계획", "계획"]
                if any(ex in clean_title for ex in exclude_words):
                    continue

                # 고용 형태 추출
                job_type = "정규직"
                if "무기계약직" in clean_title: job_type = "무기계약직"
                elif "공무직" in clean_title: job_type = "공무직"
                elif "기간제" in clean_title or "계약직" in clean_title or "촉탁직" in clean_title: job_type = "계약직/기간제"
                elif "비정규직" in clean_title: job_type = "비정규직"
                elif "인턴" in clean_title: job_type = "인턴"

                href = url
                raw_href = await link_el.get_attribute("href")
                if raw_href and raw_href != "#" and not raw_href.startswith("javascript:"):
                    if raw_href.startswith("http"): href = raw_href
                    elif raw_href.startswith("/"): href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href
                    else: href = url.rsplit("/", 1)[0] + "/" + raw_href

                # 🔥 4. 날짜 및 시간(HH:MM) 초정밀 추출기
                combined_text = raw_title + " " + row_text
                # 패턴: 2026.01.21 (수) 17:00 형태까지 모두 인식
                pattern = r'(20\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})(?:\s*(?:\([가-힣]\))?\s*(\d{1,2}:\d{2}))?'
                matches = re.findall(pattern, combined_text)
                
                start_str = "상세참조"
                end_str = "상세참조"
                status = "진행중"
                
                if matches:
                    parsed_dates = []
                    for m in matches:
                        try:
                            y, mo, d, t = m
                            has_time = bool(t)
                            hour, minute = 0, 0
                            if has_time:
                                hour, minute = map(int, t.split(':'))
                                if hour >= 24: hour, minute = 23, 59 # 24:00 표기 오류 방지
                            dt_obj = datetime(int(y), int(mo), int(d), hour, minute)
                            parsed_dates.append({'dt': dt_obj, 'has_time': has_time})
                        except:
                            continue
                    
                    if parsed_dates:
                        parsed_dates.sort(key=lambda x: x['dt']) # 날짜순 정렬
                        
                        # 날짜가 1개만 있으면 '마감일'로 간주
                        if len(parsed_dates) == 1:
                            end_item = parsed_dates[0]
                            if not end_item['has_time']: 
                                end_item['dt'] = end_item['dt'].replace(hour=18, minute=0) # 시간 없으면 18:00 마감 간주
                            
                            start_str = "상세참조"
                            end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                            
                            # 현재 시간(KST)과 마감 시간 정밀 비교
                            now_kst = now.replace(tzinfo=None)
                            if now_kst > end_item['dt']: status = "마감"
                            
                        # 날짜가 2개 이상이면 첫 날짜를 '시작일', 마지막 날짜를 '마감일'로 간주
                        elif len(parsed_dates) >= 2:
                            start_item = parsed_dates[0]
                            end_item = parsed_dates[-1]
                            
                            if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                            if not end_item['has_time']: end_item['dt'] = end_item['dt'].replace(hour=18, minute=0)
                                
                            start_str = start_item['dt'].strftime("%y.%m.%d %H:%M")
                            end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                            
                            # 현재 시간(KST)과 마감 시간 정밀 비교
                            now_kst = now.replace(tzinfo=None)
                            if now_kst > end_item['dt']: status = "마감"

                # 텍스트 자체에 마감이라고 박혀있으면 강제 마감
                if "[마감]" in raw_title or "접수마감" in row_text or "접수종료" in row_text:
                    status = "마감"
                
                found_jobs.append({
                    "instId": inst_id,
                    "title": clean_title,
                    "startDate": start_str, # 게시일 대신 시작일 저장
                    "endDate": end_str,
                    "status": status,
                    "jobType": job_type,
                    "link": href
                })
            except: continue
        
        unique_jobs = []
        seen = set()
        for job in found_jobs:
            c = job['title'].replace(" ", "")
            if c not in seen:
                unique_jobs.append(job)
                seen.add(c)
        return unique_jobs[:10]
    except Exception as e:
        print(f"Error: {e}")
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
            print(f"성공: {len(all_jobs)}개의 공고 저장 완료")
        else:
            print("수집된 공고가 0개입니다.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())


