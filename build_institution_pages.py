#!/usr/bin/env python3
"""기관별 상세 페이지 생성기.

history.json(누적 공고 이력) + jobs.json(현재 공고) + 기관 메타데이터를 합쳐
기관마다 독립된 상세 페이지(inst-{id}.html)를 만든다.

이 페이지들이 존재하는 이유:
  - '국민건강보험공단 채용'처럼 기관명 검색어에 직접 대응하는 랜딩 페이지가 필요하다.
  - 수집 아카이브·통계는 이 사이트만 보유한 고유 데이터라, 자동 수집 목록만으로는
    확보하기 어려운 '독자적 가치'를 만든다.

사용법:  python3 build_institution_pages.py
매주 워크플로(.github/workflows/institution-pages.yml)에서 자동 실행되어
데이터가 쌓일수록 페이지가 두꺼워진다.
"""

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))
SITE = "https://samdasu266-hash.github.io"

# 색인 기준 — 아카이브가 이만큼 쌓인 기관 페이지만 색인·sitemap에 넣는다.
#
# 수집 이력이 0~수건뿐인 페이지는 기관 소개 문단과 빈 통계표만 남아, 12개가
# 서로 비슷한 얇은 페이지로 보인다. 이 상태로 전부 색인하면 사이트 전체가
# '자동 생성된 유사 페이지 묶음'으로 평가돼 품질 심사에 불리하다.
# 기준 미만이면 noindex(단 follow — 링크는 계속 따라가게 둔다)를 걸고
# sitemap에서 빼며, 데이터가 쌓이면 다음 주간 실행에서 자동으로 색인 대상이 된다.
MIN_ARCHIVE_FOR_INDEX = 5

