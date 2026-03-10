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
        await asyncio.sleep(5) 
        
        found_jobs = []
        rows = await page.query_selector_all("tbody tr, .board-list li, ul.list li, .recruitment-item")
        if not rows: rows = await page.query_selector_all("a")

        now = datetime.now(KST)
        base_url = url.split("?")[0] # URL 파라미터 제거한 기본 주소

        # 목록에서 최대 10개까지만 먼저 추출
        job_candidates = []
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
                clean_title = re.sub(r'20\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}.*', '', raw_title)
                clean_title = clean_title.replace('~', '').replace('[마감]', '').replace('새글', '').strip()
                clean_title = re.sub(r'\s+', ' ', clean_title) 

                if "채용" not in clean_title or "공고" not in clean_title:
                    continue

                exclude_words = ["발표", "변호사", "합격자", "면접", "약사", "약무직", "의사", "의무직", "사전공개", "채용계획", "계획", "안내"]
                if any(ex in clean_title for ex in exclude_words):
                    continue

                # 고용 형태 추출
                job_type = "정규직"
                if "무기계약직" in clean_title: job_type = "무기계약직"
                elif "공무직" in clean_title: job_type = "공무직"
                elif "기간제" in clean_title or "계약직" in clean_title or "촉탁직" in clean_title: job_type = "계약직/기간제"
                elif "비정규직" in clean_title: job_type = "비정규직"
                elif "인턴" in clean_title: job_type = "인턴"

                # 링크 추출 및 건보 전용 안전 링크 생성
                raw_href = await link_el.get_attribute("href")
                if not raw_href or raw_href == "#" or "javascript:void" in raw_href:
                    continue
                
                href = url
                # 🔥 건보(nhis) 링크 오류 해결 로직: 게시판 파라미터를 그대로 보존하여 조립
                if inst_id == "nhis" and "javascript:fnView" in raw_href:
                    # 건보는 onclick 이벤트로 이동하므로, 그냥 채용 게시판 메인으로 보내는 것이 안전함
                    href = "https://www.nhis.or.kr/nhis/together/wbhaea02700m01.do"
                elif raw_href.startswith("http"): 
                    href = raw_href
                elif raw_href.startswith("/"): 
                    href = url.split("/")[0] + "//" + url.split("/")[2] + raw_href
                elif "?" in raw_href:
                    href = base_url + raw_href
                else: 
                    href = url.rsplit("/", 1)[0] + "/" + raw_href

                job_candidates.append({
                    "instId": inst_id,
                    "title": clean_title,
                    "raw_title": raw_title,
                    "row_text": row_text,
                    "jobType": job_type,
                    "link": href,
                    "detail_url": href # 본문 스크래핑을 위한 URL
                })
            except Exception as e:
                continue

        # 🔥 본문 딥 스크래핑 (Deep Scraping) 시작
        for job in job_candidates:
            start_str = "상세참조"
            end_str = "상세참조"
            status = "진행중"
            is_too_old = False
            combined_text = job['raw_title'] + " " + job['row_text']

            # 건보 등 본문을 읽어야 하는 경우 (시간 절약을 위해 링크가 살아있는 곳만)
            if job['detail_url'] and job['detail_url'].startswith("http") and inst_id != "nhis_safe_skip":
                try:
                    # 새 탭을 열어서 본문 내용을 긁어옴
                    detail_page = await browser.new_page(user_agent="Mozilla/5.0")
                    # 타임아웃을 짧게 주어 너무 오래 걸리는 것을 방지
                    await detail_page.goto(job['detail_url'], wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                    body_text = await detail_page.inner_text("body")
                    combined_text += " " + body_text # 목록 텍스트 + 본문 텍스트 합치기
                    await detail_page.close()
                except Exception as e:
                    # 봇 차단이나 타임아웃 발생 시 무시하고 목록 텍스트만 사용
                    try: await detail_page.close() 
                    except: pass
                    print(f"본문 접근 실패 ({job['instId']}): {job['title']}")

            # 🔥 정규식으로 연/월/일/시간 모두 찾아내기 (본문 포함)
            # 패턴 설명: '26.2.20, 2026-02-20, 3.5 15:00 등 다양한 변태적 포맷 대응
            pattern = r'(?:20)?(\d{2})\s*[-./]\s*(\d{1,2})\s*[-./]\s*(\d{1,2})(?:\s*\(?[월화수목금토일]\)?)?(?:\s*(\d{1,2}:\d{2}))?'
            matches = re.findall(pattern, combined_text)
            
            parsed_dates = []
            if matches:
                for m in matches:
                    try:
                        y, mo, d, t = m
                        y = int(y)
                        if y < 100: y += 2000 # '26 -> 2026 연환산
                        has_time = bool(t)
                        hour, minute = 0, 0
                        if has_time:
                            hour, minute = map(int, t.split(':'))
                            if hour >= 24: hour, minute = 23, 59 
                        
                        # 이상한 날짜 필터링 (예: 2026년 13월 등)
                        if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                            dt_obj = datetime(y, int(mo), int(d), hour, minute)
                            # 너무 과거이거나(5년전) 너무 미래(5년후)인 엉뚱한 숫자는 버림
                            if now.year - 2 <= dt_obj.year <= now.year + 2:
                                parsed_dates.append({'dt': dt_obj, 'has_time': has_time})
                    except:
                        continue
                
                if parsed_dates:
                    # 날짜순으로 정렬
                    parsed_dates.sort(key=lambda x: x['dt']) 
                    
                    now_kst = now.replace(tzinfo=None)

                    if len(parsed_dates) == 1:
                        # 날짜가 1개만 있으면 보통 작성일(시작일)임
                        start_item = parsed_dates[0]
                        if not start_item['has_time']: 
                            start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                        
                        start_str = start_item['dt'].strftime("%y.%m.%d")
                        end_str = "상세참조"
                        
                        # 작성일로부터 30일 지나면 오래된 공고로 간주
                        if (now_kst - start_item['dt']).days > 30:
                            status = "마감"
                            is_too_old = True
                        
                    elif len(parsed_dates) >= 2:
                        # 여러 개면 첫 날이 시작, 마지막이 마감!
                        start_item = parsed_dates[0]
                        end_item = parsed_dates[-1]
                        
                        if not start_item['has_time']: start_item['dt'] = start_item['dt'].replace(hour=0, minute=0)
                        if not end_item['has_time']: end_item['dt'] = end_item['dt'].replace(hour=18, minute=0) # 시간 없으면 오후 6시 마감 간주
                            
                        start_str = start_item['dt'].strftime("%y.%m.%d %H:%M")
                        end_str = end_item['dt'].strftime("%y.%m.%d %H:%M")
                        
                        # 마감일과 현재 시간 정밀 비교
                        if now_kst > end_item['dt']: 
                            status = "마감"
                            # 마감일로부터 30일 경과시 삭제 대상
                            if (now_kst - end_item['dt']).days > 30:
                                is_too_old = True

            # 대놓고 마감이라고 적힌 경우
            if "[마감]" in job['raw_title'] or "접수마감" in combined_text or "접수종료" in combined_text:
                status = "마감"
                if parsed_dates:
                    end_item = parsed_dates[-1]
                    now_kst = now.replace(tzinfo=None)
                    if (now_kst - end_item['dt']).days > 30:
                        is_too_old = True

            # 오래된 찌꺼기 공고는 최종 리스트에 넣지 않음
            if not is_too_old:
                found_jobs.append({
                    "instId": job['instId'],
                    "title": job['title'],
                    "startDate": start_str,
                    "endDate": end_str,
                    "status": status,
                    "jobType": job['jobType'],
                    "link": job['link']
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
        print(f"Error: {e}")
        return []
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 공식 채용 게시판 링크 모음
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


