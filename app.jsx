const { useState, useEffect, useMemo } = React;

const Icon = ({ name, className = "w-5 h-5" }) => {
    useEffect(() => { if (window.lucide) lucide.createIcons(); }, [name, className]);
    return <i data-lucide={name} className={className}></i>;
};

// 사이트 내 요청 팝업 → GAS 웹앱으로 제출 (스프레드시트 적재 + 자동 회신 메일은 GAS가 처리)
const REQUEST_ENDPOINT = "https://script.google.com/macros/s/AKfycbxef_fTDTuHv2P4ORGhgIcZGxz2QbAAc-68AfdEV1Dx5YnhQs-_sozST89ik2_sUbB_uw/exec";
const EMAIL_DOMAINS = ["naver.com", "gmail.com", "daum.net", "hanmail.net", "nate.com", "kakao.com", "icloud.com", "outlook.com"];

const RequestModal = ({ open, onClose }) => {
    const [type, setType] = useState("기관 추가 요청");
    const [org, setOrg] = useState("");
    const [url, setUrl] = useState("");
    const [content, setContent] = useState("");
    const [emailLocal, setEmailLocal] = useState("");
    const [emailDomain, setEmailDomain] = useState("naver.com");
    const [customDomain, setCustomDomain] = useState("");
    const [status, setStatus] = useState("idle"); // idle | sending | done | error

    if (!open) return null;

    const domain = emailDomain === "__custom__" ? customDomain.trim() : emailDomain;
    const email = emailLocal.trim() && domain ? `${emailLocal.trim()}@${domain}` : "";

    const reset = () => {
        setType("기관 추가 요청"); setOrg(""); setUrl(""); setContent("");
        setEmailLocal(""); setEmailDomain("naver.com"); setCustomDomain(""); setStatus("idle");
    };
    const close = () => { reset(); onClose(); };

    const submit = () => {
        if (!content.trim()) { alert("내용을 입력해주세요."); return; }
        setStatus("sending");
        fetch(REQUEST_ENDPOINT, {
            method: "POST",
            mode: "no-cors",
            headers: { "Content-Type": "text/plain;charset=utf-8" },
            body: JSON.stringify({ type, org, url, content, email }),
        }).then(() => setStatus("done")).catch(() => setStatus("error"));
    };

    return (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm" onClick={close}>
            <div className="bg-white w-full max-w-md rounded-[2rem] p-7 shadow-2xl relative animate-in zoom-in duration-300 max-h-[90vh] overflow-y-auto no-scrollbar" onClick={e => e.stopPropagation()}>
                <button onClick={close} className="absolute top-5 right-5 text-slate-300 hover:text-slate-900"><Icon name="x" /></button>
                {status === "done" ? (
                    <div className="text-center py-6">
                        <div className="w-16 h-16 mx-auto rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mb-4"><Icon name="check" className="w-8 h-8" /></div>
                        <h2 className="text-lg font-black text-slate-900 mb-2">요청이 접수되었어요!</h2>
                        <p className="text-sm text-slate-500 font-medium leading-relaxed mb-6">보내주신 의견을 검토 후 반영하겠습니다.{email ? " 입력하신 메일로 접수 확인 메일을 보내드렸어요." : ""}</p>
                        <button onClick={close} className="w-full py-3.5 bg-slate-900 text-white rounded-2xl font-bold hover:bg-blue-600 transition-colors">닫기</button>
                    </div>
                ) : (
                    <div>
                        <h2 className="text-lg font-black text-slate-900 mb-1 flex items-center gap-2"><Icon name="plus-circle" className="text-blue-600 w-5 h-5" /> 기관 추가 · 건의하기</h2>
                        <p className="text-[12px] text-slate-400 font-medium mb-5">원하는 기관이나 사이트 개선 의견을 남겨주세요.</p>
                        <div className="space-y-3.5 text-left">
                            <div>
                                <label className="text-[11px] font-bold text-slate-500 mb-1.5 block">요청 유형</label>
                                <div className="flex gap-1.5">
                                    {["기관 추가 요청", "오류 제보", "기타 건의"].map(t => (
                                        <button key={t} onClick={() => setType(t)} className={`flex-1 px-2 py-2 rounded-xl text-[11.5px] font-bold border transition-all ${type === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>{t}</button>
                                    ))}
                                </div>
                            </div>
                            <input value={org} onChange={e => setOrg(e.target.value)} placeholder="기관명 (예: 한국건강증진개발원)" className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="채용 페이지 주소 (선택)" className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                            <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="내용을 입력해주세요" rows={3} className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium resize-none" />
                            <div>
                                <label className="text-[11px] font-bold text-slate-500 mb-1.5 block">회신 받을 이메일 <span className="text-slate-300 font-medium">(선택 · 접수 확인 메일 발송)</span></label>
                                <div className="flex items-center gap-1.5">
                                    <input value={emailLocal} onChange={e => setEmailLocal(e.target.value)} placeholder="아이디" className="flex-1 min-w-0 px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                                    <span className="text-slate-400 font-bold shrink-0">@</span>
                                    <select value={emailDomain} onChange={e => setEmailDomain(e.target.value)} className="shrink-0 px-2 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium">
                                        {EMAIL_DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                                        <option value="__custom__">직접입력</option>
                                    </select>
                                </div>
                                {emailDomain === "__custom__" && (
                                    <input value={customDomain} onChange={e => setCustomDomain(e.target.value)} placeholder="도메인 직접입력 (예: company.co.kr)" className="mt-1.5 w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                                )}
                            </div>
                            {status === "error" && <p className="text-[12px] text-red-500 font-bold">전송에 실패했어요. 잠시 후 다시 시도해주세요.</p>}
                            <button onClick={submit} disabled={status === "sending"} className="w-full py-3.5 bg-blue-600 text-white rounded-2xl font-bold hover:bg-blue-700 transition-colors shadow-lg disabled:opacity-60">{status === "sending" ? "전송 중..." : "요청 보내기"}</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

// 채용 알림 구독 팝업.
// 제출된 이메일은 GAS 스프레드시트에만 저장한다(저장소는 공개이고 git 이력은
// 삭제가 어려워 수신거부 시 파기 의무를 이행할 수 없기 때문).
const NotifyModal = ({ open, onClose, institutions }) => {
    const [emailLocal, setEmailLocal] = useState("");
    const [emailDomain, setEmailDomain] = useState("naver.com");
    const [customDomain, setCustomDomain] = useState("");
    const [insts, setInsts] = useState([]);      // 빈 배열 = 전체 기관
    const [jobTypes, setJobTypes] = useState([]); // 빈 배열 = 전체 고용형태
    const [agree, setAgree] = useState(false);
    const [status, setStatus] = useState("idle"); // idle | sending | done | error

    if (!open) return null;

    const domain = emailDomain === "__custom__" ? customDomain.trim() : emailDomain;
    const email = emailLocal.trim() && domain ? `${emailLocal.trim()}@${domain}` : "";

    const reset = () => {
        setEmailLocal(""); setEmailDomain("naver.com"); setCustomDomain("");
        setInsts([]); setJobTypes([]); setAgree(false); setStatus("idle");
    };
    const close = () => { reset(); onClose(); };

    const toggle = (setter, value) =>
        setter(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);

    const submit = () => {
        if (!/.+@.+\..+/.test(email)) { alert("이메일 주소를 정확히 입력해주세요."); return; }
        if (!agree) { alert("개인정보 수집·이용에 동의해주세요."); return; }
        setStatus("sending");
        fetch(REQUEST_ENDPOINT, {
            method: "POST",
            mode: "no-cors",
            headers: { "Content-Type": "text/plain;charset=utf-8" },
            body: JSON.stringify({
                type: "채용알림 신청",
                email,
                insts: insts.join(","),
                jobTypes: jobTypes.join(","),
            }),
        }).then(() => setStatus("done")).catch(() => setStatus("error"));
    };

    const JOB_TYPES = ["정규직", "무기계약직", "계약직/기간제", "공무직", "인턴"];

    return (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm" onClick={close}>
            <div className="bg-white w-full max-w-md rounded-[2rem] p-7 shadow-2xl relative animate-in zoom-in duration-300 max-h-[90vh] overflow-y-auto no-scrollbar" onClick={e => e.stopPropagation()}>
                <button onClick={close} className="absolute top-5 right-5 text-slate-300 hover:text-slate-900"><Icon name="x" /></button>
                {status === "done" ? (
                    <div className="text-center py-6">
                        <div className="w-16 h-16 mx-auto rounded-full bg-blue-50 text-blue-500 flex items-center justify-center mb-4"><Icon name="mail-check" className="w-8 h-8" /></div>
                        <h2 className="text-lg font-black text-slate-900 mb-2">알림 신청이 완료되었어요!</h2>
                        <p className="text-sm text-slate-500 font-medium leading-relaxed mb-6">확인 메일을 보내드렸어요. 새 공고가 올라온 날 <strong className="text-slate-700">오전 8시</strong>에 한 통으로 모아 보내드립니다.</p>
                        <button onClick={close} className="w-full py-3.5 bg-slate-900 text-white rounded-2xl font-bold hover:bg-blue-600 transition-colors">닫기</button>
                    </div>
                ) : (
                    <div>
                        <h2 className="text-lg font-black text-slate-900 mb-1 flex items-center gap-2"><Icon name="bell" className="text-blue-600 w-5 h-5" /> 채용 알림 받기</h2>
                        <p className="text-[12px] text-slate-400 font-medium mb-5">새 공고가 올라온 날에만 오전 8시에 메일로 알려드립니다.</p>
                        <div className="space-y-4 text-left">
                            <div>
                                <label className="text-[11px] font-bold text-slate-500 mb-1.5 block">이메일 <span className="text-red-400">*</span></label>
                                <div className="flex items-center gap-1.5">
                                    <input value={emailLocal} onChange={e => setEmailLocal(e.target.value)} placeholder="아이디" className="flex-1 min-w-0 px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                                    <span className="text-slate-400 font-bold shrink-0">@</span>
                                    <select value={emailDomain} onChange={e => setEmailDomain(e.target.value)} className="shrink-0 px-2 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium">
                                        {EMAIL_DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                                        <option value="__custom__">직접입력</option>
                                    </select>
                                </div>
                                {emailDomain === "__custom__" && (
                                    <input value={customDomain} onChange={e => setCustomDomain(e.target.value)} placeholder="도메인 직접입력 (예: company.co.kr)" className="mt-1.5 w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium" />
                                )}
                            </div>

                            <div>
                                <label className="text-[11px] font-bold text-slate-500 mb-1.5 block">관심 기관 <span className="text-slate-300 font-medium">(선택 안 하면 전체)</span></label>
                                <div className="flex flex-wrap gap-1.5">
                                    {institutions.map(inst => (
                                        <button key={inst.id} onClick={() => toggle(setInsts, inst.id)} className={`px-2.5 py-1.5 rounded-lg text-[11.5px] font-bold border transition-all ${insts.includes(inst.id) ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>{inst.shortName}</button>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <label className="text-[11px] font-bold text-slate-500 mb-1.5 block">관심 고용형태 <span className="text-slate-300 font-medium">(선택 안 하면 전체)</span></label>
                                <div className="flex flex-wrap gap-1.5">
                                    {JOB_TYPES.map(t => (
                                        <button key={t} onClick={() => toggle(setJobTypes, t)} className={`px-2.5 py-1.5 rounded-lg text-[11.5px] font-bold border transition-all ${jobTypes.includes(t) ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>{t}</button>
                                    ))}
                                </div>
                            </div>

                            <label className="flex items-start gap-2.5 bg-slate-50 border border-slate-200 rounded-xl p-3.5 cursor-pointer">
                                <input type="checkbox" checked={agree} onChange={e => setAgree(e.target.checked)} className="mt-0.5 w-4 h-4 accent-blue-600 shrink-0" />
                                <span className="text-[11.5px] text-slate-500 font-medium leading-relaxed">
                                    채용 알림 발송을 위한 <strong className="text-slate-700">이메일 주소 수집·이용</strong>에 동의합니다. 수신거부 시 즉시 파기되며, 메일 하단 링크로 언제든 해지할 수 있습니다. <a href="privacy.html" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">개인정보처리방침</a>
                                </span>
                            </label>

                            {status === "error" && <p className="text-[12px] text-red-500 font-bold">전송에 실패했어요. 잠시 후 다시 시도해주세요.</p>}
                            <button onClick={submit} disabled={status === "sending"} className="w-full py-3.5 bg-blue-600 text-white rounded-2xl font-bold hover:bg-blue-700 transition-colors shadow-lg disabled:opacity-60">{status === "sending" ? "신청 중..." : "알림 신청하기"}</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

// 가로 스크롤 필터 줄: 오른쪽에 더 있을 때만 그라데이션+화살표 힌트를 보여준다
const ScrollRow = ({ children }) => {
    const ref = React.useRef(null);
    const [more, setMore] = useState(false);
    const check = () => {
        const el = ref.current;
        if (el) setMore(el.scrollWidth - el.clientWidth - el.scrollLeft > 8);
    };
    useEffect(() => {
        check();
        window.addEventListener('resize', check);
        return () => window.removeEventListener('resize', check);
    }, []);
    return (
        <div className="relative">
            <div ref={ref} onScroll={check} className="flex items-center gap-2 overflow-x-auto filter-scroll-container pb-2">
                {children}
            </div>
            <div className={`pointer-events-none absolute right-0 top-0 bottom-2 w-10 bg-gradient-to-l from-white to-transparent flex items-center justify-end pr-0.5 transition-opacity ${more ? 'opacity-100' : 'opacity-0'}`}>
                <Icon name="chevron-right" className="w-4 h-4 text-slate-400 animate-pulse" />
            </div>
        </div>
    );
};

// "26.03.11" 또는 "26.03.11 18:00" 형식 파싱 (그 외 형식은 null)
const parseDotDate = (s) => {
    if (!s) return null;
    const m = /^(\d{2})\.(\d{2})\.(\d{2})(?:\s+(\d{1,2}):(\d{2}))?$/.exec(s.trim());
    if (!m) return null;
    const hour = m[4] !== undefined ? +m[4] : 23;
    const minute = m[5] !== undefined ? +m[5] : 59;
    return new Date(2000 + +m[1], +m[2] - 1, +m[3], hour, minute);
};

const App = () => {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [activeTabs, setActiveTabs] = useState([]);       // [] = 전체
    const [activeJobTypes, setActiveJobTypes] = useState([]);
    const [activeRegions, setActiveRegions] = useState([]);
    const [sortBy, setSortBy] = useState('latest'); // 'latest' | 'deadline'
    const [lastSync, setLastSync] = useState(null);
    const [archiveCounts, setArchiveCounts] = useState({}); // instId → 누적 아카이브 건수
    const [mainView, setMainView] = useState(typeof location !== 'undefined' && location.hash === '#guide' ? 'guide' : 'jobs');
    const [showContact, setShowContact] = useState(false);
    const [showRequest, setShowRequest] = useState(false);
    const [showNotify, setShowNotify] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showTop, setShowTop] = useState(false);
    const navRef = React.useRef(null);

    // 스크롤을 내리면 '맨 위로' 버튼 노출
    useEffect(() => {
        const onScroll = () => setShowTop(window.scrollY > 400);
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    // 모바일 가로 네비: 현재 선택된 항목이 화면에 보이도록 스크롤
    useEffect(() => {
        const el = navRef.current?.querySelector('.nav-link.active');
        if (el && el.scrollIntoView) el.scrollIntoView({ inline: 'center', block: 'nearest' });
    }, [mainView]);

    const institutions = [
        { id: 'nhis', name: '국민건강보험공단', shortName: '건보공단', url: 'https://nhis.kpcice.kr', specs: {
            recruitSchedule: '연 2회 (상반기 3~4월, 하반기 8~9월)', seasonMonths: [3, 4, 8, 9],
            stages: '서류심사(공개경쟁 일반 7배수) → 필기시험(2~3배수) → 인성검사·증빙서류 제출 → 면접시험',
            written: 'NCS 직업기초능력 60문항 + 직무시험(법률) 20문항, 총 80문항. 직무시험은 직렬에 따라 「국민건강보험법」 또는 「노인장기요양보험법」(요양직)이 출제됩니다. 과목당 40% 미만이면 과락, 전 과목 60% 이상이 통과 기준입니다.',
            docs: '서류 배수 통과가 사실상 정량 점수 싸움입니다. 어학(토익 등)·컴활 1급·한국사 등 공고에 명시된 가점 항목을 빠짐없이 채워 두는 것이 전제 조건입니다.',
            point: '필기 배수가 커서 서류만으로는 변별이 잘 되지 않습니다. 가점을 만점 가까이 채운 뒤, 법률 과목을 조문 단위로 반복 회독하는 쪽이 합격 확률을 크게 올립니다.' } },
        { id: 'hira', name: '건강보험심사평가원', shortName: '심평원', url: 'https://hira.recruitlab.co.kr', specs: {
            recruitSchedule: '연 2회 (상반기 4~5월, 하반기 9~10월)', seasonMonths: [4, 5, 9, 10],
            stages: '1차 서류심사 → 2차 필기시험(인성검사 병행) → 3차 면접심사',
            written: 'NCS 기반 직업기초능력평가와 직무수행능력평가를 함께 치릅니다. 직종·직군별로 출제 범위와 전형 단계가 달라지므로 지원 직군의 공고문 확인이 필수입니다.',
            docs: '심사직은 임상 경력 요건이 지원 자격 자체에 걸리는 경우가 많습니다. 요양기관 종별·근무 기간을 증빙 가능한 형태로 정리해 두어야 합니다.',
            point: '보건의료 데이터를 다루는 기관 특성상 ADsP·SQLD 같은 데이터 자격이 자기소개서와 면접에서 실제 설득력을 만듭니다. 심사 기준·급여 청구 흐름을 이해하고 있다는 점을 사례로 보여주세요.' } },
        { id: 'nps', name: '국민연금공단', shortName: '국민연금', url: 'https://nps.saramin.co.kr', specs: {
            recruitSchedule: '연 2회 (상반기 4월, 하반기 9월)', seasonMonths: [4, 9],
            stages: '서류전형(10배수) → 인성검사 → 필기시험(2배수) → 면접전형 (최종은 필기·면접 5:5 합산)',
            written: '직업기초능력평가 + 종합직무지식평가로 구성됩니다. 종합직무지식평가는 직렬별로 전공 과목 배분이 달라, 지원 직렬의 출제 비중을 먼저 확인한 뒤 학습 범위를 좁히는 것이 효율적입니다.',
            docs: '사회복지사 1급 등 직무 연계 자격의 가점 비중이 높은 편입니다. 자격 취득 시점이 접수 마감일 기준으로 인정되는지 공고에서 확인하세요.',
            point: '필기와 면접이 5:5로 합산되므로 필기 고득점이 면접 열세를 덮을 수 있는 구조입니다. 종합직무지식 난이도가 높은 편이라 준비 기간을 길게 잡는 편이 안전합니다.' } },
        { id: 'comwel', name: '근로복지공단', shortName: '근로복지', url: 'https://www.comwel.or.kr/recruit', specs: {
            recruitSchedule: '연 2회 (상반기 4~5월, 하반기 9~10월)', seasonMonths: [4, 5, 9, 10],
            stages: '서류전형 → 필기전형 → 면접전형',
            written: '전 직렬 공통으로 NCS 직업기초능력을 치르고, 행정직(일반) 6급 일반전형은 직무기초지식평가를 추가로 응시합니다. 직무기초지식은 산재보상·고용보험 등 공단 핵심 사업과 맞닿아 있습니다.',
            docs: '블라인드 원칙이 엄격해 학교·출신 등 식별 정보가 기재되면 불이익이 발생할 수 있습니다. 직업상담사 2급·사회복지사 1급 등 직무 연계 자격을 우선 확보하세요.',
            point: '산재보험·고용보험 제도를 이해해 두면 직무기초지식과 면접 답변을 동시에 강화할 수 있습니다. 제도 지식이 곧 지원 동기의 근거가 됩니다.' } },
        { id: 'neca', name: '한국보건의료연구원', shortName: '보의연', url: 'https://www.neca.re.kr', specs: {
            recruitSchedule: '수시 및 상·하반기 통합 채용', seasonMonths: [],
            stages: '서류심사 → 면접(직무 발표·연구 역량 검증 포함) 중심으로 진행되며, 필기시험 없이 치러지는 공고가 많습니다.',
            written: '표준화된 필기시험보다는 연구계획 발표, 직무 관련 과제 등 직무수행능력 검증 방식이 사용되는 경우가 일반적입니다. 공고별로 전형이 달라 반드시 원문을 확인하세요.',
            docs: '석·박사 학위와 연구 실적(논문·보고서·연구 참여 이력)이 서류 평가의 실질적 기준입니다. 제1저자 여부와 연구에서 맡은 역할을 명확히 기술하세요.',
            point: '근거중심 보건의료(HTA)를 다루는 기관인 만큼, 임상 경험을 "연구 질문으로 바꿀 수 있는 사람"임을 보여주는 서술이 유효합니다.' } },
        { id: 'kuksiwon', name: '한국보건의료인국가시험원', shortName: '국시원', url: 'https://dware.intojob.co.kr', specs: {
            recruitSchedule: '연 1~2회 (하반기 집중)', seasonMonths: [9, 10, 11],
            stages: '1차 서류심사 → 2차 종합면접 구조로 진행되는 공고가 다수입니다.',
            written: '별도 필기시험 없이 서류·면접 중심으로 선발하는 경우가 많습니다. 취업지원대상자 가산은 필기·면접 만점의 40% 이상 득점자에게만 적용됩니다.',
            docs: '시험 출제·관리 업무 특성상 행정·기획 문서 작성 역량과 보건의료 직역 이해를 함께 봅니다. 문서 작업 경험을 구체적 산출물 단위로 정리하세요.',
            point: '필기 부담이 적은 대신 서류·면접의 변별력이 큽니다. 국가시험 시행이라는 공적 업무의 정확성·보안 요구를 이해하고 있음을 답변에 담으세요.' } },
        { id: 'koiha', name: '의료기관평가인증원', shortName: '인증원', url: 'https://koiha.recruiter.co.kr', specs: {
            recruitSchedule: '상·하반기 및 결원 수시 채용', seasonMonths: [],
            stages: '서류전형 → 면접전형 중심의 수시 채용이 일반적이며, 공고에 따라 인성검사가 추가됩니다.',
            written: '정기 공채형 필기시험보다는 직무 경험 검증과 면접 비중이 큽니다. 조사위원 직무는 인증 기준에 대한 실무 이해를 직접 묻는 질문이 나옵니다.',
            docs: '공인영어성적 제출을 요구하는 공고가 있으며, 의료기관 인증·QPS(환자안전) 실무 경력이 핵심 평가 요소입니다.',
            point: '병원 인증 준비를 직접 해 본 경험(기준 해석, 근거 자료 준비, 부서 조율)이 있다면 가장 강력한 무기입니다. 담당했던 기준 항목을 구체적으로 제시하세요.' } },
        { id: 'redcross', name: '대한적십자사', shortName: '적십자사', url: 'https://www.redcross.or.kr/recruit/', specs: {
            recruitSchedule: '본사 통합 및 각 지사별 수시', seasonMonths: [],
            stages: '서류전형 → 면접전형(직무인성 심층 종합면접)이 기본 골격이며, 연도·직렬에 따라 인적성 검사가 추가된 사례도 있습니다.',
            written: '면접에서 직무전문성·문제해결능력·조직이해능력·대인관계능력·직업윤리를 평가 항목으로 명시합니다. 각 항목에 대응하는 경험 사례를 미리 매칭해 두세요.',
            docs: '헌혈·봉사 실적을 우대 요소로 반영하는 공고가 있습니다. 혈액사업·재난구호 등 지원 사업 분야를 명확히 골라 지원 동기를 좁히는 것이 좋습니다.',
            point: '인도주의라는 기관 미션에 대한 이해도가 면접에서 실제로 갈립니다. 추상적 공감이 아니라 본인의 경험과 연결된 이유를 준비하세요.' } },
        { id: 'mohw', name: '보건복지부 및 소속기관', shortName: '보건복지부', url: 'https://www.mohw.go.kr', specs: {
            recruitSchedule: '수시 채용 (공무직·임기제 중심)', seasonMonths: [],
            stages: '서류전형 → 면접전형이 일반적이며, 소속기관·직위 유형(공무직/임기제/기간제)에 따라 절차가 크게 달라집니다.',
            written: '표준 필기시험은 통상 없고, 직무수행계획서·경력기술서 심사와 면접으로 평가합니다. 임기제 공무원은 경력·자격 요건이 지원 자격에 명시됩니다.',
            docs: '공고에서 요구하는 경력 연수·자격을 충족하는지가 1차 관문입니다. 경력증명서의 직무 내용이 공고의 담당 업무와 겹치도록 기술하세요.',
            point: '보건복지부 공고에는 소속·산하기관 채용이 함께 게시되는 경우가 있습니다. 본 사이트는 원 기관에서 이미 수집된 공고는 중복 표시하지 않습니다.' } },
        { id: 'khepi', name: '한국건강증진개발원', shortName: '건강증진원', url: 'https://khepi-hr.jobnlab.co.kr/', specs: {
            recruitSchedule: '수시 및 상·하반기 채용', seasonMonths: [],
            stages: '서류전형 → 면접전형 구조가 일반적이며, 직무 관련 발표·과제가 포함되는 공고가 있습니다.',
            written: '공채형 필기보다 직무 경험·사업 기획 역량 검증 비중이 큽니다. 지원 사업단(금연, 영양, 신체활동, 지역사회 통합건강증진 등)을 특정해 준비하세요.',
            docs: '보건교육사, 건강증진 사업 수행 경력이 실질적 우대 요소입니다. 사업 기획·평가 경험을 지표(참여자 수, 사업 성과 등) 중심으로 기술하면 좋습니다.',
            point: '국가 건강증진 사업의 기획·평가를 수행하는 기관입니다. 임상 현장에서 본 문제를 "정책·사업 단위 개선안"으로 옮겨 말할 수 있으면 강점이 됩니다.' } },
        { id: 'nmc', name: '국립중앙의료원', shortName: '중앙의료원', url: 'https://nmc.recruiter.co.kr/app/jobnotice/list', specs: {
            recruitSchedule: '수시 채용 (직무별 개별 공고)', seasonMonths: [],
            stages: '서류전형 → 면접전형 중심이며, 계약직·무기계약직·정규직 등 고용형태에 따라 절차가 다릅니다.',
            written: '별도 필기시험 없이 직무 관련 경력·자격 검증과 면접으로 선발하는 공고가 많습니다. 연구직은 연구계획·실적 검토가 포함될 수 있습니다.',
            docs: '공고마다 요구 자격·경력이 명확히 다르므로 지원 자격 충족 여부 확인이 우선입니다. 공공보건의료 사업 참여 경험이 있으면 명시하세요.',
            point: '공공보건의료의 중추 기관으로 행정·연구·사업 직무를 함께 채용합니다. 본 사이트는 임상 진료 직역(전공의·병동 간호 등) 공고는 제외하고 비임상 직무만 수집합니다.' } },
        { id: 'kac', name: '한국공항공사(보건관리자)', shortName: '공항공사', url: 'https://kac.careerlink.kr/jobs', specs: {
            recruitSchedule: '결원 발생 시 수시 (통합 공고 내 직무별 선발)', seasonMonths: [],
            stages: '서류전형 → 면접전형이 일반적이며, 통합 채용 공고 안에 보건관리자 직무가 포함되어 공고되는 경우가 많습니다.',
            written: '보건관리자 직무는 필기시험보다 자격 요건 충족과 산업보건 실무 경험 검증이 중심입니다.',
            docs: '「산업안전보건법」상 보건관리자 선임 자격(간호사, 산업위생관리기사 등)이 필수입니다. 자격 종류에 따라 지원 가능 여부가 갈립니다.',
            point: '사업장 보건관리는 건강진단 사후관리, 작업환경 개선, 근로자 건강상담이 핵심 업무입니다. 본 사이트는 통합 공고 본문까지 확인해 보건관리자 채용만 선별합니다.' } }
    ];

    useEffect(() => {
        const loadJobs = () => {
            fetch('jobs.json?t=' + Date.now())
                .then(r => r.ok ? r.json() : { jobs: [] })
                .then(data => {
                    const list = (data.jobs || []).filter(j => j && j.title).map((j, i) => ({ id: 'job_' + i, ...j }));
                    const sortKey = (job) => { const d = parseDotDate(job.startDate || job.postedDate); return d ? d.getTime() : 0; };
                    list.sort((a, b) => sortKey(b) - sortKey(a));
                    setJobs(list);
                    if (data.lastSync) setLastSync(new Date(data.lastSync));
                    setLoading(false);
                })
                .catch(() => setLoading(false));
        };
        // 누적 이력은 기관별 아카이브 건수 표시에만 쓰므로 최초 1회만 불러온다.
        // (공채 비수기에 진행중 공고가 적을 때 "지난 공고" 진입점을 만들어 주는 용도)
        fetch('history.json?t=' + Date.now())
            .then(r => r.ok ? r.json() : { jobs: [] })
            .then(data => {
                const counts = {};
                (data.jobs || []).forEach(j => {
                    if (j && j.instId) counts[j.instId] = (counts[j.instId] || 0) + 1;
                });
                setArchiveCounts(counts);
            })
            .catch(() => {});

        loadJobs();
        const timer = setInterval(loadJobs, 10 * 60 * 1000); // 열어둔 화면도 10분마다 자동 갱신
        return () => clearInterval(timer);
    }, []);

    // ⚠️ matchType/matchRegion은 아래 filteredJobs useMemo에서 사용하므로 반드시 먼저 정의해야 한다.
    //    (const는 호이스팅되지 않아, 뒤에 두면 필터 선택 시 TDZ ReferenceError로 앱이 크래시함)
    // ⚠️ 아래 파생값들은 반드시 렌더 블록보다 위에서 정의해야 한다.
    //    (JSX에서 먼저 참조되면 TDZ ReferenceError로 앱 전체가 언마운트된다)
    const currentMonth = new Date().getMonth() + 1;
    const seasonNow = institutions.filter(i => i.specs.seasonMonths.includes(currentMonth));
    // 비수기(=이번 달 공채 기관이 없음)에는 "다음 시즌이 언제인지"가 가장 필요한 정보다.
    // 이번 달 다음으로 공채가 있는 달을 찾아 그 달의 기관을 함께 보여준다.
    const nextSeason = (() => {
        if (seasonNow.length > 0) return null;
        for (let step = 1; step <= 12; step++) {
            const m = ((currentMonth - 1 + step) % 12) + 1;
            const list = institutions.filter(i => i.specs.seasonMonths.includes(m));
            if (list.length > 0) return { month: m, list };
        }
        return null;
    })();
    const totalArchive = Object.values(archiveCounts).reduce((a, b) => a + b, 0);

    const matchType = (sel, actual) => sel === '계약직'
        ? (actual.includes('계약직') || actual.includes('기간제'))
        : actual.includes(sel);
    const matchRegion = (sel, actual) => {
        if (sel === '경인') return actual.includes('경기') || actual.includes('인천');
        if (sel === '대전충남') return actual.includes('대전') || actual.includes('세종') || actual.includes('충남');
        return actual.includes(sel);
    };

    const filteredJobs = useMemo(() => {
        let result = jobs.filter(job => {
            // 마감되었거나 접수기한이 지난 공고는 화면에서 숨김
            if (job.status === '마감') return false;
            const endDt = parseDotDate(job.endDate);
            if (endDt && endDt < new Date()) return false;

            const matchesSearch = job.title?.toLowerCase().includes(searchTerm.toLowerCase());
            const matchesInst = activeTabs.length === 0 || activeTabs.includes(job.instId);

            const actualJobType = job.jobType || "정규직";
            const matchesType = activeJobTypes.length === 0 || activeJobTypes.some(t => matchType(t, actualJobType));

            const actualRegion = job.region || "전국";
            const matchesRegion = activeRegions.length === 0 || activeRegions.some(r => matchRegion(r, actualRegion));

            return matchesSearch && matchesInst && matchesType && matchesRegion;
        });
        if (sortBy === 'deadline') {
            result = [...result].sort((a, b) => {
                const da = parseDotDate(a.endDate);
                const db = parseDotDate(b.endDate);
                if (!da && !db) return 0;
                if (!da) return 1;   // 마감일 미상은 뒤로
                if (!db) return -1;
                return da - db;
            });
        }
        return result;
    }, [jobs, searchTerm, activeTabs, activeJobTypes, activeRegions, sortBy]);

    // 검색창 예시(회색 글씨)는 실제 수집된 공고 제목에 존재하는 단어만 노출한다.
    // → 예시를 검색했을 때 결과가 항상 뜨도록 보장. (없으면 일반 예시로 폴백)
    const searchPlaceholder = useMemo(() => {
        const candidates = ['간호', '보건', '공무직', '기간제', '연구', '행정', '전문직', '사회복지', '시설', '채용'];
        const titles = jobs.map(j => (j.title || ''));
        const hits = candidates.filter(c => titles.some(t => t.includes(c))).slice(0, 3);
        const ex = hits.length ? hits.join(', ') : '채용, 공고';
        return `공고 제목으로 검색 (예: ${ex})...`;
    }, [jobs]);

    // 다중 선택 토글: 'all'을 누르면 전체(빈 배열)로 초기화, 그 외에는 켜고 끄기
    const toggleFilter = (setter, value) => {
        if (value === 'all') { setter([]); return; }
        setter(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
    };

    // 수집 시각은 항상 한국 표준시(KST)로 표기
    const formatDate = (d) => d ? d.toLocaleDateString('ko-KR', { timeZone: 'Asia/Seoul', year: 'numeric', month: 'long', day: 'numeric' }) : '확인 중...';
    const formatTime = (d) => d ? d.toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false }) : '';

    // 접수 시작일이 오늘 포함 2일 이내면 NEW 배지 (날짜 단위 비교)
    const isNew = (job) => {
        const start = parseDotDate(job.startDate);
        if (!start) return false;
        const s = new Date(start); s.setHours(0, 0, 0, 0);
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const diffDays = Math.round((today - s) / 86400000);
        return diffDays >= 0 && diffDays <= 2;
    };

    // 마감까지 남은 날짜 (7일 이내만 배지로 표시)
    const getDday = (job) => {
        const end = parseDotDate(job.endDate);
        if (!end) return null;
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const endDay = new Date(end); endDay.setHours(0, 0, 0, 0);
        const diff = Math.round((endDay - today) / 86400000);
        if (diff < 0) return null;
        if (diff === 0) return { label: '오늘 마감', urgent: true };
        if (diff <= 3) return { label: `마감 D-${diff}`, urgent: true };
        if (diff <= 7) return { label: `마감 D-${diff}`, urgent: false };
        return null;
    };

    return (
        <div className="max-w-5xl mx-auto p-4 md:p-8 flex flex-col min-h-[100dvh]">
            
            <nav ref={navRef} className="mb-10 -mx-4 md:mx-0 px-4 md:px-0 border-b border-slate-200 flex items-center gap-0.5 overflow-x-auto no-scrollbar whitespace-nowrap text-[12.5px] md:text-[13px] font-bold">
                <button onClick={() => { setMainView('jobs'); if (history.replaceState) history.replaceState(null, '', location.pathname); }} className={`nav-link ${mainView === 'jobs' ? 'active' : 'text-slate-500 hover:text-slate-800'}`}>홈</button>
                <button onClick={() => { setMainView('guide'); if (history.replaceState) history.replaceState(null, '', '#guide'); }} className={`nav-link ${mainView === 'guide' ? 'active' : 'text-slate-500 hover:text-slate-800'}`}>기관별 합격 가이드</button>
                <a href="guide.html" className="nav-link text-slate-500 hover:text-slate-800">근무환경·워라밸</a>
                <a href="tips.html" className="nav-link text-slate-500 hover:text-slate-800">채용 트렌드</a>
                <a href="career.html" className="nav-link text-slate-500 hover:text-slate-800">임상경력 활용</a>
                <a href="license.html" className="nav-link text-slate-500 hover:text-slate-800">서류 가점 전략</a>
                <a href="interview.html" className="nav-link text-slate-500 hover:text-slate-800">면접 필승 가이드</a>
            </nav>

            <header className="mb-10 space-y-4">
                <div className="flex flex-wrap gap-2">
                    <span className="bg-blue-600 text-white px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span> 1시간 주기 자동 업데이트</span>
                    <span className="bg-white border border-slate-200 text-slate-600 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm flex items-center gap-1"><Icon name="calendar" className="w-3 h-3 text-blue-500" /> 기준일자: {formatDate(lastSync)}</span>
                    <span className="bg-white border border-slate-200 text-slate-500 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm flex items-center gap-1"><Icon name="clock" className="w-3 h-3" /> 최근 수집: {formatTime(lastSync)} KST</span>
                    <button onClick={() => setShowRequest(true)} className="bg-white border border-blue-200 text-blue-600 px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm flex items-center gap-1 hover:bg-blue-50 transition-colors"><Icon name="plus-circle" className="w-3 h-3" /> 기관 추가 요청</button>
                    <button onClick={() => setShowNotify(true)} className="bg-blue-600 text-white px-2.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm flex items-center gap-1 hover:bg-blue-700 transition-colors"><Icon name="bell" className="w-3 h-3" /> 채용 알림 받기</button>
                </div>
                <div className="space-y-2.5">
                    <h1 className="text-[26px] md:text-[34px] font-black text-slate-900 leading-[1.22] tracking-tight break-keep">
                        <span className="bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">보건의료 공기업 채용 통합 포털</span>
                    </h1>
                    <p className="text-[13.5px] md:text-[15px] text-slate-500 font-medium leading-relaxed max-w-2xl break-keep">국민건강보험공단·건강보험심사평가원·국민연금공단·근로복지공단 등 12개 기관의 공공기관 채용 공고를 1시간마다 자동으로 모아 보여드립니다. 보건관리자·보건직·행정직 공고와 기관별 전형 절차·근무환경 정보까지 한곳에서 확인하세요.</p>
                </div>
            </header>

            {mainView === 'jobs' ? (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 md:gap-8">
                    <aside className="lg:col-span-1 space-y-6 order-2 lg:order-1">
                        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm text-left">
                            <h2 className="text-[11px] font-black text-slate-400 uppercase mb-4 tracking-widest flex items-center gap-1">
                                <Icon name="link" className="w-3 h-3" /> 기관별 채용 사이트
                            </h2>
                            <nav className="space-y-3">
                                {institutions.map(inst => (
                                    <div key={inst.id} className="pb-3 border-b border-slate-50 last:border-0 last:pb-0">
                                        <div className="flex items-center justify-between text-[13px] font-bold text-slate-700">
                                            <button onClick={() => window.open(inst.url, '_blank')} className="hover:text-blue-600 transition-colors flex items-center gap-1.5 text-left">
                                                <Icon name="building-2" className="w-3.5 h-3.5 text-slate-400" />
                                                {inst.name}
                                            </button>
                                            <button onClick={() => window.open(inst.url, '_blank')} className="text-slate-300 hover:text-blue-600 transition-colors">
                                                <Icon name="external-link" className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </nav>
                            <button onClick={() => setShowRequest(true)} className="mt-4 block w-full text-center py-2.5 rounded-xl border border-dashed border-blue-300 text-blue-600 text-xs font-bold hover:bg-blue-50 transition-colors">+ 원하는 기관이 없나요? 추가 요청하기</button>
                        </div>
                    </aside>
                    
                    <main className="lg:col-span-3 space-y-6 order-1 lg:order-2">
                        <div className="bg-white p-4 md:p-5 rounded-2xl border border-slate-200 shadow-sm flex flex-col gap-4">
                            <div className="relative">
                                <Icon name="search" className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                                <input type="text" placeholder={searchPlaceholder} onChange={e => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-100 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium transition-all" />
                            </div>

                            <div className="flex flex-col gap-3">
                                <p className="text-[10.5px] text-slate-400 font-medium flex items-center gap-1 -mb-1"><Icon name="mouse-pointer-click" className="w-3 h-3" /> 여러 개를 선택하면 함께 볼 수 있어요</p>
                                <ScrollRow>
                                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest mr-1 shrink-0 flex items-center gap-1 w-12"><Icon name="building" className="w-3 h-3"/> 기관</span>
                                    <button onClick={() => toggleFilter(setActiveTabs, 'all')} className={`flex-shrink-0 px-3.5 py-1.5 rounded-lg text-xs font-bold border transition-all ${activeTabs.length === 0 ? 'bg-slate-900 text-white border-slate-900 shadow-md' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-slate-800'}`}>전체</button>
                                    {institutions.map(inst => (
                                        <button key={inst.id} onClick={() => toggleFilter(setActiveTabs, inst.id)} className={`flex-shrink-0 px-3.5 py-1.5 rounded-lg text-xs font-bold border transition-all ${activeTabs.includes(inst.id) ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-100' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50 hover:text-blue-600'}`}>
                                            {inst.shortName}
                                        </button>
                                    ))}
                                </ScrollRow>

                                <ScrollRow>
                                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest mr-1 shrink-0 flex items-center gap-1 w-12"><Icon name="briefcase" className="w-3 h-3"/> 계약</span>
                                    {[ { id: 'all', label: '전체' }, { id: '정규직', label: '정규직' }, { id: '무기계약직', label: '무기계약직' }, { id: '계약직', label: '계약직/기간제' }, { id: '비정규직', label: '비정규직' }, { id: '인턴', label: '체험형 인턴' }].map(type => (
                                        <button key={type.id} onClick={() => toggleFilter(setActiveJobTypes, type.id)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-[11.5px] font-bold border transition-all ${(type.id === 'all' ? activeJobTypes.length === 0 : activeJobTypes.includes(type.id)) ? 'bg-purple-600 text-white border-purple-600 shadow-md shadow-purple-100' : 'bg-white text-slate-500 border-slate-200 hover:bg-purple-50 hover:text-purple-700 hover:border-purple-200'}`}>
                                            {type.label}
                                        </button>
                                    ))}
                                </ScrollRow>

                                <ScrollRow>
                                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest mr-1 shrink-0 flex items-center gap-1 w-12"><Icon name="map-pin" className="w-3 h-3"/> 지역</span>
                                    {[ { id: 'all', label: '전체' }, { id: '전국', label: '전국' }, { id: '서울', label: '서울' }, { id: '경인', label: '경기·인천' }, { id: '강원', label: '강원' }, { id: '대전충남', label: '대전·세종·충남' }, { id: '충북', label: '충북' }, { id: '광주', label: '광주' }, { id: '전북', label: '전북' }, { id: '전남', label: '전남' }, { id: '부산', label: '부산' }, { id: '대구', label: '대구' }, { id: '울산', label: '울산' }, { id: '경북', label: '경북' }, { id: '경남', label: '경남' }, { id: '제주', label: '제주' } ].map(reg => (
                                        <button key={reg.id} onClick={() => toggleFilter(setActiveRegions, reg.id)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-[11.5px] font-bold border transition-all ${(reg.id === 'all' ? activeRegions.length === 0 : activeRegions.includes(reg.id)) ? 'bg-emerald-600 text-white border-emerald-600 shadow-md shadow-emerald-100' : 'bg-white text-slate-500 border-slate-200 hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-200'}`}>
                                            {reg.label}
                                        </button>
                                    ))}
                                </ScrollRow>
                            </div>
                        </div>

                        <div className="flex items-center justify-between px-1">
                            <p className="text-xs font-bold text-slate-500">진행중 공고 <span className="text-blue-600">{filteredJobs.length}</span>건</p>
                            <div className="flex gap-1">
                                <button onClick={() => setSortBy('latest')} className={`px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-all ${sortBy === 'latest' ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}>최신순</button>
                                <button onClick={() => setSortBy('deadline')} className={`px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-all ${sortBy === 'deadline' ? 'bg-red-500 text-white border-red-500' : 'bg-white text-slate-500 border-slate-200 hover:bg-red-50 hover:text-red-500'}`}>마감임박순</button>
                            </div>
                        </div>

                        <div className="space-y-3">
                            {loading ? <div className="py-20 text-center text-slate-300 animate-pulse font-bold text-sm">최신 채용 정보를 동기화 중입니다...</div> :
                                filteredJobs.length > 0 ? (
                                    filteredJobs.map(job => {
                                        const instInfo = institutions.find(i => i.id === job.instId) || { shortName: (job.instId || '').toUpperCase() };
                                        const isClosed = job.status === '마감';
                                        const dday = getDday(job);
                                        return (
                                            <a key={job.id} href={job.link || '#'} target="_blank" rel="noopener noreferrer" aria-label={`${instInfo.shortName} ${job.title} 공고 보기`} className="job-card group block bg-white p-5 md:p-6 rounded-2xl border border-slate-200 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 text-left focus:outline-none focus:ring-2 focus:ring-blue-500">
                                                <div className="flex-1">
                                                    <div className="flex gap-1.5 mb-2 flex-wrap">
                                                        {isNew(job) && <span className="text-[10px] font-black px-2 py-0.5 rounded bg-emerald-500 text-white">NEW</span>}
                                                        {dday && <span className={`text-[10px] font-black px-2 py-0.5 rounded ${dday.urgent ? 'bg-red-500 text-white' : 'bg-orange-100 text-orange-600 border border-orange-200'}`}>{dday.label}</span>}
                                                        <span className="text-[10px] font-black px-2 py-0.5 bg-slate-100 rounded text-slate-500 uppercase tracking-tight">{instInfo.shortName}</span>
                                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${isClosed ? 'text-red-600 bg-red-50 border-red-100' : 'text-blue-600 bg-blue-50 border-blue-100'}`}>{isClosed ? '서류접수마감' : '채용진행중'}</span>
                                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded border text-purple-600 bg-purple-50 border-purple-100">{job.jobType || "정규직"}</span>
                                                        <span className="text-[10px] font-bold px-2 py-0.5 rounded border text-emerald-600 bg-emerald-50 border-emerald-100 flex items-center gap-0.5">
                                                            <Icon name="map-pin" className="w-2.5 h-2.5" /> {job.region || "전국"}
                                                        </span>
                                                    </div>
                                                    <h3 className={`text-[16px] md:text-[17px] font-bold text-slate-800 mb-2 leading-snug break-keep`}>{job.title}</h3>
                                                    <p className="text-[11px] font-bold text-slate-400 flex items-center gap-1"><Icon name="calendar" className="w-3 h-3" /> 접수기간: {job.startDate} ~ <span className={isClosed ? 'text-slate-300' : 'text-red-400'}>{job.endDate}</span></p>
                                                </div>
                                                <span className={`w-full md:w-auto px-7 py-2.5 rounded-xl font-bold text-xs shadow-sm transition-all text-center ${isClosed ? 'bg-slate-100 text-slate-400' : 'bg-slate-900 text-white group-hover:bg-blue-600'}`}>{isClosed ? '모집종료' : '지원하기 →'}</span>
                                            </a>
                                        );
                                    })
                                ) : (
                                    <div className="py-20 text-center bg-white rounded-3xl border border-dashed border-slate-200 flex flex-col items-center justify-center gap-3">
                                        <Icon name="search-x" className="w-10 h-10 text-slate-300" />
                                        <p className="text-slate-400 text-sm font-bold">현재 필터 조건에 맞는 공고가 없습니다.</p>
                                        <button onClick={() => { setActiveTabs([]); setActiveJobTypes([]); setActiveRegions([]); setSearchTerm(''); }} className="mt-2 text-[11px] text-blue-600 font-bold hover:underline">필터 전체 초기화</button>
                                    </div>
                                )
                            }
                        </div>

                        {/* 공채는 계절을 크게 타기 때문에(3~4월·8~10월 집중) 비수기에 처음 방문한
                            사람은 진행중 공고 몇 건만 보고 "정보가 없는 사이트"로 오해하기 쉽다.
                            → 다음 채용 시즌 예고와 누적 아카이브 진입점을 함께 제공한다. */}
                        <section className="bg-white p-5 md:p-7 rounded-2xl border border-slate-200 shadow-sm text-left space-y-6">
                            <div>
                                <h2 className="text-[15px] font-black text-slate-900 flex items-center gap-2"><Icon name="calendar-days" className="w-4 h-4 text-blue-600" /> 기관별 채용 시즌</h2>
                                <p className="text-[12px] text-slate-400 font-medium mt-1">
                                    지금 공고가 적다면 비수기일 수 있습니다. 주요 기관의 공채는 <strong className="text-slate-500">상반기 3~5월</strong>, <strong className="text-slate-500">하반기 8~10월</strong>에 몰립니다.
                                </p>
                            </div>

                            {seasonNow.length > 0 ? (
                                <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                                    <p className="text-[12.5px] font-bold text-blue-900 leading-relaxed">
                                        📌 {currentMonth}월은 <strong>{seasonNow.map(i => i.shortName).join(' · ')}</strong> 공채가 집중되는 시기입니다. 공고가 아직 안 보인다면 곧 올라올 수 있으니 다시 확인해 주세요.
                                    </p>
                                </div>
                            ) : nextSeason && (
                                <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
                                    <p className="text-[12.5px] font-bold text-amber-900 leading-relaxed">
                                        🌙 {currentMonth}월은 정기 공채 비수기입니다. 다음 공채 시즌은 <strong>{nextSeason.month}월</strong>이며, <strong>{nextSeason.list.map(i => i.shortName).join(' · ')}</strong> 채용이 시작됩니다. 그때까지도 수시 채용 공고는 계속 올라옵니다.
                                    </p>
                                </div>
                            )}

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
                                {institutions.map(inst => {
                                    const inSeason = inst.specs.seasonMonths.includes(currentMonth);
                                    const n = archiveCounts[inst.id] || 0;
                                    return (
                                        <div key={inst.id} className="flex items-center justify-between gap-3 py-1.5 border-b border-slate-50 last:border-0">
                                            <div className="min-w-0">
                                                <a href={'inst-' + inst.id + '.html'} className={`text-[13px] font-bold hover:underline ${inSeason ? 'text-blue-700' : 'text-slate-700'}`}>
                                                    {inSeason && '🔵 '}{inst.shortName}
                                                </a>
                                                <p className="text-[11px] text-slate-400 font-medium truncate">{inst.specs.recruitSchedule}</p>
                                            </div>
                                            <a href={'inst-' + inst.id + '.html'} className="shrink-0 text-[11px] font-bold text-slate-500 bg-slate-100 hover:bg-blue-100 hover:text-blue-700 px-2.5 py-1 rounded-full transition-colors">
                                                {n > 0 ? `지난 공고 ${n}건` : '기관 정보'}
                                            </a>
                                        </div>
                                    );
                                })}
                            </div>

                            {totalArchive > 0 && (
                                <p className="text-[12px] text-slate-500 font-medium bg-slate-50 border border-slate-200 rounded-xl p-4 leading-relaxed">
                                    📁 지금까지 수집한 공고 <strong className="text-slate-800">{totalArchive}건</strong>을 기관별 상세 페이지에 보관하고 있습니다. 마감된 공고도 남아 있어, 그 기관이 <strong className="text-slate-800">어떤 직무를 어떤 고용형태로 뽑아 왔는지</strong> 확인할 수 있습니다.
                                </p>
                            )}
                        </section>
                    </main>
                </div>
            ) : (
                <div className="bg-white p-8 md:p-12 rounded-3xl border border-slate-200 shadow-sm space-y-16 text-left">
                    <header className="border-b border-slate-100 pb-8">
                        <h2 className="text-2xl font-black text-slate-900 mb-4">보건의료 공공기관별 전형 절차·필기 과목 분석</h2>
                        <p className="text-slate-500 font-medium leading-relaxed">이 페이지는 <strong className="text-slate-700">"어떻게 들어가는가"</strong>만 다룹니다. 기관별 전형 단계, 필기 시험 구성, 서류 요건과 가점 항목을 정리했습니다.</p>
                        <div className="mt-5 bg-slate-50 border border-slate-200 rounded-2xl p-5 text-[13px] text-slate-600 font-medium leading-relaxed space-y-1.5">
                            <p className="font-bold text-slate-800 mb-2">📚 다른 페이지와의 역할 구분</p>
                            <p>· <a href="guide.html" className="text-blue-600 font-bold hover:underline">기관별 근무환경·워라밸</a> — 본사 위치, 순환근무, 업무강도, 조직문화, <strong>신입 초임(ALIO 공시 기준)</strong> 등 <strong>입사 이후의 삶</strong></p>
                            <p>· <strong>기관별 상세 페이지</strong> — 기관별 누적 공고 아카이브와 고용형태·근무지역 수집 통계 (각 기관 카드 하단 링크)</p>
                        </div>
                        <p className="text-[12px] text-slate-400 font-medium mt-4">※ 전형 절차와 필기 과목은 채용 연도·직렬·고용형태에 따라 달라집니다. 아래 내용은 최근 공고를 기준으로 한 일반적인 경향이며, 지원 전 반드시 해당 공고 원문을 확인하세요.</p>
                    </header>

                    <div className="grid grid-cols-1 gap-12">
                        {institutions.map(inst => (
                            <article key={inst.id} className="space-y-5">
                                <h3 className="text-xl font-bold text-blue-700 flex items-center gap-2 underline underline-offset-8 decoration-blue-100"><Icon name="building" /> {inst.name} ({inst.shortName})</h3>
                                <div className="text-[14px] text-slate-700 space-y-3 font-medium leading-relaxed">
                                    <p><strong>📅 채용 주기:</strong> {inst.specs.recruitSchedule}</p>
                                    <p><strong>🪜 전형 단계:</strong> {inst.specs.stages}</p>
                                    <p><strong>✍️ 필기·직무 평가:</strong> {inst.specs.written}</p>
                                    <p><strong>📄 서류 요건·가점:</strong> {inst.specs.docs}</p>
                                    <div className="bg-blue-50 p-6 rounded-2xl text-blue-900 text-[13.5px] border border-blue-100 mt-2 shadow-inner leading-relaxed">
                                        <strong>💡 준비 포인트:</strong> {inst.specs.point}
                                    </div>
                                    <div className="flex flex-wrap gap-2 pt-1">
                                        <a href={'inst-' + inst.id + '.html'} className="text-[12px] font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-full transition">📋 공고 아카이브·수집 통계</a>
                                        <a href="guide.html" className="text-[12px] font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-full transition">🏢 근무환경·초임 보기</a>
                                        <a href={inst.url} target="_blank" rel="noopener noreferrer" className="text-[12px] font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-full transition">🔗 공식 채용 페이지</a>
                                    </div>
                                </div>
                            </article>
                        ))}
                    </div>
                </div>
            )}

            <section className="mt-20 bg-white p-6 md:p-9 rounded-3xl border border-slate-200 shadow-sm text-left">
                <h2 className="text-xl font-black text-slate-900 mb-1.5 flex items-center gap-2"><Icon name="help-circle" className="text-blue-600" /> 보건의료 취업 자주 묻는 질문 (FAQ)</h2>
                <p className="text-[12px] text-slate-400 font-medium mb-6">탈임상·보건직 공기업 준비생들이 가장 많이 묻는 질문을 모았습니다.</p>
                <div className="divide-y divide-slate-100">
                    {[
                        { q: "보건직 공기업 채용에서 가장 중요한 '서류 컷' 기준은 무엇인가요?", a: "대부분의 기관은 자격증·어학 점수로 서류를 선발하는 '정량 평가' 방식을 채택합니다. 컴활 1급, 한국사 1급, 토익 800점 이상의 기본 스펙을 갖춘 뒤, 직렬별 우대 자격증(사회복지사 1급 등)으로 추가 가점을 확보하는 것이 합격권의 기본입니다." },
                        { q: "임상 경력(병원 근무 경험)이 채용에 얼마나 도움이 되나요?", a: "심평원 심사직, 인증원 조사위원처럼 임상 경험을 직접 요구하는 직무에서는 종합병원급 이상 경력이 사실상 필수 경쟁력입니다. 반면 일반 행정직은 블라인드 원칙상 경력보다 NCS 필기와 정량 스펙이 더 크게 작용합니다. 간호사·방사선사·임상병리사 등 직역과 지원 직무에 따라 경력의 가치가 달라집니다." },
                        { q: "블라인드 채용인데 어떻게 준비해야 하나요?", a: "출신 학교·나이·가족관계 등은 평가에서 배제되므로, 자기소개서와 면접에서 '직무 역량 중심'으로 서술하는 것이 핵심입니다. 기관의 미션·사업을 숙지하고, 본인의 경험을 직무 역량과 연결해 구조화(STAR 기법)하는 연습을 권장합니다." },
                        { q: "공고는 얼마나 자주 갱신되나요?", a: "본 사이트는 각 기관 채용 페이지를 1시간마다 자동 수집하여 진행 중인 공고만 보여드립니다. 마감되었거나 접수 기한이 지난 공고는 자동으로 숨겨집니다. 다만 정확한 자격 요건과 일정은 반드시 각 기관 공식 공고문을 확인하세요." },
                        { q: "원하는 기관이 목록에 없어요. 추가할 수 있나요?", a: "상단 '기관 추가 요청' 버튼이나 하단 '문의하기'를 통해 기관명과 채용 페이지 주소를 남겨주시면, 검토 후 수집 대상에 반영합니다." },
                    ].map((f, i) => (
                        <details key={i} className="group py-4">
                            <summary className="flex items-start gap-2 cursor-pointer list-none font-bold text-slate-900 text-[14.5px] leading-snug break-keep">
                                <span className="text-blue-600 shrink-0">Q.</span>
                                <span className="flex-1">{f.q}</span>
                                <Icon name="chevron-down" className="w-4 h-4 text-slate-400 mt-0.5 shrink-0 transition-transform group-open:rotate-180" />
                            </summary>
                            <p className="mt-3 pl-5 text-[13.5px] text-slate-600 font-medium leading-relaxed break-keep">{f.a}</p>
                        </details>
                    ))}
                </div>
            </section>

            <footer className="mt-20 pt-10 pb-6 border-t border-slate-200 text-center space-y-6">
                <div className="flex justify-center gap-6 text-[12px] font-bold text-slate-500">
                    <a href="about.html" className="hover:text-slate-800 transition-colors">소개·운영정책</a>
                    <span className="text-slate-300">·</span>
                    <a href="privacy.html" className="hover:text-slate-800 transition-colors">개인정보처리방침</a>
                    <span className="text-slate-200">|</span>
                    <button onClick={() => setShowContact(true)} className="hover:text-slate-800 transition-colors">문의하기</button>
                </div>
                <div className="space-y-1">
                    <p className="text-[11px] text-slate-400 font-medium">© 2026 보건의료 채용 포털. All rights reserved.</p>
                    <p className="text-[10px] text-slate-300">모든 채용 정보는 실시간 수집 데이터로, 정확한 내용은 반드시 각 기관의 공식 공고문을 확인하시기 바랍니다.</p>
                </div>
            </footer>

            {/* 맨 위로 스크롤 버튼 (좌측 하단, 챗봇과 겹치지 않게) */}
            {showTop && (
                <button
                    onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                    aria-label="맨 위로 이동"
                    className="fixed bottom-6 left-6 md:bottom-8 md:left-8 z-50 w-11 h-11 rounded-full bg-white border border-slate-200 text-slate-600 shadow-lg hover:text-blue-600 hover:border-blue-300 flex items-center justify-center transition-all animate-in fade-in"
                >
                    <Icon name="arrow-up" className="w-5 h-5" />
                </button>
            )}

            {/* --- AI 탈임상 도우미 챗봇 플로팅 버튼 영역 --- */}
            <div className="fixed bottom-6 right-6 md:bottom-8 md:right-8 z-50 flex flex-col items-end animate-in fade-in duration-500">
                {/* 말풍선 안내창 */}
                <div className="bg-slate-800 text-white text-[11px] font-bold px-3.5 py-2 rounded-xl shadow-lg mb-3 relative animate-bounce">
                    ※ 구글 로그인이 필요해요!
                    <div className="absolute -bottom-1.5 right-6 w-3 h-3 bg-slate-800 rotate-45"></div>
                </div>
                {/* 챗봇 버튼 */}
                <button 
                    onClick={() => window.open('https://gemini.google.com/gem/1ehAKI98f7tQPD3UjfiEGuL-nXJNPyeSf?usp=sharing', '_blank')}
                    className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-5 py-3.5 rounded-full font-black shadow-2xl hover:shadow-blue-500/30 hover:-translate-y-1 transition-all flex items-center gap-2.5 border-2 border-white/20 group"
                    title="AI 탈임상 도우미에게 물어보세요!"
                >
                    <Icon name="bot" className="w-5 h-5 group-hover:animate-bounce" />
                    <span className="hidden md:inline">탈임상 AI 챗봇</span>
                    <span className="md:hidden">AI 챗봇</span>
                </button>
            </div>

            {showContact && (
                <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
                    <div className="bg-white w-full max-w-sm rounded-[2.5rem] p-8 shadow-2xl relative text-center animate-in zoom-in duration-300">
                        <button onClick={() => setShowContact(false)} className="absolute top-6 right-6 text-slate-300 hover:text-slate-900"><Icon name="x" /></button>
                        <Icon name="mail" className="w-14 h-14 mx-auto text-blue-500 mb-4" />
                        <h2 className="text-xl font-black text-slate-900 mb-3">운영자 문의하기</h2>
                        <p className="text-sm text-slate-600 font-medium mb-6 leading-relaxed">기관 추가 요청·오류 제보·건의사항은 아래 버튼으로 남겨주시거나, 메일로 보내주셔도 됩니다.</p>
                        <button onClick={() => { setShowContact(false); setShowRequest(true); }} className="w-full py-4 bg-blue-600 text-white rounded-2xl font-bold hover:bg-blue-700 transition-colors shadow-lg mb-4 flex items-center justify-center gap-2"><Icon name="plus-circle" className="w-4 h-4" /> 기관 추가 · 건의하기</button>
                        <div className="bg-slate-50 p-3 rounded-2xl border border-slate-100 mb-6 flex items-center justify-between gap-2">
                            <span className="font-bold text-blue-600 text-[14px] tracking-tight truncate">samdasu266@gmail.com</span>
                            <div className="flex items-center gap-1 shrink-0">
                                <button onClick={() => { navigator.clipboard.writeText("samdasu266@gmail.com"); setCopied(true); setTimeout(() => setCopied(false), 1500); }} title="주소 복사" className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-500 hover:text-blue-600 hover:border-blue-300 flex items-center justify-center transition-colors"><Icon name={copied ? "check" : "copy"} className="w-4 h-4" /></button>
                                <a href="mailto:samdasu266@gmail.com" title="메일 보내기" className="w-9 h-9 rounded-xl bg-white border border-slate-200 text-slate-500 hover:text-blue-600 hover:border-blue-300 flex items-center justify-center transition-colors"><Icon name="mail" className="w-4 h-4" /></a>
                            </div>
                        </div>
                        <button onClick={() => setShowContact(false)} className="w-full py-4 bg-slate-900 text-white rounded-2xl font-bold hover:bg-blue-600 transition-colors shadow-lg">닫기</button>
                    </div>
                </div>
            )}

            <RequestModal open={showRequest} onClose={() => setShowRequest(false)} />
            <NotifyModal open={showNotify} onClose={() => setShowNotify(false)} institutions={institutions} />
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
