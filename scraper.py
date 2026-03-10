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

                # 🔥 1. 제목에 포함된 지저분한 기간 날짜 텍스트 완벽 제거 
                # (예: 2026-01-21(수) 17:00 ~ 2026-02-04(수) 18:00 패턴을 통째로 날림)
                clean_title = re.sub(r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*', '', raw_title).strip()

                # 🔥 2. "채용" 과 "공고" 두 단어가 무조건 모두(AND) 있어야만 통과
                if "채용" not in clean_title or "공고" not in clean_title:
                    continue

                # 🔥 3. 제외 단어 중 하나라도 있으면 즉시 버림 (OR 조건)
                exclude_words = ["발표", "변호사", "합격자", "면접", "약사", "약무직", "의사", "의무직"]
                if any(ex in clean_title for ex in exclude_words):
                    continue

                # 🔥 4. 제목을 분석하여 고용 형태(정규직/비정규직 등) 자동 추출
                job_type = "정규직" # 안 적혀있으면 기본 정규직 간주
                if "무기계약직" in clean_title:
                    job_type = "무기계약직"
                elif "공무직" in clean_title:
                    job_type = "공무직"
                elif "기간제" in clean_title or "계약직" in clean_title or "촉탁직" in clean_title:
                    job_type = "계약직/기간제"
                elif "비정규직" in clean_title:
                    job_type = "비정규직"
                elif "인턴" in clean_title:
                    job_type = "인턴"

                href = url
                raw_href = await link_el.get_attribute("href")
                if raw_href:
                    if raw_href.startswith("http"): href = raw_href
                    elif raw_href.startswith("/"): href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href

                # 날짜 파싱 및 마감 상태 처리
                date_matches = re.findall(r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}', row_text)
                
                posted_date_str = now.strftime("%Y-%m-%d")
                end_date_str = "상세참조"
                status = "진행중"
                
                if date_matches:
                    parsed_dates = []
                    for d in date_matches:
                        clean_d = re.sub(r'\s+', '', d).replace('.', '-').replace('/', '-')
                        parts = clean_d.split('-')
                        if len(parts) == 3:
                            formatted_date = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                            parsed_dates.append(formatted_date)
                    
                    if parsed_dates:
                        posted_date_str = parsed_dates[0]
                        if len(parsed_dates) >= 2:
                            # 여러 날짜 중 마지막 날짜를 마감일로 판단
                            end_date_str = parsed_dates[-1]
                            try:
                                # 🔥 마감일 18:00 기준으로 현재 시간과 비교 (건보 상반기 종료 오류 해결)
                                end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(hours=18)
                                if now > end_date_obj:
                                    status = "마감"
                            except:
                                pass

                # 게시판 텍스트에 아예 '마감' 글자가 박혀있으면 강제 마감
                if "[마감]" in raw_title or "접수마감" in row_text or "접수종료" in row_text:
                    status = "마감"
                
                found_jobs.append({
                    "instId": inst_id,
                    "title": clean_title.replace("새글", "").replace("[마감]", "").strip(),
                    "postedDate": posted_date_str,
                    "endDate": end_date_str,
                    "status": status,
                    "jobType": job_type, # 데이터베이스에 직무 형태 저장
                    "link": href
                })
            except: continue
        
        # 중복 제목 제거
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
            print(f"성공: {len(all_jobs)}개의 공고 저장")
        else:
            print("수집된 공고가 0개입니다.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())


