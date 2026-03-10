import os
import json
import asyncio
import re  # 🔥 텍스트에서 날짜를 찾아내기 위한 정규식 모듈 추가
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
        
        # 🔥 단순히 제목만 찾는게 아니라, 날짜/카테고리까지 다 읽기 위해 테이블의 한 '줄(Row)'을 통째로 가져옵니다.
        rows = await page.query_selector_all("tbody tr")
        # 만약 tr 형식이 아니라면, 리스트(li)나 카드(item) 형식으로도 찾아봅니다.
        if not rows or len(rows) < 2:
            rows = await page.query_selector_all(".board-list li, ul.list li, .recruitment-item, .item")
        # 그래도 못 찾으면 최후의 수단으로 제목을 가져옵니다.
        if not rows or len(rows) < 2:
            rows = await page.query_selector_all("a, td.subject, div.tit, span.title, td.title")
        
        now = datetime.now(KST)
        
        for row in rows:
            try:
                # 한 줄의 모든 글자를 싹 다 읽어옵니다.
                row_text = (await row.inner_text()).strip()
                if len(row_text) < 5: 
                    continue
                
                # 🔥 [요청 1] 건보(NHIS)인 경우, 글 안에 "채용 공고"라는 말이 없으면 수집 안 함!
                if inst_id == 'nhis':
                    if "채용공고" not in row_text.replace(" ", ""):
                        continue
                
                # 첨부파일 거르기!
                ban_words = [".hwp", ".hwpx", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", "첨부", "다운로드", "붙임", "file"]
                if any(ban in row_text.lower() for ban in ban_words):
                    continue
                    
                # 진짜 공고 키워드
                keywords = ["채용", "공고", "모집", "예고", "안내", "신규직원", "채용계획", "임용"]
                if not any(kw in row_text for kw in keywords):
                    continue
                
                # 그 줄 안에 있는 링크(a 태그) 찾기
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A":
                        link_el = row
                    else:
                        continue
                        
                title = (await link_el.inner_text()).strip()
                if len(title) < 5: continue
                
                href = url
                raw_href = await link_el.get_attribute("href")
                if raw_href:
                    if raw_href.startswith("http"): href = raw_href
                    elif raw_href.startswith("/"): href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href
                    elif raw_href.startswith("javascript"): href = url
                    
                # 🔥 [요청 3] 날짜 및 접수기간 자동 추출기
                # "2026.03.10" 혹은 "2026-03-10" 등의 패턴을 모두 찾아냅니다.
                date_matches = re.findall(r'20\d{2}[-./]\d{2}[-./]\d{2}', row_text)
                
                posted_date_str = now.strftime("%Y-%m-%d")
                end_date_str = "상세 모집요강 참조"
                is_too_old = False
                
                # 날짜를 발견했다면?
                if date_matches:
                    # 표기법을 통일 (예: 2026.03.10 -> 2026-03-10)
                    parsed_dates = [d.replace('.', '-').replace('/', '-') for d in date_matches]
                    
                    # 가장 첫 번째 날짜를 '작성일'로 설정
                    posted_date_str = parsed_dates[0]
                    posted_date_obj = datetime.strptime(posted_date_str, "%Y-%m-%d").replace(tzinfo=KST)
                    
                    # 🔥 [요청 2] 1달(30일) 이상 경과된 공고는 패스!
                    if (now - posted_date_obj).days > 30:
                        is_too_old = True
                        
                    # 만약 날짜가 2개 이상 있다면, 두 번째 날짜를 '마감일'로 꽂아줍니다!
                    if len(parsed_dates) >= 2:
                        end_date_str = parsed_dates[1]
                
                # 1달 넘은 낡은 공고면 리스트에 넣지 않고 스킵합니다.
                if is_too_old:
                    continue
                            
                found_jobs.append({
                    "instId": inst_id,
                    "title": title,
                    "postedDate": posted_date_str,  # 추출한 진짜 작성일
                    "endDate": end_date_str,        # 추출한 진짜 마감일
                    "type": "채용공고",
                    "link": href
                })
            except Exception as e:
                continue
        
        # 중복 제목 제거
        unique_jobs = []
        seen_titles = set()
        for job in found_jobs:
            if job['title'] not in seen_titles:
                unique_jobs.append(job)
                seen_titles.add(job['title'])
                
        print(f"[{inst_id}] 수집 성공! 첨부파일/과거공고 제외 {len(unique_jobs)}건 발견")
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
            # 한국 시간으로 동기화 시간 정확히 기록
            batch.set(meta_ref, {"lastSync": datetime.now(KST).isoformat()})
            
            batch.commit()
            print(f"🎉 성공! 깔끔하게 정제된 총 {len(all_collected_jobs)}개의 공고 저장 완료!")
        else:
            print("수집된 공고가 0개입니다.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