# 기관 메타데이터 — app.jsx institutions 및 guide.html 카드와 정합을 유지한다.
INSTITUTIONS = [
    {
        "id": "nhis", "name": "국민건강보험공단", "short": "건보공단", "emoji": "🏢",
        "url": "https://nhis.kpcice.kr",
        "location": "강원특별자치도 원주시",
        "salary": "약 4,400만원", "avg": "약 6,900만원",
        "schedule": "연 2회 (상반기 3~4월, 하반기 8~9월)",
        "intro": "건강보험 자격·부과·급여와 장기요양보험을 운영하는 국내 최대 보건의료 공공기관입니다. 전국 지사망이 넓어 연고지 근무 가능성이 높은 편입니다.",
        "keypoint": "요양직은 간호사·물리치료사·작업치료사·사회복지사 등 면허 소지자만 지원할 수 있어, 보건의료인에게 문이 넓은 대표 기관입니다.",
    },
    {
        "id": "hira", "name": "건강보험심사평가원", "short": "심평원", "emoji": "🩺",
        "url": "https://hira.recruitlab.co.kr",
        "location": "강원특별자치도 원주시",
        "salary": "약 4,300만원", "avg": "약 7,000만원",
        "schedule": "연 2회 (상반기 4~5월, 하반기 9~10월)",
        "intro": "요양급여 심사와 의료 질 평가를 담당합니다. 보건의료 면허 소지자 비중이 매우 높아 임상 경력을 직접 활용하기 좋은 기관입니다.",
        "keypoint": "심사직은 종합병원급 이상 임상 경력이 지원 요건인 경우가 많아, 임상 경력이 곧 경쟁력이 됩니다.",
    },
    {
        "id": "nps", "name": "국민연금공단", "short": "국민연금", "emoji": "💰",
        "url": "https://nps.saramin.co.kr",
        "location": "전북특별자치도 전주시",
        "salary": "약 3,900만원", "avg": "약 6,000만원",
        "schedule": "연 2회 (상반기 4월, 하반기 9월)",
        "intro": "국민연금 제도를 운영하며 전국 지사 순환 근무 체제입니다. 기금 운용·연금 지급 전문성을 쌓을 수 있습니다.",
        "keypoint": "사회복지사 자격의 가점 비중이 높고, NCS·전공 필기 난도가 높은 편이라 필기 준비 비중을 크게 잡아야 합니다.",
    },
    {
        "id": "comwel", "name": "근로복지공단", "short": "근로복지", "emoji": "🏥",
        "url": "https://www.comwel.or.kr/recruit",
        "location": "울산광역시",
        "salary": "약 3,400만원", "avg": "약 5,600만원",
        "schedule": "연 2회 (상반기 4~5월, 하반기 9~10월)",
        "intro": "산재보험 행정과 직영 병원 운영이라는 두 축을 가진 기관입니다. 산재 보상이라는 특수 분야 커리어를 쌓기에 유리합니다.",
        "keypoint": "산업간호·직업병 분야 경험이 있다면 직무 연관성을 강하게 어필할 수 있습니다.",
    },
    {
        "id": "neca", "name": "한국보건의료연구원", "short": "보의연", "emoji": "📊",
        "url": "https://www.neca.re.kr",
        "location": "서울특별시 광진구 (보건복지행정타운)",
        "salary": "약 3,300만원", "avg": "약 5,300만원",
        "schedule": "수시 및 상·하반기 통합 채용",
        "intro": "근거 기반 의학(EBM)과 보건의료 정책을 연구합니다. 석·박사 비중이 높아 학술적 분위기가 강하며 서울 근무가 가능합니다.",
        "keypoint": "연구 실적·논문·통계 역량이 핵심이라, 대학원 진학을 병행한 탈임상 경로와 잘 맞습니다.",
    },
    {
        "id": "kuksiwon", "name": "한국보건의료인국가시험원", "short": "국시원", "emoji": "📝",
        "url": "https://dware.intojob.co.kr",
        "location": "서울특별시 광진구",
        "salary": "약 3,700만원", "avg": "약 5,300만원",
        "schedule": "연 1~2회 (하반기 집중)",
        "intro": "보건의료인 국가시험을 주관합니다. 시험 시즌에는 업무 밀도가 높지만 비시즌에는 평온한 편입니다.",
        "keypoint": "서울 고정 근무가 가능해 수도권 정착 선호자에게 인기가 높고, 기관 규모가 작아 채용 규모도 작습니다.",
    },
    {
        "id": "koiha", "name": "의료기관평가인증원", "short": "인증원", "emoji": "✅",
        "url": "https://koiha.recruiter.co.kr",
        "location": "서울특별시 영등포구",
        "salary": "약 3,900만원", "avg": "약 6,000만원",
        "schedule": "상·하반기 및 결원 수시 채용",
        "intro": "의료기관 인증 평가를 수행합니다. 병원 시스템을 평가·컨설팅하는 역할이라 직무 자부심이 높은 편입니다.",
        "keypoint": "전국 병원 현장 평가 출장이 잦고, 임상 경험과 QI(질 향상) 활동 경력이 직접적인 강점이 됩니다.",
    },
    {
        "id": "redcross", "name": "대한적십자사", "short": "적십자사", "emoji": "🩸",
        "url": "https://www.redcross.or.kr/recruit/",
        "location": "강원특별자치도 원주시 (본사) · 전국 혈액원",
        "salary": "약 3,300만원", "avg": "약 6,000만원",
        "schedule": "본사 통합 및 각 지사·혈액원별 수시",
        "intro": "혈액사업과 인도주의 활동을 수행합니다. 전국 혈액원·적십자병원·지사로 근무지가 다양합니다.",
        "keypoint": "헌혈 횟수·봉사 실적이 가점으로 인정되는 경우가 있으며, 혈액관리 파트는 교대·주말 근무가 발생할 수 있습니다.",
    },
    {
        "id": "mohw", "name": "보건복지부 및 소속기관", "short": "보건복지부", "emoji": "🏛️",
        "url": "https://www.mohw.go.kr",
        "location": "세종특별자치시 (소속기관 전국)",
        "salary": "공무직 보수규정 적용", "avg": "직급별 상이",
        "schedule": "수시 채용",
        "intro": "보건복지부 본부와 소속·산하기관의 공무직·임기제 채용이 함께 공고됩니다. 국립병원·정보원 등 다양한 기관이 포함됩니다.",
        "keypoint": "소속기관마다 근무지가 전혀 다르므로, 공고문에서 실제 근무지를 반드시 확인해야 합니다.",
    },
    {
        "id": "khepi", "name": "한국건강증진개발원", "short": "건강증진원", "emoji": "🌱",
        "url": "https://khepi-hr.jobnlab.co.kr/",
        "location": "서울특별시 광진구 능동로 400 (보건복지행정타운)",
        "salary": "약 3,300만원", "avg": "약 5,000~6,300만원",
        "schedule": "수시 및 상·하반기 채용",
        "intro": "국가 금연지원사업, 지역사회 통합건강증진사업 등 건강증진 정책을 기획·관리·평가합니다. 진료가 아닌 사업 관리·정책 연구가 중심입니다.",
        "keypoint": "현직자 리뷰에서 주 4.5일제와 수평적 문화가 강점으로 꼽히며, 보건교육·건강증진 분야 전환에 적합합니다.",
    },
    {
        "id": "nmc", "name": "국립중앙의료원", "short": "중앙의료원", "emoji": "🏥",
        "url": "https://nmc.recruiter.co.kr/app/jobnotice/list",
        "location": "서울특별시 중구 을지로 245",
        "salary": "약 3,400만원", "avg": "약 5,200만원",
        "schedule": "상반기 3~5월 · 하반기 9~11월 집중",
        "intro": "공공보건의료의 중추 기관으로 진료와 함께 정책·교육·연구 기능을 수행합니다. 직원 약 1,750명 규모입니다.",
        "keypoint": "본 사이트는 탈임상 관점에 맞춰 진료·병동 등 임상 포지션을 제외하고 연구·행정 직무 공고만 수집합니다.",
    },
    {
        "id": "kac", "name": "한국공항공사", "short": "공항공사", "emoji": "✈️",
        "url": "https://kac.careerlink.kr/jobs",
        "location": "서울특별시 강서구 (전국 14개 공항)",
        "salary": "약 4,000만원", "avg": "약 6,800만원",
        "schedule": "결원 발생 시 수시",
        "intro": "보건의료 기관은 아니지만 사업장 보건관리자(산업보건) 직무를 채용합니다. 근로자 건강관리·작업환경 관리가 주 업무입니다.",
        "keypoint": "본 사이트는 보건관리자 직무 공고만 선별해 수집합니다. 교대 없는 주간 상근이 기본이라 산업간호 전환에 적합합니다.",
    },
]

