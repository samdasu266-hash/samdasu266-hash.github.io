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
        locale="ko-KR",
        extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"}
    )
    
    try:
        print(f"[{inst_id}] 사이트 접속 중: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8) 
        
        found_jobs = []
        
        rows = await page.query_selector_all("tbody tr")
        if not rows or len(rows) < 2:
            rows = await page.query_selector_all(".board-list li, ul.list li, .recruitment-item, .item")
        if not rows or len(rows) < 2:
            rows = await page.query_selector_all("a, td.subject, div.tit, span.title, td.title")
        
        now = datetime.now(KST)
        
        for row in rows:
            try:
                row_text = (await row.inner_text()).strip()
                if len(row_text) < 5: 
                    continue
                
                link_el = await row.query_selector("a")
                if not link_el:
                    if await row.evaluate("node => node.tagName") == "A":
                        link_el = row
                    else:
                        continue
                        
                title = (await link_el.inner_text()).strip()
                if len(title) < 5: continue

                # 🔥 [건보공단 & 연금공단 필터] "채용공고"가 없으면 패스
                if inst_id in ['nhis', 'nps']:
                    if "채용" not in row_text.replace(" ", ""):
                        continue
                
                # 🔥 [보건복지부 중복 방지 필터] 기존 5대 기관 이름이 제목에 있으면 스킵!
                if inst_id == 'mohw':
                    overlap_keywords = ['건강보험', '건보', '심사평가원', '심평원', '보건의료연구원', '보의연', '국가시험원', '국시원', '의료기관평가인증원', '인증원', '국민연금']
                    if any(overlap in title for overlap in overlap_keywords):
                        continue

                # 첨부파일 거르기는 "제목(title)"에만 적용
                ban_words = [".hwp", ".hwpx", ".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", "첨부", "다운로드", "붙임", "file"]
                if any(ban in title.lower() for ban in ban_words):
                    continue
                    
                keywords = ["채용", "공고", "모집", "예고", "안내", "신규직원", "채용계획", "임용"]
                if not any(kw in title for kw in keywords):
                    continue
                
                href = url
                raw_href = await link_el.get_attribute("href")
                if raw_href:
                    if raw_href.startswith("http"): href = raw_href
                    elif raw_href.startswith("/"): href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href
                    elif raw_href.startswith("javascript"): href = url
                    
                # 날짜 및 기간 추출기
                date_matches = re.findall(r'20\d{2}\s*[-./]\s*\d{2}\s*[-./]\s*\d{2}', row_text)
                
                posted_date_str = now.strftime("%Y-%m-%d")
                end_date_str = "상세 모집요강 참조"
                is_too_old = False
                
                if date_matches:
                    parsed_dates = [d.replace(' ', '').replace('.', '-').replace('/', '-') for d in date_matches]
                    posted_date_str = parsed_dates[0]
                    
                    try:
                        posted_date_obj = datetime.strptime(posted_date_str, "%Y-%m-%d").replace(tzinfo=KST)
                        # 30일 초과된 공고 제외
                        if (now - posted_date_obj).days > 30:
                            is_too_old = True
                    except:
                        pass
                        
                    if len(parsed_dates) >= 2:
                        end_date_str = parsed_dates[1]
                
                if is_too_old:
                    continue
                            
                found_jobs.append({
                    "instId": inst_id,
                    "title": title,
                    "postedDate": posted_date_str,
                    "endDate": end_date_str,
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
                
        print(f"[{inst_id}] 수집 성공! 총 {len(unique_jobs)}건 발견")
        return unique_jobs[:10]
        
    except Exception as e:
        print(f"[{inst_id}] 접속 에러: {e}")
        return []
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        
        # 🔥 국민연금(nps) 및 보건복지부(mohw) 타겟 추가!
        targets = [
            {"id": "hira", "url": "https://hira.recruitlab.co.kr/app/recruitment-announcement/list"},
            {"id": "nhis", "url": "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"},
            {"id": "neca", "url": "https://www.neca.re.kr/lay1/program/S1T207C209/people/index.do"},
            {"id": "kuksiwon", "url": "https://dware.intojob.co.kr/main/kuksiwon.jsp"},
            {"id": "koiha", "url": "https://koiha.recruiter.co.kr/career/job"},
            {"id": "nps", "url": "https://www.nps.or.kr/pnsgdnc/hiregdnc/getOHAE0004M0List.do"},
            {"id": "mohw", "url": "https://www.mohw.go.kr/board.es?mid=a10501010400&bid=0003"}
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
            batch.set(meta_ref, {"lastSync": datetime.now(KST).isoformat()})
            
            batch.commit()
            print(f"🎉 성공! 깔끔하게 정제된 총 {len(all_collected_jobs)}개의 공고 저장 완료!")
        else:
            print("수집된 공고가 0개입니다.")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
