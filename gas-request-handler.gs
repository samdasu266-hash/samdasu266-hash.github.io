/**
 * 보건공기업 알리미 - Google Apps Script (요청 접수 + 채용 알림 메일)
 *
 * [설치 방법]
 * 1) script.google.com 에서 기존 프로젝트(요청 폼 만든 프로젝트)를 열거나 새 프로젝트 생성
 * 2) 이 파일 내용을 Code.gs 에 붙여넣기
 * 3) 아래 SHEET_ID 를 "보건공기업 알리미 - 요청 접수 내역" 스프레드시트 ID로 설정
 *    (스프레드시트 URL 의 /d/ 와 /edit 사이 문자열)
 * 4) 상단 [배포] → [배포 관리] → 기존 웹앱 옆 연필(수정) → 버전: 새 버전 →
 *    실행 계정: 나, 액세스 권한: 모든 사용자 → [배포]  (URL 이 그대로 유지됨)
 *    ※ 처음 배포라면 [배포] → [새 배포] → 유형: 웹 앱 으로 동일하게 설정
 * 5) 최초 1회 권한 승인(메일 전송/시트 접근/외부 요청) 필요
 *
 * [채용 알림 메일 추가 설정]
 * 6) 편집기에서 함수 목록에서 setupDailyTrigger 를 선택하고 [실행] 을 1회 누른다.
 *    → 매일 오전 8시(KST)에 sendDailyDigest 가 자동 실행되는 트리거가 생성된다.
 *    (이미 트리거가 있으면 중복 생성하지 않는다)
 * 7) 테스트하려면 함수 목록에서 sendTestDigest 를 선택하고 [실행].
 *    → TEST_EMAIL 주소로 "오늘 신규 공고" 메일이 1통 발송된다.
 *
 * [중요 - 개인정보]
 * 구독자 이메일은 이 스프레드시트에만 저장한다. GitHub 저장소는 공개이며
 * git 이력은 사실상 삭제가 불가능하므로, 구독자 정보를 저장소에 올리면
 * 수신거부 시 파기 의무를 이행할 수 없다.
 */

var SHEET_ID = "1kFZNfsSyUNIianP4Txb8of_xux_Jr0te3QoaQ2XpKl0"; // ← 요청 접수 내역 스프레드시트 ID
var TAB_NAME = "웹요청";        // 팝업 요청이 쌓일 탭 이름
var SUB_TAB_NAME = "구독자";    // 채용 알림 구독자가 쌓일 탭 이름
var ADMIN_EMAIL = "samdasu266@gmail.com"; // 새 요청 알림을 받을 운영자 메일 (빈 문자열이면 알림 안 보냄)

var SITE_URL = "https://samdasu266-hash.github.io/";
var HISTORY_URL = "https://raw.githubusercontent.com/samdasu266-hash/samdasu266-hash.github.io/main/history.json";
var WEBAPP_URL = "";  // ← 배포 후 웹앱 URL 을 여기에 넣으면 메일에 수신거부 링크가 붙는다

var TEST_EMAIL = "jh941223@naver.com"; // sendTestDigest 가 사용할 테스트 수신 주소

// 기관 ID → 표시 이름 (app.jsx 의 institutions 와 동일하게 유지)
var INST_NAMES = {
  nhis: "국민건강보험공단", hira: "건강보험심사평가원", nps: "국민연금공단",
  comwel: "근로복지공단", neca: "한국보건의료연구원", kuksiwon: "한국보건의료인국가시험원",
  koiha: "의료기관평가인증원", redcross: "대한적십자사", mohw: "보건복지부 및 소속기관",
  khepi: "한국건강증진개발원", nmc: "국립중앙의료원", kac: "한국공항공사(보건관리자)"
};