NAV = [
    ("index.html", "홈"),
    ("index.html#guide", "기관별 합격 가이드"),
    ("guide.html", "근무환경·워라밸"),
    ("gongmujik.html", "공무직·무기계약직"),
    ("bogeon-manager.html", "보건관리자"),
    ("ganhojik.html", "간호직 공무원"),
    ("tips.html", "채용 트렌드"),
    ("career.html", "임상경력 활용"),
    ("license.html", "서류 가점 전략"),
    ("interview.html", "면접 필승 가이드"),
]


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load(fn, default):
    try:
        with open(os.path.join(BASE, fn), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def nav_html():
    # 마크업·스타일은 tailwind.input.css 의 .site-nav 규칙과 짝을 이룬다.
    # (항목 10개가 한 줄에 안 들어가 데스크톱은 줄바꿈, 모바일은 가로 스크롤)
    return ('    <div class="site-nav-wrap mb-8 -mx-4 md:mx-0 border-b border-slate-200 pb-2">\n'
            '      <nav class="site-nav px-4 md:px-0 text-[12.5px] md:text-[13px]">\n'
            + "\n".join(f'        <a href="{h}" class="site-nav-link">{l}</a>' for h, l in NAV)
            + '\n      </nav>\n    </div>')


def build_page(inst, hist_jobs, live_jobs, version, today):
    iid = inst["id"]
    mine = [j for j in hist_jobs if j.get("instId") == iid]
    live = [j for j in live_jobs if j.get("instId") == iid]
    mine_sorted = sorted(mine, key=lambda x: x.get("firstSeen", ""), reverse=True)

    indexable = len(mine) >= MIN_ARCHIVE_FOR_INDEX
    robots = ("" if indexable else
              '\n    <meta name="robots" content="noindex,follow">')

    types = Counter((j.get("jobType") or "정규직") for j in mine)
    regions = Counter((j.get("region") or "전국").split("(")[0].strip() for j in mine)
    first_seen = min((j.get("firstSeen", "") for j in mine), default="")
    last_seen = max((j.get("lastSeen", "") for j in mine), default="")

    title = f"{inst['name']} 채용 정보 — 공고 아카이브·수집 통계 | 보건공기업 알리미"
    desc = (f"{inst['name']} 채용 공고 아카이브와 수집 통계. 본사 {inst['location']}, "
            f"신입 초임 {inst['salary']}, 채용 주기 {inst['schedule']}. "
            f"지금까지 수집된 공고 {len(mine)}건의 고용형태·근무지역 분포를 함께 제공합니다.")
    url = f"{SITE}/inst-{iid}.html"

    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"{inst['name']} 채용 정보", "description": desc,
        "url": url, "inLanguage": "ko-KR",
        "about": {"@type": "Organization", "name": inst["name"], "url": inst["url"]},
        "dateModified": today,
    }

    # ── 통계 블록
    stat_rows = "".join(
        f'<div class="flex justify-between py-1.5 border-b border-slate-100 last:border-0">'
        f'<span class="text-slate-500">{esc(k)}</span>'
        f'<span class="font-bold text-slate-900">{v}건</span></div>'
        for k, v in types.most_common())
    region_rows = "".join(
        f'<div class="flex justify-between py-1.5 border-b border-slate-100 last:border-0">'
        f'<span class="text-slate-500">{esc(k)}</span>'
        f'<span class="font-bold text-slate-900">{v}건</span></div>'
        for k, v in regions.most_common(6))

    # ── 아카이브 목록
    if mine_sorted:
        rows = []
        for j in mine_sorted:
            closed = ""
            if not any(l.get("title") == j.get("title") for l in live):
                closed = '<span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 ml-1">마감</span>'
            rows.append(
                '<li class="py-3 border-b border-slate-100 last:border-0">'
                f'<div class="font-bold text-slate-800 text-[14px] leading-snug break-keep">{esc(j.get("title"))}{closed}</div>'
                f'<div class="text-[12px] text-slate-500 mt-1">'
                f'{esc(j.get("jobType") or "정규직")} · {esc(j.get("region") or "전국")} · '
                f'접수 {esc(j.get("startDate") or "-")} ~ {esc(j.get("endDate") or "-")}'
                f'<span class="text-slate-400"> · 수집 {esc(j.get("firstSeen") or "-")}</span></div></li>')
        archive = '<ul class="mt-4">' + "".join(rows) + "</ul>"
    else:
        archive = ('<p class="mt-4 text-[13.5px] text-slate-500">아직 이 기관에서 수집된 공고가 없습니다. '
                   '새 공고가 올라오면 자동으로 이곳에 쌓입니다.</p>')

    live_html = ""
    if live:
        items = "".join(
            f'<li class="py-2"><a href="{esc(j.get("link") or inst["url"])}" target="_blank" '
            f'rel="noopener noreferrer" class="text-blue-600 font-bold hover:underline text-[14px]">'
            f'{esc(j.get("title"))}</a>'
            f'<span class="block text-[12px] text-slate-500">~ {esc(j.get("endDate") or "상세참조")}</span></li>'
            for j in live)
        live_html = (
            '<section class="bg-blue-50 border border-blue-100 p-6 rounded-2xl mb-8">'
            f'<h2 class="text-[15px] font-bold text-blue-900 mb-1">🔔 지금 접수 중인 공고 {len(live)}건</h2>'
            f'<ul class="divide-y divide-blue-100">{items}</ul></section>')

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-7297NMP8GQ"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-7297NMP8GQ');
</script>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">{robots}
    <!-- Google AdSense -->
    <meta name="google-adsense-account" content="ca-pub-2720320967054456">
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2720320967054456" crossorigin="anonymous"></script>
    <link rel="canonical" href="{url}">
    <title>{esc(title)}</title>
    <meta name="description" content="{esc(desc)}">
    <meta name="keywords" content="{esc(inst['name'])} 채용, {esc(inst['short'])} 채용, {esc(inst['name'])} 채용공고, {esc(inst['short'])} 연봉, {esc(inst['short'])} 초봉, 보건의료 공공기관 채용">
    <meta property="og:type" content="article">
    <meta property="og:title" content="{esc(title)}">
    <meta property="og:description" content="{esc(desc)}">
    <meta property="og:url" content="{url}">
    <meta property="og:image" content="https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?q=80&w=1200&auto=format&fit=crop">
    <meta name="twitter:card" content="summary_large_image">
    <script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=2)}
    </script>
    <link rel="stylesheet" href="tailwind.css?v={version}">
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
        body {{ font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif; background-color: #f8fafc; color: #1e293b; line-height: 1.8; }}
    </style>
</head>
<body class="p-4 md:p-8 max-w-4xl mx-auto text-left">
{nav_html()}

    <article class="bg-white p-8 md:p-12 rounded-3xl border border-slate-200 shadow-sm">
        <header class="border-b border-slate-100 pb-8 mb-8">
            <h1 class="text-3xl md:text-4xl font-black text-slate-900 leading-tight">{inst['emoji']} {esc(inst['name'])} 채용 정보</h1>
            <p class="text-[12px] text-slate-400 font-medium mt-3">🔄 최근 갱신: {today} · 수집 이력 {len(mine)}건</p>
            <p class="text-slate-500 font-medium mt-4 leading-relaxed break-keep">{esc(inst['intro'])}</p>
        </header>

        {live_html}

        <section class="mb-10">
            <h2 class="text-xl font-bold text-slate-900 mb-4">기본 정보</h2>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[14px]">
                <div class="bg-slate-50 border border-slate-100 rounded-2xl p-4"><span class="block text-[12px] text-slate-500 mb-1">본사 위치</span><strong class="text-slate-900">{esc(inst['location'])}</strong></div>
                <div class="bg-slate-50 border border-slate-100 rounded-2xl p-4"><span class="block text-[12px] text-slate-500 mb-1">채용 주기</span><strong class="text-slate-900">{esc(inst['schedule'])}</strong></div>
                <div class="bg-slate-50 border border-slate-100 rounded-2xl p-4"><span class="block text-[12px] text-slate-500 mb-1">신입 초임(근사치)</span><strong class="text-slate-900">{esc(inst['salary'])}</strong></div>
                <div class="bg-slate-50 border border-slate-100 rounded-2xl p-4"><span class="block text-[12px] text-slate-500 mb-1">평균 보수(근사치)</span><strong class="text-slate-900">{esc(inst['avg'])}</strong></div>
            </div>
            <p class="mt-4 text-[13.5px] text-slate-700 font-medium leading-relaxed break-keep"><strong class="text-slate-900">💡 지원 포인트 —</strong> {esc(inst['keypoint'])}</p>
            <p class="mt-3 text-[12px] text-slate-400">※ 금액은 공시·채용정보를 종합한 근사치입니다. 정확한 기준은 <a href="{esc(inst['url'])}" target="_blank" rel="noopener noreferrer" class="text-blue-600 underline">{esc(inst['short'])} 채용 페이지</a>와 공고문을 확인하세요.</p>
        </section>

        <section class="mb-10">
            <h2 class="text-xl font-bold text-slate-900 mb-1">📊 이 사이트가 수집한 채용 통계</h2>
            <p class="text-[12.5px] text-slate-400 mb-4">{esc(first_seen)} ~ {esc(last_seen)} 동안 자동 수집된 {len(mine)}건 기준 · 매주 갱신</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-[13.5px]">
                <div class="border border-slate-200 rounded-2xl p-5">
                    <h3 class="font-bold text-slate-900 mb-2">고용형태 분포</h3>
                    {stat_rows or '<p class="text-slate-400">데이터 누적 중</p>'}
                </div>
                <div class="border border-slate-200 rounded-2xl p-5">
                    <h3 class="font-bold text-slate-900 mb-2">근무지역 분포</h3>
                    {region_rows or '<p class="text-slate-400">데이터 누적 중</p>'}
                </div>
            </div>
        </section>

        <section class="mb-10">
            <h2 class="text-xl font-bold text-slate-900 mb-1">📁 {esc(inst['short'])} 공고 아카이브</h2>
            <p class="text-[12.5px] text-slate-400">마감되어 원본 사이트에서 내려간 공고도 기록으로 남겨둡니다. 과거 어떤 직무를 언제 뽑았는지 확인해 다음 채용을 예측하는 데 활용하세요.</p>
            {archive}
        </section>

        <section class="bg-slate-50 border border-slate-200 rounded-2xl p-6">
            <h2 class="text-[15px] font-bold text-slate-900 mb-3">함께 보면 좋은 가이드</h2>
            <ul class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[13.5px]">
                <li><a href="index.html#guide" class="text-blue-600 font-bold hover:underline">기관별 합격 가이드 — 전형 단계·필기 과목</a></li>
                <li><a href="guide.html" class="text-blue-600 font-bold hover:underline">근무환경·워라밸 — 입사 후 생활</a></li>
                <li><a href="license.html" class="text-blue-600 font-bold hover:underline">서류 가점 전략 — 자격·어학</a></li>
                <li><a href="interview.html" class="text-blue-600 font-bold hover:underline">면접 필승 가이드 — 구조화 면접</a></li>
            </ul>
        </section>
    </article>

    <footer class="mt-12 text-center text-slate-400 text-[12px] font-medium border-t pt-8">
        <p>© 2026 보건의료 채용 포털. All rights reserved.</p>
        <p class="mt-1">본 아카이브는 각 기관 공식 채용 페이지에서 자동 수집한 기록입니다. 정확한 내용은 반드시 원본 공고문을 확인하세요.</p>
        <p class="mt-2"><a href="about.html" class="text-slate-500 hover:text-blue-600 underline">사이트 소개·운영정책</a></p>
    </footer>
    <script src="nav.js?v=202608110038" defer></script>
</body>
</html>
"""


def main():
    hist = load("history.json", {"jobs": []}).get("jobs", [])
    live = load("jobs.json", {"jobs": []}).get("jobs", [])
    now = datetime.now(KST)
    today = now.strftime("%Y.%m.%d")
    version = now.strftime("%Y%m%d%H%M")

    written = []
    for inst in INSTITUTIONS:
        html = build_page(inst, hist, live, version, today)
        fn = f"inst-{inst['id']}.html"
        with open(os.path.join(BASE, fn), "w", encoding="utf-8") as f:
            f.write(html)
        n = len([j for j in hist if j.get("instId") == inst["id"]])
        written.append((fn, n))
        mark = "색인" if n >= MIN_ARCHIVE_FOR_INDEX else "noindex"
        print(f"  생성: {fn} (아카이브 {n}건, {mark})")

    # sitemap.xml 갱신 — 아카이브가 MIN_ARCHIVE_FOR_INDEX 이상인 기관만 넣는다.
    # 기준을 밑도는 페이지는 이미 색인돼 있었더라도 항목을 도로 걷어내, 페이지의
    # noindex 상태와 sitemap이 서로 어긋나지 않게 맞춘다.
    sm_path = os.path.join(BASE, "sitemap.xml")
    try:
        sm = open(sm_path, encoding="utf-8").read()
        d = now.strftime("%Y-%m-%d")

        for fn, n in written:
            listed = f"/{fn}<" in sm
            if n >= MIN_ARCHIVE_FOR_INDEX and not listed:
                sm = sm.replace(
                    "</urlset>",
                    f"<url>\n  <loc>{SITE}/{fn}</loc>\n  <lastmod>{d}</lastmod>\n</url>\n\n</urlset>")
                print(f"  sitemap 추가: {fn} (아카이브 {n}건)")
            elif n < MIN_ARCHIVE_FOR_INDEX and listed:
                sm = re.sub(
                    r"[ \t]*<url>\s*<loc>[^<]*/" + re.escape(fn) + r"</loc>.*?</url>\s*",
                    "", sm, flags=re.S)
                print(f"  sitemap 제외: {fn} (아카이브 {n}건 < {MIN_ARCHIVE_FOR_INDEX})")

        open(sm_path, "w", encoding="utf-8").write(sm)
    except Exception as e:
        print(f"  sitemap 갱신 건너뜀: {e}")

    # institutions.json — 기관 목록을 사이트에 공개해, 저장소 밖(GAS 등)에서도
    # 같은 목록을 읽어 쓰게 한다.
    #
    # 기관을 추가할 때 이 파일의 INSTITUTIONS 한 곳만 고치면 되도록 하기 위한 것이다.
    # 이게 없으면 기관을 추가할 때마다 GAS 의 INST_NAMES 를 손으로 고치고 재배포해야
    # 하고, 빠뜨리면 알림 메일에 기관명 대신 'khepi' 같은 ID 가 그대로 찍힌다.
    meta_path = os.path.join(BASE, "institutions.json")
    meta = {
        "generated": now.isoformat(timespec="seconds"),
        "institutions": [
            {k: inst[k] for k in ("id", "name", "short", "url", "location", "schedule")}
            for inst in INSTITUTIONS
        ],
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"  institutions.json 생성 ({len(INSTITUTIONS)}개 기관)")

    indexed = sum(1 for _, n in written if n >= MIN_ARCHIVE_FOR_INDEX)
    print(f"✅ 기관 페이지 {len(written)}개 생성 완료 "
          f"(색인 {indexed}개 / noindex {len(written) - indexed}개, 총 아카이브 {len(hist)}건)")


if __name__ == "__main__":
    main()
