/* Shared dashboard scripts */

(function () {
  var bubble;

  function createBubble() {
    var el = document.createElement("div");
    el.className = "tooltip-bubble";
    document.body.appendChild(el);
    return el;
  }

  bubble = createBubble();

  function clear() {
    bubble.classList.remove("active");
    bubble.textContent = "";
  }

  function show(text, anchor) {
    if (!anchor || !text) {
      clear();
      return;
    }
    bubble.textContent = text;
    bubble.classList.add("active");

    var r = anchor.getBoundingClientRect();
    var br = bubble.getBoundingClientRect();
    var left = r.left + r.width / 2 - br.width / 2;

    var pad = 10;
    var maxLeft = window.innerWidth - br.width - pad;
    if (left < pad) left = pad;
    if (left > maxLeft) left = maxLeft;

    var above = r.top - br.height - 8 > 0;
    var top = above ? r.top - br.height - 8 : r.bottom + 8;

    bubble.style.left = left + "px";
    bubble.style.top = top + "px";
  }

  function raise(anchor) {
    if (!bubble.classList.contains("active")) return;
    var br = bubble.getBoundingClientRect();
    bubble.style.top = (br.top === "" ? 0 : parseInt(br.top, 10)) + 1 + "px";
  }

  document.addEventListener("mousemove", function (e) {
    var target = e.target;
    var text = target.getAttribute ? target.getAttribute("data-tooltip") : null;
    if (text && text.length) {
      show(text, target);
    } else {
      clear();
    }
  });

  document.addEventListener("mouseenter", function (e) {
    var target = e.target;
    var text = target.getAttribute ? target.getAttribute("data-tooltip") : null;
    if (text && text.length) {
      show(text, target);
    }
  }, true);

  document.addEventListener("mouseleave", function (e) {
    var target = e.target;
    if (target.getAttribute && target.getAttribute("data-tooltip")) {
      clear();
    }
  }, true);

  document.addEventListener("dragstart", clear);
  document.addEventListener("keydown", clear);

  /* Participate dialog */
  (function () {
    var backdrop = document.getElementById("participate-dialog");
    var btn = document.getElementById("participate-btn");
    if (!backdrop || !btn) return;
    var close = backdrop.querySelector(".dialog-close");
    var lastFocus = null;

    function open() {
      lastFocus = document.activeElement;
      backdrop.removeAttribute("hidden");
      setTimeout(function () { close.focus(); }, 0);
    }
    function closeDialog() {
      backdrop.setAttribute("hidden", "");
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    btn.addEventListener("click", open);
    if (close) close.addEventListener("click", closeDialog);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) closeDialog();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !backdrop.hasAttribute("hidden")) closeDialog();
    });
  })();
})();
