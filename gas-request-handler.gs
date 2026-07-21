/**
 * 보건공기업 알리미 - 기관 추가·건의 팝업 수신용 Google Apps Script
 *
 * [설치 방법]
 * 1) script.google.com 에서 기존 프로젝트(요청 폼 만든 프로젝트)를 열거나 새 프로젝트 생성
 * 2) 이 파일 내용을 Code.gs 에 붙여넣기
 * 3) 아래 SHEET_ID 를 "보건공기업 알리미 - 요청 접수 내역" 스프레드시트 ID로 설정
 *    (스프레드시트 URL 의 /d/ 와 /edit 사이 문자열)
 * 4) 상단 [배포] → [배포 관리] → 기존 웹앱 옆 연필(수정) → 버전: 새 버전 →
 *    실행 계정: 나, 액세스 권한: 모든 사용자 → [배포]  (URL 이 그대로 유지됨)
 *    ※ 처음 배포라면 [배포] → [새 배포] → 유형: 웹 앱 으로 동일하게 설정
 * 5) 최초 1회 권한 승인(메일 전송/시트 접근) 필요
 */

var SHEET_ID = "1kFZNfsSyUNIianP4Txb8of_xux_Jr0te3QoaQ2XpKl0"; // ← 요청 접수 내역 스프레드시트 ID
var TAB_NAME = "웹요청";       // 팝업 요청이 쌓일 탭 이름
var ADMIN_EMAIL = "samdasu266@gmail.com"; // 새 요청 알림을 받을 운영자 메일 (빈 문자열이면 알림 안 보냄)

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
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
          "\n— 보건공기업 알리미 운영자 드림\n" +
          "https://samdasu266-hash.github.io/"
      });
    }

    // 운영자에게 새 요청 알림
    if (ADMIN_EMAIL) {
      MailApp.sendEmail(ADMIN_EMAIL,
        "[알리미] 새 요청: " + (data.type || "") + " / " + (data.org || ""),
        "유형: " + (data.type || "") + "\n기관: " + (data.org || "") + "\nURL: " + (data.url || "") +
        "\n내용: " + (data.content || "") + "\n회신메일: " + (data.email || "(없음)"));
    }

    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet() {
  return ContentService.createTextOutput("보건공기업 알리미 요청 수신 엔드포인트");
}
