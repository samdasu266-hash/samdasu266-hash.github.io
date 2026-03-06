import os
import json
import asyncio
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore # 구글 전용 도구를 직접 꺼냄
from playwright.async_api import async_playwright

# 1. Firebase 인증 (GitHub Secrets에서 가져옴)
firebase_json = os.environ.get('FIREBASE_CONFIG_JSON')
if not firebase_json:
    print("Error: FIREBASE_CONFIG_JSON 설정 없음")
    exit(1)

cred = credentials.Certificate(json.loads(firebase_json))
if not firebase_admin._apps:
    # 'projectId'를 직접 적어줘서 로봇이 엉뚱한 곳으로 가지 못하게 못박았습니다.
    firebase_admin.initialize_app(cred, {
        'projectId': 'get-out-from-hospital'
    })
cred_dict = json.loads(firebase_json)
project_id = cred_dict.get('project_id')
db = firestore.Client(project=project_id, database='default')
APP_ID = "recruitment-portal-v3"

async def scrape_site(browser, inst_id, url):
    # 한국 윈도우 사용자의 크롬 브라우저로 완벽하게 위장합니다
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        locale="ko-KR",
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"}
    )
    
    try:
        print(f"[{inst_id}] 사이트 뚫는 중...")
        # 사이트가 완전히 켜질 때까지 충분히 기다립니다 (보안 프로그램 우회 목적)
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8) 
        
        found_jobs = []
        
        # [만능 치트키] HTML 구조를 무시하고, 화면의 모든 제목과 링크를 쓸어 담습니다.
        elements = await page.query_selector_all("a, td.subject, div.tit, span.title, td.title")
        
        for el in elements:
            try:
                text = (await el.inner_text()).strip()
                # 텍스트가 너무 짧은 건 메뉴 이름이므로 무시
                if len(text) < 8: 
                    continue
                    
                # 공고 제목에 무조건 들어가는 핵심 키워드로 사냥
                keywords = ["채용", "공고", "모집", "예고", "안내", "신규직원", "채용계획", "임용"]
                if any(kw in text for kw in keywords):
                    
                    # 링크 추출
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
        
        # 중복된 제목 제거
        unique_jobs = []
        seen_titles = set()
        for job in found_jobs:
            if job['title'] not in seen_titles:
                unique_jobs.append(job)
                seen_titles.add(job['title'])
                
        print(f"[{inst_id}] 수집 성공! {len(unique_jobs)}건 발견")
        return unique_jobs[:10] # 너무 많으면 최신 10개만 자르기
        
    except Exception as e:
        print(f"[{inst_id}] 접속 차단됨 또는 에러: {e}")
        return []
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        # 봇 탐지기를 피하기 위한 특수 설정 (로봇이 아닌 척)
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
            jobs_path = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('jobs')
            
            for i, job in enumerate(all_collected_jobs):
                doc_ref = jobs_path.document(f"job_{i}")
                batch.set(doc_ref, job)
            
            meta_ref = db.collection('artifacts').document(APP_ID).collection('public').document('data').collection('metadata').document('sync')
            batch.set(meta_ref, {"lastSync": datetime.now().isoformat()})
            
            batch.commit()
            print(f"🎉 성공! 총 {len(all_collected_jobs)}개의 공고 창고에 저장 완료!")
        else:
            print("수집된 공고가 0개입니다. (여전히 차단되었거나 정말 공고가 없을 수 있습니다.)")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())





