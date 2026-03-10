import os
import json
import asyncio
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore  # 🔥 구글 클라우드 대신 파이어베이스 전용 모듈 사용
from playwright.async_api import async_playwright

# 1. Firebase 인증 (표준 방식)
firebase_json = os.environ.get('FIREBASE_CONFIG_JSON')
if not firebase_json:
    print("Error: FIREBASE_CONFIG_JSON 설정 없음")
    exit(1)

cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# 2. 길을 잃지 않는 가장 안전한 DB 연결 방식
db = firestore.client()

APP_ID = "recruitment-portal-v3"

async def scrape_site(browser, inst_id, url):
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR",
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"}
    )
    
    try:
        print(f"[{inst_id}] 사이트 뚫는 중...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8) 
        
        found_jobs = []
        elements = await page.query_selector_all("a, td.subject, div.tit, span.title, td.title")
        
        for el in elements:
            try:
                text = (await el.inner_text()).strip()
                if len(text) < 8: 
                    continue
                    
                keywords = ["채용", "공고", "모집", "예고", "안내", "신규직원", "채용계획", "임용"]
                if any(kw in text for kw in keywords):
                    href = url
                    if await el.evaluate("node => node.tagName") == "A":
                        raw_href = await el.get_attribute("href")
                        if raw_href and raw_href.startswith("http"):
                            href = raw_href
                        elif raw_href and raw_href.startswith("/"):
                            base = url.split("/")[0] + "//" + url.split("/")[2]
                            href = base + raw_href
                            
                    found_jobs.append({
                        "instId": inst_id,
                        "title": text,
                        "postedDate": datetime.now().strftime("%Y-%m-%d"),
                        "endDate": "상세 모집요강 참조",
                        "type": "채용공고",
                        "link": href
                    })
            except:
                continue
        
        unique_jobs = []
        seen_titles = set()
        for job in found_jobs:
            if job['title'] not in seen_titles:
                unique_jobs.append(job)
                seen_titles.add(job['title'])
                
        print(f"[{inst_id}] 수집 성공! {len(unique_jobs)}건 발견")
        return unique_jobs[:10]
        
    except Exception as e:
        print(f"[{inst_id}] 접속 차단됨 또는 에러: {e}")
        return []
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        
        targets = [
            {"id": "hira", "url": "https://hira.recruitlab.co.kr/app/recruitment-announcement/list"},
            {"id": "nhis", "url": "https://nhis.kpcice.kr/Include/PackageAppo.html?rRound=1"},
            {"id": "neca", "url": "https://neca.applyin.co.kr/jobs/"},
            {"id": "kuksiwon", "url": "https://dware.intojob.co.kr/main/kuksiwon.jsp"},
            {"id": "koiha", "url": "https://koiha.recruiter.co.kr/career/job"}
        ]
        
        all_collected_jobs = []
        for target in targets:
            jobs = await scrape_site(browser, target['id'], target['url'])
            all_collected_jobs.extend(jobs)
        
        if all_collected_jobs:
            batch = db.batch()
            # 웹사이트가 바라보는 정확한 경로
            jobs_path = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('jobs')
            
            for i, job in enumerate(all_collected_jobs):
                doc_ref = jobs_path.document(f"job_{i}")
                batch.set(doc_ref, job)
            
            meta_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('metadata').document('sync')
            batch.set(meta_ref, {"lastSync": datetime.now().isoformat()})
            
            batch.commit()
            print(f"🎉 성공! 총 {len(all_collected_jobs)}개의 공고 창고에 저장 완료!")
        else:
            print("수집된 공고가 0개입니다.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