/* ────────────────────────────── 웹앱 수신 ────────────────────────────── */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // 채용 알림 구독 신청은 별도 탭으로 분리 처리
    if (data.type === "채용알림 신청") {
      return handleSubscribe_(data);
    }

    var ss = SpreadsheetApp.openById(SHEET_ID);
    var sheet = ss.getSheetByName(TAB_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(TAB_NAME);
      sheet.appendRow(["접수일시", "요청유형", "기관명", "URL", "내용", "이메일", "처리상태"]);
    }
    sheet.appendRow([
      new Date(),
      data.type || "",
      data.org || "",
      data.url || "",
      data.content || "",
      data.email || "",
      "미처리"
    ]);

    // 제출자에게 접수 확인 메일 자동 발송 (이메일을 입력한 경우에만)
    if (data.email && /.+@.+\..+/.test(data.email)) {
      MailApp.sendEmail({
        to: data.email,
        subject: "[보건공기업 알리미] 요청이 정상 접수되었습니다",
        body:
          "안녕하세요,\n\n" +
          "보건공기업 알리미에 남겨주신 요청(\"" + (data.type || "건의") + "\")이 정상적으로 접수되었습니다.\n" +
          "검토 후 사이트에 반영하겠습니다. 소중한 의견 감사합니다.\n\n" +
          (data.org ? ("· 기관명: " + data.org + "\n") : "") +
          (data.content ? ("· 내용: " + data.content + "\n") : "") +
          "\n— 보건공기업 알리미 운영자 드림\n" + SITE_URL
      });
    }

    // 운영자에게 새 요청 알림
    if (ADMIN_EMAIL) {
      MailApp.sendEmail(ADMIN_EMAIL,
        "[알리미] 새 요청: " + (data.type || "") + " / " + (data.org || ""),
        "유형: " + (data.type || "") + "\n기관: " + (data.org || "") + "\nURL: " + (data.url || "") +
        "\n내용: " + (data.content || "") + "\n회신메일: " + (data.email || "(없음)"));
    }

    return json_({ ok: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  // 메일 하단 수신거부 링크: .../exec?unsub=토큰
  var token = e && e.parameter ? e.parameter.unsub : null;
  if (token) {
    var ok = unsubscribe_(token);
    return HtmlService.createHtmlOutput(
      '<div style="font-family:sans-serif;max-width:520px;margin:80px auto;text-align:center;line-height:1.7">' +
      (ok
        ? '<h2 style="color:#0f172a">수신거부가 완료되었습니다</h2>' +
          '<p style="color:#64748b">더 이상 채용 알림 메일을 보내지 않습니다.<br>등록하신 이메일은 곧 파기됩니다.</p>'
        : '<h2 style="color:#0f172a">이미 처리되었거나 잘못된 링크입니다</h2>' +
          '<p style="color:#64748b">문의가 필요하시면 사이트 하단 문의하기를 이용해 주세요.</p>') +
      '<p style="margin-top:28px"><a href="' + SITE_URL + '" style="color:#2563eb">보건공기업 알리미로 돌아가기</a></p></div>'
    );
  }
  return ContentService.createTextOutput("보건공기업 알리미 요청 수신 엔드포인트");
}

/* ────────────────────────────── 구독 처리 ────────────────────────────── */

function subSheet_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sheet = ss.getSheetByName(SUB_TAB_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SUB_TAB_NAME);
    sheet.appendRow(["신청일시", "이메일", "관심기관", "관심고용형태", "토큰", "상태", "최근발송일"]);
  }
  return sheet;
}

function handleSubscribe_(data) {
  var email = (data.email || "").trim();
  if (!/.+@.+\..+/.test(email)) return json_({ ok: false, error: "invalid email" });

  var sheet = subSheet_();
  var rows = sheet.getDataRange().getValues();

  // 이미 구독 중이면 관심 조건만 갱신 (중복 행을 만들지 않는다)
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][1]).trim().toLowerCase() === email.toLowerCase()) {
      sheet.getRange(i + 1, 3).setValue(data.insts || "");
      sheet.getRange(i + 1, 4).setValue(data.jobTypes || "");
      sheet.getRange(i + 1, 6).setValue("구독중");
      sendWelcome_(email, String(rows[i][4]), data, true);
      return json_({ ok: true, updated: true });
    }
  }

  var token = Utilities.getUuid();
  sheet.appendRow([new Date(), email, data.insts || "", data.jobTypes || "", token, "구독중", ""]);
  sendWelcome_(email, token, data, false);

  if (ADMIN_EMAIL) {
    MailApp.sendEmail(ADMIN_EMAIL, "[알리미] 채용 알림 신규 구독",
      "이메일: " + email + "\n관심기관: " + (data.insts || "전체") + "\n관심고용형태: " + (data.jobTypes || "전체"));
  }
  return json_({ ok: true });
}

