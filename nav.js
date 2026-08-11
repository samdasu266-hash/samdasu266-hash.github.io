/* 상단 내비게이션 보조 스크립트 (정적 페이지 공용)
 *
 * 모바일에서는 항목 10개가 한 줄에 안 들어가 가로 스크롤이 된다.
 *  1) 현재 페이지 항목이 화면 밖에 있으면 보이도록 스크롤한다.
 *     (없으면 "내가 어디 있는지" 안 보여서 위치를 잃는다)
 *  2) 양 끝에 닿으면 그쪽 페이드를 감춘다.
 *
 * 데스크톱은 줄바꿈이라 스크롤이 없어 아무 일도 하지 않는다.
 */
(function () {
  function init() {
    var wrap = document.querySelector(".site-nav-wrap");
    var nav = document.querySelector(".site-nav");
    if (!wrap || !nav) return;

    function syncFade() {
      var max = nav.scrollWidth - nav.clientWidth;
      wrap.classList.toggle("is-start", nav.scrollLeft <= 1);
      wrap.classList.toggle("is-end", max - nav.scrollLeft <= 1);
    }

    var active = nav.querySelector(".site-nav-link.is-active");
    if (active && nav.scrollWidth > nav.clientWidth) {
      // scrollIntoView 는 페이지 전체를 움직일 수 있어 직접 계산한다
      var target = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
      nav.scrollLeft = Math.max(0, target);
    }

    syncFade();
    nav.addEventListener("scroll", syncFade, { passive: true });
    window.addEventListener("resize", syncFade);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
