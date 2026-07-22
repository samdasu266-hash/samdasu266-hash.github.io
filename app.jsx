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
    const [mainView, setMainView] = useState(typeof location !== 'undefined' && location.hash === '#guide' ? 'guide' : 'jobs');
    const [showContact, setShowContact] = useState(false);
    const [showRequest, setShowRequest] = useState(false);
    const [copied, setCopied] = useState(false);

    const institutions = [
        { id: 'nhis', name: '국민건강보험공단', shortName: '건보공단', url: 'https://nhis.kpcice.kr', specs: { recruitSchedule: '연 2회 (상반기 3~4월, 하반기 8~9월)', salary: '신입 약 4,400만원 / 평균 약 6,900만원', language: '토익 850점 이상 안정권', cert: '컴활 1급·한국사 심화 등 기본 가점', summary: '서류 가점을 만점으로 채우는 것이 기본 전제입니다.' } },
        { id: 'hira', name: '건강보험심사평가원', shortName: '심평원', url: 'https://hira.recruitlab.co.kr', specs: { recruitSchedule: '연 2회 (상반기 4~5월, 하반기 9~10월)', salary: '신입 약 4,300만원 / 평균 약 7,000만원', language: '토익 850점 이상 (심사직 700+)', cert: 'ADsP, SQLD 등 데이터 역량 우대', summary: '심사직은 종합병원급 이상의 임상 경력이 합격의 핵심입니다.' } },
        { id: 'nps', name: '국민연금공단', shortName: '국민연금', url: 'https://nps.saramin.co.kr', specs: { recruitSchedule: '연 2회 (상반기 4월, 하반기 9월)', salary: '신입 약 3,900만원 / 평균 약 6,000만원', language: '토익 800점 이상 권장', cert: '사회복지사 1급 가점 비중 높음', summary: 'NCS 및 전공 필기 시험의 난이도가 상당히 높은 편입니다.' } },
        { id: 'comwel', name: '근로복지공단', shortName: '근로복지', url: 'https://www.comwel.or.kr/recruit', specs: { recruitSchedule: '연 2회 (상반기 4~5월, 하반기 9~10월)', salary: '신입 약 3,400만원 / 평균 약 5,600만원', language: '토익 750점 이상 우대', cert: '직무 자격증 가점 비중 높음', summary: '블라인드 원칙 준수와 필기 성적이 합격에 결정적입니다.' } },
        { id: 'neca', name: '한국보건의료연구원', shortName: '보의연', url: 'https://www.neca.re.kr', specs: { recruitSchedule: '수시 및 상·하반기 통합 채용', salary: '신입 약 3,300만원 / 평균 약 5,300만원', language: '토익 800점 이상 권장', cert: '석/박사 학위 및 연구 실적 중시', summary: '연구 중심 기관으로 학술적 전문성과 서울 근무의 장점이 큽니다.' } },
        { id: 'kuksiwon', name: '한국보건의료인국가시험원', shortName: '국시원', url: 'https://dware.intojob.co.kr', specs: { recruitSchedule: '연 1~2회 (하반기 집중)', salary: '신입 약 3,700만원 / 평균 약 5,300만원', language: '토익 750점 이상 권장', cert: '행정 및 기획 역량 중시', summary: '서울 광진구 소재 및 비수기 워라밸이 매우 뛰어납니다.' } },
        { id: 'koiha', name: '의료기관평가인증원', shortName: '인증원', url: 'https://koiha.recruiter.co.kr', specs: { recruitSchedule: '상·하반기 및 결원 수시 채용', salary: '신입 약 3,900만원 / 평균 약 6,000만원', language: '공인영어성적 필수 제출', cert: '인증 평가 및 QPS 실무자 우대', summary: '전국 병원 현장 평가 출장이 잦은 직무적 특성이 있습니다.' } },
        { id: 'redcross', name: '대한적십자사', shortName: '적십자사', url: 'https://www.redcross.or.kr/recruit/', specs: { recruitSchedule: '본사 통합 및 각 지사별 수시', salary: '신입 약 3,300만원 / 평균 약 6,000만원', language: '토익 750점 이상 권장', cert: '헌혈·봉사 실적 가점(우대)', summary: '봉사 정신과 기관 미션에 대한 이해도가 면접에서 중요합니다.' } },
        { id: 'mohw', name: '보건복지부 및 소속기관', shortName: '보건복지부', url: 'https://www.mohw.go.kr', specs: { recruitSchedule: '수시 채용', salary: '공무직 보수규정 적용', language: '직무별 상이', cert: '관련 실무경력 중시', summary: '다양한 공무직 및 임기제 채용이 진행됩니다.' } }
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
        loadJobs();
        const timer = setInterval(loadJobs, 10 * 60 * 1000); // 열어둔 화면도 10분마다 자동 갱신
        return () => clearInterval(timer);
    }, []);

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

    // 다중 선택 토글: 'all'을 누르면 전체(빈 배열)로 초기화, 그 외에는 켜고 끄기
    const toggleFilter = (setter, value) => {
        if (value === 'all') { setter([]); return; }
        setter(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
    };
    const matchType = (sel, actual) => sel === '계약직'
        ? (actual.includes('계약직') || actual.includes('기간제'))
        : actual.includes(sel);
    const matchRegion = (sel, actual) => {
        if (sel === '경인') return actual.includes('경기') || actual.includes('인천');
        if (sel === '대전충남') return actual.includes('대전') || actual.includes('세종') || actual.includes('충남');
        return actual.includes(sel);
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
            
            <nav className="mb-10 -mx-4 md:mx-0 px-4 md:px-0 border-b border-slate-200 flex items-center gap-0.5 overflow-x-auto no-scrollbar whitespace-nowrap text-[12.5px] md:text-[13px] font-bold">
                <button onClick={() => { setMainView('jobs'); if (history.replaceState) history.replaceState(null, '', location.pathname); }} className={`nav-link ${mainView === 'jobs' ? 'active' : 'text-slate-500 hover:text-slate-800'}`}>실시간 채용공고</button>
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
                </div>
                <div className="space-y-2.5">
                    <h1 className="text-[26px] md:text-[34px] font-black text-slate-900 leading-[1.22] tracking-tight break-keep">
                        <span className="bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">보건의료 공기업 채용 통합 포털</span>
                    </h1>
                    <p className="text-[13.5px] md:text-[15px] text-slate-500 font-medium leading-relaxed max-w-2xl break-keep">건강보험공단·심평원·국민연금 등 주요 보건의료 공공기관 채용공고를 1시간마다 자동으로 모아 보여드립니다. 기관별 합격 가이드까지 한곳에서 확인하세요.</p>
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
                                <input type="text" placeholder="공고 제목으로 검색 (예: 간호사, 임상병리사, 행정직)..." onChange={e => setSearchTerm(e.target.value)} className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-100 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium transition-all" />
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
                    </main>
                </div>
            ) : (
                <div className="bg-white p-8 md:p-12 rounded-3xl border border-slate-200 shadow-sm space-y-16 text-left">
                    <header className="border-b border-slate-100 pb-8">
                        <h2 className="text-2xl font-black text-slate-900 mb-4">보건의료 공공기관별 심층 합격 전략 분석</h2>
                        <p className="text-slate-500 font-medium leading-relaxed">각 기관의 채용 특성과 핵심 스펙을 정리했습니다. 본인의 강점에 맞는 기관을 골라 전략적으로 준비하세요.</p>
                        <p className="text-[12px] text-slate-400 font-medium mt-3">※ 급여는 ALIO 공시 기준 근사치이며 연도·수당에 따라 편차가 있습니다. 채용 주기·자격·일정 등 세부 기준은 반드시 각 기관 공식 공고를 확인하세요.</p>
                    </header>
                    
                    <div className="grid grid-cols-1 gap-12">
                        {institutions.map(inst => (
                            <article key={inst.id} className="space-y-5">
                                <h3 className="text-xl font-bold text-blue-700 flex items-center gap-2 underline underline-offset-8 decoration-blue-100"><Icon name="building" /> {inst.name} ({inst.shortName})</h3>
                                <div className="text-[14px] text-slate-700 space-y-3 font-medium leading-relaxed">
                                    <p><strong>📅 연간 채용 주기:</strong> {inst.specs.recruitSchedule}에 신입·경력직 채용이 집중됩니다.</p>
                                    <p><strong>💰 처우(ALIO 근사치):</strong> {inst.specs.salary} 수준이며, 공공기관 특유의 안정적인 호봉제와 복지를 갖추고 있습니다.</p>
                                    <p><strong>🎯 핵심 스펙:</strong> 어학은 {inst.specs.language}, 자격증 가점은 {inst.specs.cert} 위주로 준비하는 것이 효율적입니다.</p>
                                    <div className="bg-blue-50 p-6 rounded-2xl text-blue-900 text-[13.5px] border border-blue-100 mt-2 shadow-inner leading-relaxed">
                                        <strong>💡 현직자 합격 꿀팁:</strong> {inst.specs.summary}
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
                    <span className="text-slate-200">|</span>
                    <button onClick={() => setShowContact(true)} className="hover:text-slate-800 transition-colors">문의하기</button>
                </div>
                <div className="space-y-1">
                    <p className="text-[11px] text-slate-400 font-medium">© 2026 보건의료 채용 포털. All rights reserved.</p>
                    <p className="text-[10px] text-slate-300">모든 채용 정보는 실시간 수집 데이터로, 정확한 내용은 반드시 각 기관의 공식 공고문을 확인하시기 바랍니다.</p>
                </div>
            </footer>

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
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
