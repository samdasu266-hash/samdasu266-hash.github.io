#!/usr/bin/env python3
"""홈페이지 정적 콘텐츠 생성기.

index.html 의 본문은 React(app.js)가 그리기 때문에, HTML 소스에는
`<div id="root"></div>` 와 소개 문단만 남는다. 크롤러와 광고 심사가 보는
정적 본문이 2,000자 미만이라 '내용이 빈약한 페이지'로 평가되기 쉽다.

이 스크립트는 jobs.json + 기관 메타데이터로 아래 내용을 정적 HTML로 만들어
index.html 의 표시 영역에 심는다. **사용자에게도 그대로 보이는 콘텐츠**이며,
크롤러에게만 보여주는 숨김 텍스트가 아니다(클로킹이 아님).

  - 현재 진행 중인 공고 목록 (기관·고용형태·근무지역·마감일·원문 링크)
  - 기관별 채용 시즌 표
  - 자주 묻는 질문 (React FAQ 와 동일 내용)
  - 가이드 콘텐츠 요약 + 내부 링크

사용법:  python3 build_static_home.py
스크래퍼 워크플로에서 매시간 자동 실행되어 공고 목록이 항상 최신으로 유지된다.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))

START = "<!--STATIC_HOME_START-->"
END = "<!--STATIC_HOME_END-->"

# 기관 목록은 build_institution_pages.py 가 만드는 institutions.json 에서 읽는다.
# 기관을 추가할 때 그쪽 INSTITUTIONS 한 곳만 고치면 여기와 GAS 알림 메일에
# 함께 반영된다. 아래 예비값은 institutions.json 이 없을 때만 쓰인다.
INST_FALLBACK = {  # id: (기관명, 본사 소재지, 채용 주기)
    "nhis": ("국민건강보험공단", "강원특별자치도 원주시", "연 2회 (상반기 3~4월, 하반기 8~9월)"),
    "hira": ("건강보험심사평가원", "강원특별자치도 원주시", "연 2회 (상반기 4~5월, 하반기 9~10월)"),
    "nps": ("국민연금공단", "전북특별자치도 전주시", "연 2회 (상반기 4월, 하반기 9월)"),
    "comwel": ("근로복지공단", "울산광역시", "연 2회 (상반기 4~5월, 하반기 9~10월)"),
    "neca": ("한국보건의료연구원", "서울특별시 광진구 (보건복지행정타운)", "수시 및 상·하반기 통합 채용"),
    "kuksiwon": ("한국보건의료인국가시험원", "서울특별시 광진구", "연 1~2회 (하반기 집중)"),
    "koiha": ("의료기관평가인증원", "서울특별시 영등포구", "상·하반기 및 결원 수시 채용"),
    "redcross": ("대한적십자사", "강원특별자치도 원주시 (본사) · 전국 혈액원", "본사 통합 및 각 지사별 수시"),
    "mohw": ("보건복지부 및 소속기관", "세종특별자치시 (소속기관 전국)", "수시 채용 (공무직·임기제 중심)"),
    "khepi": ("한국건강증진개발원", "서울특별시 광진구 능동로 400 (보건복지행정타운)", "수시 및 상·하반기 채용"),
    "nmc": ("국립중앙의료원", "서울특별시 중구 을지로 245", "수시 채용 (직무별 개별 공고)"),
    "kac": ("한국공항공사(보건관리자)", "서울특별시 강서구 (전국 14개 공항)", "결원 발생 시 수시"),
}


def load_inst():
    """institutions.json → {id: (name, location, schedule)}"""
    try:
        with open(os.path.join(BASE, "institutions.json"), encoding="utf-8") as f:
            rows = json.load(f).get("institutions", [])
        out = {r["id"]: (r.get("name", r["id"]), r.get("location", ""), r.get("schedule", ""))
               for r in rows if r.get("id")}
        if out:
            return out
    except Exception:
        pass
    return INST_FALLBACK


INST = load_inst()


FAQ = [
    ("보건직 공기업 채용에서 가장 중요한 '서류 컷' 기준은 무엇인가요?",
     "대부분의 기관은 자격증·어학 점수로 서류를 선발하는 '정량 평가' 방식을 채택합니다. 컴활 1급, 한국사 1급, "
     "토익 800점 이상의 기본 스펙을 갖춘 뒤, 직렬별 우대 자격증(사회복지사 1급 등)으로 추가 가점을 확보하는 "
     "것이 합격권의 기본입니다."),
    ("임상 경력(병원 근무 경험)이 채용에 얼마나 도움이 되나요?",
     "심평원 심사직, 인증원 조사위원처럼 임상 경험을 직접 요구하는 직무에서는 종합병원급 이상 경력이 사실상 "
     "필수 경쟁력입니다. 반면 일반 행정직은 블라인드 원칙상 경력보다 NCS 필기와 정량 스펙이 더 크게 작용합니다. "
     "간호사·방사선사·임상병리사 등 직역과 지원 직무에 따라 경력의 가치가 달라집니다."),
    ("블라인드 채용인데 어떻게 준비해야 하나요?",
     "출신 학교·나이·가족관계 등은 평가에서 배제되므로, 자기소개서와 면접에서 '직무 역량 중심'으로 서술하는 "
     "것이 핵심입니다. 기관의 미션·사업을 숙지하고, 본인의 경험을 직무 역량과 연결해 구조화(STAR 기법)하는 "
     "연습을 권장합니다."),
    ("공고는 얼마나 자주 갱신되나요?",
     "본 사이트는 각 기관 채용 페이지를 1시간마다 자동 수집하여 진행 중인 공고만 보여드립니다. 마감되었거나 "
     "접수 기한이 지난 공고는 자동으로 숨겨집니다. 다만 정확한 자격 요건과 일정은 반드시 각 기관 공식 공고문을 "
     "확인하세요."),
    ("원하는 기관이 목록에 없어요. 추가할 수 있나요?",
     "상단 '기관 추가 요청' 버튼이나 하단 '문의하기'를 통해 기관명과 채용 페이지 주소를 남겨주시면, 검토 후 "
     "수집 대상에 반영합니다."),
]

GUIDES = [
    ("index.html#guide", "기관별 합격 가이드",
     "기관마다 전형 단계와 필기 과목이 다릅니다. 건보공단은 직업기초능력 60문항에 직무시험(법률) 20문항을 "
     "더해 과목당 40%·전 과목 60%를 넘겨야 하고, 국민연금은 필기와 면접을 5:5로 합산해 필기 고득점이 "
     "면접 열세를 덮을 수 있습니다. 근로복지공단은 행정직 6급 일반전형에만 직무기초지식이 추가되고, "
     "국시원은 필기 없이 서류·면접으로 뽑는 공고가 많습니다. 12개 기관의 전형 절차·서류 요건·가점 항목을 "
     "기관별로 정리했습니다."),
    ("guide.html", "기관별 근무환경·워라밸",
     "합격 이후의 생활을 좌우하는 요소를 다룹니다. 본사가 원주냐 전주냐 울산이냐에 따라 정착 난이도가 다르고, "
     "전국 지사 순환 근무를 전제로 하는 기관과 본사 고정 근무가 가능한 기관은 생활 설계가 달라집니다. "
     "위치·순환근무 여부·업무 강도와 성수기·육아휴직과 유연근무 분위기, 그리고 ALIO 공시 기준 신입 초임과 "
     "평균 보수를 기관별 카드로 비교할 수 있습니다."),
    ("tips.html", "보건의료 채용 트렌드",
     "공공기관 채용 시장의 최근 흐름을 정리한 칼럼입니다. NCS 기반 직무역량 평가의 확대, 블라인드 채용의 "
     "정착에 따른 준비 방식 변화, 직무 중심 자기소개서 작성 기조 등 준비 전략에 실제로 영향을 주는 "
     "변화를 다룹니다."),
    ("career.html", "임상 경력 활용 전략",
     "병원에서 쌓은 경력을 공공기관 직무 언어로 옮기는 방법을 다룹니다. 같은 경력이라도 심평원 심사직, "
     "인증원 조사위원, 건보공단 요양직에서 요구하는 서술 방식이 다릅니다. 경력을 직무 역량으로 재구성하는 "
     "구체적 작성 예시를 담았습니다."),
    ("gongmujik.html", "공무직·무기계약직 채용 완전 정리",
     "공무직은 공무원이 아닙니다. 기관마다 다른 명칭(공무직·업무직·현업직), 알리오 공시상 분류, 일반 "
     "정규직과의 직급·승진 차이, 보수 체계와 정년까지 실제로 무엇이 다른지 정리했습니다. 공고에서 "
     "고용형태만 보고 지원했다가 입사 후에 조건을 알게 되는 일을 줄이기 위한 문서입니다."),
    ("bogeon-manager.html", "보건관리자 완전 정리",
     "보건관리자는 산업안전보건법이 정한 법정 직무입니다. 시행령 별표 6의 자격 요건, 제22조가 규정한 "
     "업무 14가지, 간호사 면허가 있어야 할 수 있는 의료행위의 범위, 사업장 규모별 선임 기준을 "
     "법령 근거와 함께 정리했습니다. 산업간호로 전환하려는 분께 필요한 기준입니다."),
    ("ganhojik.html", "간호직 공무원 완전 정리",
     "'간호직 공무원'은 하나가 아닙니다. 국립병원 경력경쟁채용, 보건소에서 근무하는 지방직 8급, "
     "24주 직무교육을 받는 보건진료 전담공무원 — 세 갈래의 응시 자격·시험 과목·근무지·보수가 "
     "각각 다릅니다. 어느 쪽을 준비할지부터 정할 수 있도록 구분해 정리했습니다."),
    ("license.html", "서류 가점 전략",
     "서류 배수 통과가 정량 점수 싸움인 기관이 많습니다. 컴퓨터활용능력 1급, 한국사능력검정시험, "
     "사회복지사 1급, 어학 성적 등 가점 항목별 실효성과 취득 난이도, 준비 순서를 정리했습니다."),
    ("interview.html", "면접 필승 가이드",
     "기관별 면접 방식과 평가 항목을 정리했습니다. 직무전문성·문제해결능력·조직이해능력·대인관계능력·"
     "직업윤리 같은 평가 항목에 대응하는 경험 사례를 구조화(STAR)해 준비하는 방법을 다룹니다."),
]


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build():
    try:
        with open(os.path.join(BASE, "jobs.json"), encoding="utf-8") as f:
            jobs = json.load(f).get("jobs", [])
    except Exception:
        jobs = []

    today = datetime.now(KST)
    month = today.month
    now_label = today.strftime("%Y년 %m월 %d일")

    P = ['<section class="max-w-5xl mx-auto px-4 md:px-8 pb-16 space-y-6">']

    # ── 현재 진행 중인 공고 (본문 텍스트로도 남는 목록) ──────────────
    P.append('<div class="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm text-left">')
    P.append(f'<h2 class="text-lg font-black text-slate-900 mb-1">현재 접수 중인 보건의료 공공기관 채용 공고 '
             f'{len(jobs)}건</h2>')
    P.append(f'<p class="text-[12px] text-slate-400 font-medium mb-5">{now_label} 기준 · 매시간 자동 갱신</p>')
    if jobs:
        P.append('<ul class="divide-y divide-slate-100 text-[13.5px]">')
        for j in jobs:
            name = INST.get(j.get("instId"), (j.get("instId", ""), "", ""))[0]
            meta = " · ".join(x for x in [j.get("jobType"), j.get("region")] if x)
            end = j.get("endDate")
            due = (f'~{esc(end)} 마감' if end and end != "상세참조" else "마감일은 공고 확인")
            link = j.get("link")
            title = esc(j.get("title", ""))
            title_html = (f'<a href="{esc(link)}" target="_blank" rel="noopener noreferrer nofollow" '
                          f'class="text-slate-900 font-bold hover:text-blue-600 hover:underline">{title}</a>'
                          if link else f'<span class="text-slate-900 font-bold">{title}</span>')
            P.append(f'<li class="py-3"><span class="text-blue-600 font-bold text-[12px]">{esc(name)}</span><br>'
                     f'{title_html}<br>'
                     f'<span class="text-slate-500 text-[12.5px]">{esc(meta)}{" · " if meta else ""}{due}</span></li>')
        P.append("</ul>")
    else:
        P.append('<p class="text-slate-500 text-[13.5px]">현재 접수 중인 공고가 없습니다. '
                 '기관별 상세 페이지에서 지난 공고 아카이브를 확인하실 수 있습니다.</p>')
    P.append('<p class="text-[12px] text-slate-400 mt-5 leading-relaxed">공고 제목을 누르면 해당 기관의 '
             '공식 채용 페이지 원문으로 이동합니다. 지원 자격·전형 일정·제출 서류는 반드시 원문을 '
             '확인해 주세요.</p>')
    P.append("</div>")

    # ── 기관별 채용 시즌 ────────────────────────────────────────────
    P.append('<div class="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm text-left">')
    P.append('<h2 class="text-lg font-black text-slate-900 mb-1">기관별 채용 시기 한눈에 보기</h2>')
    P.append('<p class="text-[13.5px] text-slate-600 leading-relaxed mb-5">주요 기관의 정기 공채는 '
             '<strong>상반기 3~5월</strong>과 <strong>하반기 8~10월</strong>에 몰립니다. 그 사이 기간에 '
             '공고가 적은 것은 비수기이기 때문이며, 수시 채용 기관의 공고는 연중 계속 올라옵니다.</p>')
    P.append('<div class="overflow-x-auto"><table class="w-full text-[13px] border border-slate-200 rounded-xl">')
    P.append('<thead class="bg-slate-50 text-slate-500 text-left"><tr>'
             '<th class="p-3 font-bold">기관</th><th class="p-3 font-bold">본사 소재지</th>'
             '<th class="p-3 font-bold">채용 주기</th>'
             '<th class="p-3 font-bold">상세</th></tr></thead><tbody class="divide-y divide-slate-100">')
    for iid, (name, loc, sched) in INST.items():
        P.append(f'<tr><td class="p-3 font-bold text-slate-800">{esc(name)}</td>'
                 f'<td class="p-3 text-slate-600">{esc(loc)}</td>'
                 f'<td class="p-3 text-slate-600">{esc(sched)}</td>'
                 f'<td class="p-3"><a href="inst-{iid}.html" class="text-blue-600 hover:underline">'
                 f'공고 아카이브</a></td></tr>')
    P.append("</tbody></table></div>")
    P.append("</div>")

    # ── 가이드 콘텐츠 요약 ──────────────────────────────────────────
    P.append('<div class="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm text-left">')
    P.append('<h2 class="text-lg font-black text-slate-900 mb-5">채용 준비 가이드</h2>')
    P.append('<div class="space-y-5">')
    for href, title, body in GUIDES:
        P.append(f'<div><h3 class="text-[15px] font-bold text-slate-900 mb-1.5">'
                 f'<a href="{href}" class="hover:text-blue-600 hover:underline">{esc(title)}</a></h3>'
                 f'<p class="text-[13.5px] text-slate-600 leading-relaxed">{esc(body)}</p></div>')
    P.append("</div></div>")

    # ── FAQ ─────────────────────────────────────────────────────────
    P.append('<div class="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm text-left">')
    P.append('<h2 class="text-lg font-black text-slate-900 mb-5">보건의료 취업 자주 묻는 질문</h2>')
    P.append('<div class="space-y-5">')
    for q, a in FAQ:
        P.append(f'<div><h3 class="text-[14px] font-bold text-slate-900 mb-1.5">{esc(q)}</h3>'
                 f'<p class="text-[13.5px] text-slate-600 leading-relaxed">{esc(a)}</p></div>')
    P.append("</div></div>")

    P.append("</section>")
    return "\n".join(P)


def main():
    path = os.path.join(BASE, "index.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()

    if START not in html or END not in html:
        raise SystemExit(f"index.html 에 {START} / {END} 표시가 없습니다.")

    block = build()
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        START + "\n" + block + "\n" + END,
        html, flags=re.S)

    if new != html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"✅ index.html 정적 콘텐츠 갱신 ({len(block):,}자)")
    else:
        print("변경 없음")


if __name__ == "__main__":
    main()
