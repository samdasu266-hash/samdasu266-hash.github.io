import streamlit as st
import pandas as pd
import feedparser
import requests
from datetime import datetime

st.set_page_config(page_title="공공기관 & 전문직무 채용 모아보기", layout="wide")

st.title("🎯 핵심 기관 및 전문 직무 채용 모니터링")
st.write("의료기관평가인증원, 건보, 심평원, NECA 및 QI/환자안전 직무 공고를 실시간으로 가져옵니다.")

# 검색 키워드 설정 (기관명 + 핵심 직무)
KEYWORDS = [
    "의료기관평가인증원",
    "건강보험심사평가원",
    "국민건강보험공단",
    "한국보건의료연구원",
    "QI 간호사",
    "환자안전 전담",
    "보건의료 통계"
]

@st.cache_data(ttl=600) # 10분마다 데이터 갱신
def get_rss_jobs(keyword):
    # 사람인 검색 결과 RSS URL (URL 인코딩 포함)
    rss_url = f"https://www.saramin.co.kr/zf_user/rss/recruit-psearch?searchword={keyword}"
    
    try:
        # RSS 피드 파싱
        feed = feedparser.parse(rss_url)
        jobs = []
        
        for entry in feed.entries:
            # RSS에서 제공하는 기본 정보 추출
            title = entry.title
            link = entry.link
            
            # 날짜 형식 변환 (문자열에서 날짜객체로)
            pub_date = entry.published if 'published' in entry else "날짜 정보 없음"
            
            jobs.append({
                '구분': f"[{keyword}] 관련",
                '공고명': title,
                '등록일': pub_date,
                '링크': link
            })
        return jobs
    except Exception as e:
        return []

# 실행 버튼
if st.button("🔄 최신 공고 업데이트 (RSS 기반)"):
    with st.spinner("사람인 RSS 피드를 분석 중입니다..."):
        all_jobs = []
        
        # 설정한 모든 키워드에 대해 루프 실행
        for kw in KEYWORDS:
            all_jobs.extend(get_rss_jobs(kw))
            
        if all_jobs:
            df = pd.DataFrame(all_jobs)
            
            # 중복된 공고 제거 (링크 기준)
            df = df.drop_duplicates(subset=['링크'])
            
            # 최신순 정렬 (등록일 기준 - 문자열이라 단순 정렬)
            df = df.sort_values(by='등록일', ascending=False)

            st.success(f"총 {len(df)}개의 공고를 찾았습니다.")
            
            # 결과 테이블 출력
            st.dataframe(
                df,
                column_config={
                    "링크": st.column_config.LinkColumn("공고 바로가기"),
                    "등록일": st.column_config.TextColumn("등록일", width="medium")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("현재 검색 조건에 맞는 공고가 없습니다.")
else:
    st.info("위 버튼을 누르면 사람인에 등록된 최신 기관 및 직무 공고를 한눈에 볼 수 있습니다.")

st.divider()
st.caption("본 서비스는 사람인 RSS 데이터를 활용하며, 실제 공고 마감 여부는 해당 사이트에서 확인하시기 바랍니다.")