function sendWelcome_(email, token, data, isUpdate) {
  var instLabel = data.insts ? data.insts.split(",").map(function (id) {
    return INST_NAMES[id.trim()] || id.trim();
  }).join(", ") : "전체 기관";
  MailApp.sendEmail({
    to: email,
    subject: isUpdate
      ? "[보건공기업 알리미] 채용 알림 설정이 변경되었습니다"
      : "[보건공기업 알리미] 채용 알림 신청이 완료되었습니다",
    htmlBody:
      '<div style="font-family:sans-serif;line-height:1.7;color:#0f172a;max-width:560px">' +
      '<h2 style="margin:0 0 12px">채용 알림 ' + (isUpdate ? "설정이 변경" : "신청이 완료") + '되었습니다</h2>' +
      '<p style="color:#475569;margin:0 0 16px">아래 조건에 맞는 새 공고가 올라온 날 <strong>오전 8시</strong>에 한 통으로 모아 보내드립니다. 해당하는 공고가 없는 날은 메일을 보내지 않으니, 알림이 오지 않아도 정상입니다.</p>' +
      '<table style="border-collapse:collapse;font-size:14px;color:#334155">' +
      '<tr><td style="padding:4px 12px 4px 0;color:#94a3b8">관심 기관</td><td>' + escapeHtml_(instLabel) + '</td></tr>' +
      '<tr><td style="padding:4px 12px 4px 0;color:#94a3b8">관심 고용형태</td><td>' + escapeHtml_(data.jobTypes || "전체") + '</td></tr>' +
      '</table>' +
      '<p style="margin:20px 0 0"><a href="' + SITE_URL + '" style="color:#2563eb">보건공기업 알리미 바로가기</a></p>' +
      unsubFooter_(token) + '</div>'
  });
}

function unsubscribe_(token) {
  var sheet = subSheet_();
  var rows = sheet.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (String(rows[i][4]) === String(token)) {
      sheet.getRange(i + 1, 6).setValue("해지");
      return true;
    }
  }
  return false;
}

/* ──────────────────────────── 일일 알림 메일 ──────────────────────────── */

/**
 * 매일 오전 8시(KST) 실행.
 * history.json 의 firstSeen 이 오늘인 공고 = 오늘 새로 수집된 공고.
 * (스크래퍼가 매시간 firstSeen 을 기록하므로 별도 스냅샷 비교가 필요 없다)
 */
function sendDailyDigest() {
  var today = todayKst_();

  // 같은 날 중복 발송 방지
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty("lastDigestDate") === today) {
    Logger.log("이미 " + today + " 발송 완료 — 건너뜀");
    return;
  }

  var fresh = fetchNewJobs_(today);
  if (fresh.length === 0) {
    Logger.log("오늘 신규 공고 없음 — 발송하지 않음");
    props.setProperty("lastDigestDate", today);
    return;
  }

  var sheet = subSheet_();
  var rows = sheet.getDataRange().getValues();
  var sent = 0;

  for (var i = 1; i < rows.length; i++) {
    var email = String(rows[i][1]).trim();
    var insts = String(rows[i][2] || "").trim();
    var types = String(rows[i][3] || "").trim();
    var token = String(rows[i][4]);
    var state = String(rows[i][5]);
    if (state !== "구독중" || !/.+@.+\..+/.test(email)) continue;

    var mine = filterForSubscriber_(fresh, insts, types);
    if (mine.length === 0) continue;

    MailApp.sendEmail({
      to: email,
      subject: "[보건공기업 알리미] 오늘 새로 올라온 공고 " + mine.length + "건",
      htmlBody: digestHtml_(mine, token, today)
    });
    sheet.getRange(i + 1, 7).setValue(today);
    sent++;
  }

  props.setProperty("lastDigestDate", today);
  Logger.log("신규 공고 " + fresh.length + "건 / 발송 " + sent + "통");
}

/** 매일 오전 8시 트리거 생성 (중복 생성 방지) */
function setupDailyTrigger() {
  var exists = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === "sendDailyDigest";
  });
  if (exists) { Logger.log("이미 트리거가 있습니다."); return; }
  ScriptApp.newTrigger("sendDailyDigest").timeBased().atHour(8).everyDays(1).create();
  Logger.log("매일 오전 8시 트리거를 생성했습니다.");
}

/** 테스트 발송: TEST_EMAIL 로 오늘(없으면 최근) 신규 공고 메일을 1통 보낸다 */
function sendTestDigest() {
  var today = todayKst_();
  var fresh = fetchNewJobs_(today);
  if (fresh.length === 0) {
    // 오늘 신규가 없으면 가장 최근 수집분으로 미리보기를 만든다
    fresh = fetchRecentJobs_(5);
  }
  MailApp.sendEmail({
    to: TEST_EMAIL,
    subject: "[테스트][보건공기업 알리미] 새로 올라온 공고 " + fresh.length + "건",
    htmlBody: digestHtml_(fresh, "TEST-TOKEN", today)
  });
  Logger.log(TEST_EMAIL + " 로 테스트 메일 " + fresh.length + "건 발송");
}

/* ──────────────────────────────── 유틸 ──────────────────────────────── */

