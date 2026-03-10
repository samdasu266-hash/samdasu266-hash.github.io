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

# 🔥 한국 시간 고정
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
        today = now.date()

        for row in rows:
            try:
                row_text = (await row.inner_text()).strip()
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A": link_el = row
                    else: continue
                        
                title = (await link_el.inner_text()).strip()
                if len(title) < 5: continue

                # 채용/공고 단어 필수 필터
                if "채용" not in title and "공고" not in title:
                    continue

                # 제외 단어
                exclude_words = ["의사", "의무직", "진료직", "합격자", "변호사"]
                if any(ex in title for ex in exclude_words):
                    continue

                href = url
                raw_href = await link_el.get_attribute("href")
                if raw_href:
                    if raw_href.startswith("http"): href = raw_href
                    elif raw_href.startswith("/"): href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href

                # 날짜 추출
                date_matches = re.findall(r'20\d{2}\s*[-./]\s*\d{2}\s*[-./]\s*\d{2}', row_text)
                posted_date_str = now.strftime("%Y-%m-%d")
                end_date_str = "상세참조"
                status = "진행중" # 기본값
                
                if date_matches:
                    parsed = [d.replace(' ', '').replace('.', '-').replace('/', '-') for d in date_matches]
                    posted_date_str = parsed[0]
                    
                    # 마감일이 존재할 경우 비교 로직
                    if len(parsed) >= 2: 
                        end_date_str = parsed[1]
                        try:
                            end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                            if today > end_date_obj:
                                status = "마감"
                        except:
                            pass
                
                found_jobs.append({
                    "instId": inst_id,
                    "title": title.replace("새글", "").strip(),
                    "postedDate": posted_date_str,
                    "endDate": end_date_str,
                    "status": status, # 🔥 진행중 또는 마감 상태 추가
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
            {"id": "redcross", "url": "https://www.redcross.or.kr/recruit/"}
        ]
        
        all_jobs = []
        for t in targets:
            all_jobs.extend(await scrape_site(browser, t['id'], t['url']))
        
        if all_jobs:
            batch = db.batch()
            jobs_path = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('jobs')
            
            # 기존 데이터 삭제
            for doc in jobs_path.get():
                batch.delete(doc.reference)
            
            # 새 데이터 저장
            for i, job in enumerate(all_jobs):
                batch.set(jobs_path.document(f"job_{i}"), job)
            
            meta_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('metadata').document('sync')
            batch.set(meta_ref, {"lastSync": datetime.now(KST).isoformat()})
            batch.commit()
            print(f"완료: {len(all_jobs)}개 저장")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

