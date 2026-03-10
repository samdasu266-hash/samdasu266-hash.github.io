import os
import json
import asyncio
# 🔥 한국 시간(KST)을 맞추기 위해 timedelta, timezone 추가
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

# 🔥 로봇 시계를 무조건 한국 시간(UTC+9)으로 강제 고정
KST = timezone(timedelta(hours=9))

async def scrape_site(browser, inst_id, url):
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR",
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"}
    )
    
    try:
        print(f"[{inst_id}] 사이트 접속 중: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8) 
        
        found_jobs = []
        elements = await page.query_selector_all("a, td.subject, div.tit, span.title, td.title")
        
        for el in elements:
            try:
                text = (await el.inner_text()).strip()
                # 텍스트가 너무 짧으면 무시
                if len(text) < 8: 
                    continue
                
                # 첨부파일 거르기!
                ban_words = [".hwp", ".hwpx", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", "첨부", "다운로드", "붙임", "file"]
                if any(ban in text.lower() for ban in ban_words):
                    continue
                    
                # 진짜 공고 키워드
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
                        elif raw_href and raw_href.startswith("javascript"):
                            href = url
                            
                    found_jobs.append({
                        "instId": inst_id,
                        "title": text,
                        # 🔥 한국 시간으로 날짜 기록
                        "postedDate": datetime.now(KST).strftime("%Y-%m-%d"),
                        "endDate": "상세 모집요강 참조",
                        "type": "채용공고",
                        "link": href
                    })
            except:
                continue
        
        # 중복 제목 제거
        unique_jobs = []
        seen_titles = set()
        for job in found_jobs:
            if job['title'] not in seen_titles:
                unique_jobs.append(job)
                seen_titles.add(job['title'])
                
        print(f"[{inst_id}] 수집 성공! 첨부파일 제외 {len(unique_jobs)}건 발견")
        return unique_jobs[:10]
        
    except Exception as e:
        print(f"[{inst_id}] 접속 에러: {e}")
        return []
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        
        targets = [
            {"id": "hira", "url": "https://hira.recruitlab.co.kr/app/recruitment-announcement/list"},
            {"id": "nhis", "url": "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"},
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
            jobs_path = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('jobs')
            
            for i, job in enumerate(all_collected_jobs):
                doc_ref = jobs_path.document(f"job_{i}")
                batch.set(doc_ref, job)
            
            meta_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('metadata').document('sync')
            # 🔥 한국 시간으로 동기화 시간 정확히 기록
            batch.set(meta_ref, {"lastSync": datetime.now(KST).isoformat()})
            
            batch.commit()
            print(f"🎉 성공! 깔끔하게 정제된 총 {len(all_collected_jobs)}개의 공고 저장 완료!")
        else:
            print("수집된 공고가 0개입니다.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