function fetchHistory_() {
  var res = UrlFetchApp.fetch(HISTORY_URL, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error("history.json 조회 실패: " + res.getResponseCode());
  return JSON.parse(res.getContentText()).jobs || [];
}

function fetchNewJobs_(today) {
  return fetchHistory_().filter(function (j) {
    return j.firstSeen === today && j.status !== "마감";
  });
}

function fetchRecentJobs_(n) {
  var all = fetchHistory_().filter(function (j) { return j.status !== "마감"; });
  all.sort(function (a, b) { return String(b.firstSeen).localeCompare(String(a.firstSeen)); });
  return all.slice(0, n);
}

function filterForSubscriber_(jobs, insts, types) {
  var instList = insts ? insts.split(",").map(function (s) { return s.trim(); }).filter(String) : [];
  var typeList = types ? types.split(",").map(function (s) { return s.trim(); }).filter(String) : [];
  return jobs.filter(function (j) {
    if (instList.length && instList.indexOf(j.instId) === -1) return false;
    if (typeList.length && typeList.indexOf(j.jobType) === -1) return false;
    return true;
  });
}

function todayKst_() {
  return Utilities.formatDate(new Date(), "Asia/Seoul", "yyyy-MM-dd");
}

function escapeHtml_(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function unsubFooter_(token) {
  var link = WEBAPP_URL ? (WEBAPP_URL + "?unsub=" + encodeURIComponent(token)) : "";
  return '<hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0 14px">' +
    '<p style="font-size:11.5px;color:#94a3b8;line-height:1.6;margin:0">' +
    '이 메일은 보건공기업 알리미 채용 알림을 신청하신 분께 발송됩니다.<br>' +
    (link
      ? '더 이상 받고 싶지 않으시면 <a href="' + link + '" style="color:#64748b">수신거부</a>를 눌러주세요.'
      : '수신거부를 원하시면 이 메일에 회신해 주세요.') +
    '</p>';
}

/** 공고 목록 → 메일 본문 HTML (네이버·다음 메일 호환을 위해 인라인 스타일만 사용) */
function digestHtml_(jobs, token, today) {
  var cards = jobs.map(function (j) {
    var inst = INST_NAMES[j.instId] || j.instId;
    var meta = [j.jobType, j.region].filter(String).join(" · ");
    var due = j.endDate && j.endDate !== "상세참조"
      ? '<span style="color:#dc2626;font-weight:bold">~' + escapeHtml_(j.endDate) + '</span>'
      : '<span style="color:#94a3b8">마감일은 공고에서 확인</span>';
    return '' +
      '<table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:12px;margin:0 0 12px">' +
      '<tr><td style="padding:16px 18px">' +
      '<div style="font-size:11.5px;font-weight:bold;color:#2563eb;margin-bottom:6px">' + escapeHtml_(inst) + '</div>' +
      '<div style="font-size:15px;font-weight:bold;color:#0f172a;line-height:1.45;margin-bottom:8px">' +
      escapeHtml_(j.title) + '</div>' +
      '<div style="font-size:12.5px;color:#64748b;margin-bottom:12px">' +
      (meta ? escapeHtml_(meta) + ' &nbsp;|&nbsp; ' : '') + due + '</div>' +
      (j.link
        ? '<a href="' + escapeHtml_(j.link) + '" style="display:inline-block;background:#2563eb;color:#fff;' +
          'text-decoration:none;font-size:12.5px;font-weight:bold;padding:8px 16px;border-radius:8px">공고 보러가기</a>'
        : '') +
      '</td></tr></table>';
  }).join("");

  return '' +
    '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Malgun Gothic\',sans-serif;' +
    'background:#f8fafc;padding:24px 12px">' +
    '<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:16px;padding:28px 24px">' +
    '<div style="font-size:12px;color:#94a3b8;font-weight:bold;margin-bottom:4px">' + escapeHtml_(today) + '</div>' +
    '<h1 style="font-size:20px;color:#0f172a;margin:0 0 6px">새로 올라온 공고 ' + jobs.length + '건</h1>' +
    '<p style="font-size:13px;color:#64748b;margin:0 0 22px;line-height:1.6">' +
    '관심 기관으로 등록하신 조건에 맞는 공고입니다. 지원 자격과 마감일은 반드시 공고 원문을 확인해 주세요.</p>' +
    cards +
    '<p style="margin:22px 0 0;text-align:center">' +
    '<a href="' + SITE_URL + '" style="color:#2563eb;font-size:13px;font-weight:bold">전체 공고 보러가기 →</a></p>' +
    unsubFooter_(token) +
    '</div></div>';
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
