// Simple duration picker initializer
// Attaches to inputs with data-duration-picker="true"
(function () {
  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function toSeconds(h, m, s) {
    return (h | 0) * 3600 + (m | 0) * 60 + (s | 0);
  }

  function fromSeconds(total) {
    total = Math.max(0, total | 0);
    var h = Math.floor(total / 3600);
    var rem = total % 3600;
    var m = Math.floor(rem / 60);
    var s = rem % 60;
    return { h: h, m: m, s: s };
  }

  function fmt(num) {
    return (num < 10 ? "0" : "") + num;
  }

  function fmt2(num) {
    // Hours zero-padded to at least 2 (keeps 3+ digits intact)
    if (num < 10) return "0" + num;
    return String(num);
  }

  function format(total, includeSeconds) {
    var p = fromSeconds(total);
    if (includeSeconds) {
      return fmt2(p.h) + ":" + fmt(p.m) + ":" + fmt(p.s);
    }
    return fmt2(p.h) + ":" + fmt(p.m);
  }

  function parseDisplay(val, includeSeconds) {
    if (!val) return null;
    var parts = val.split(":");
    if (!includeSeconds) {
      if (parts.length !== 2) return null;
      var h = parseInt(parts[0], 10);
      var m = parseInt(parts[1], 10);
      if (Number.isNaN(h) || Number.isNaN(m)) return null;
      if (m < 0 || m > 59) return null;
      return toSeconds(h, m, 0);
    }
    if (parts.length !== 3) return null;
    var h3 = parseInt(parts[0], 10);
    var m3 = parseInt(parts[1], 10);
    var s3 = parseInt(parts[2], 10);
    if (Number.isNaN(h3) || Number.isNaN(m3) || Number.isNaN(s3)) return null;
    if (m3 < 0 || m3 > 59 || s3 < 0 || s3 > 59) return null;
    return toSeconds(h3, m3, s3);
  }

  function sync(el) {
    var includeSeconds = (el.getAttribute("data-include-seconds") || "false") === "true";
    var min = parseInt(el.getAttribute("data-min") || "0", 10);
    var max = parseInt(el.getAttribute("data-max") || "359999", 10);
    var targetId = el.getAttribute("data-target-id");
    var target = targetId && document.getElementById(targetId);
    if (!target) return;

    var st = ensureState(el);
    var parsed = parseDisplay(el.value, includeSeconds);
    if (parsed == null) {
      // fallback to current target seconds
      var seconds = parseInt(target.value || "0", 10) || 0;
      el.value = format(seconds, includeSeconds);
      // Restore segment selection
      selectSegment(el, st.selectedSeg, includeSeconds);
      return;
    }
    var clamped = clamp(parsed, min, max);
    target.value = String(clamped);
    // reflect clamped back to display
    el.value = format(clamped, includeSeconds);

    // bubble a change for frameworks listening
    var evt = new Event("change", { bubbles: true });
    target.dispatchEvent(evt);
    // Keep selection on current segment
    selectSegment(el, st.selectedSeg, includeSeconds);
  }

  function ensureState(el) {
    if (!el._durationPickerState) {
      el._durationPickerState = { selectedSeg: 0 };
    }
    return el._durationPickerState;
  }

  function getCursorSegment(el, includeSeconds) {
    // Determine which segment (0=h,1=m,2=s) the caret is in by counting colons
    var pos = el.selectionStart || 0;
    var before = (el.value || "").slice(0, pos);
    var colons = (before.match(/:/g) || []).length;
    if (!includeSeconds) return Math.min(colons, 1);
    return Math.min(colons, 2);
  }

  function segmentRangesFromValue(val) {
    var parts = (val || "").split(":");
    var ranges = [];
    var idx = 0;
    for (var i = 0; i < parts.length; i++) {
      var start = idx;
      var end = start + parts[i].length;
      ranges.push([start, end]);
      idx = end + 1; // skip colon
    }
    return ranges;
  }

  function selectSegment(el, seg, includeSeconds) {
    // Highlight the current segment to keep arrows affecting it persistently
    try {
      var ranges = segmentRangesFromValue(el.value);
      if (!includeSeconds && ranges.length > 2) {
        ranges = ranges.slice(0, 2);
      }
      var r = ranges[Math.max(0, Math.min(seg, ranges.length - 1))];
      if (r) {
        el.setSelectionRange(r[0], r[1]);
      }
    } catch (_) {
      // ignore selection errors (e.g., element not focused)
    }
  }

  function adjustBy(el, delta) {
    var includeSeconds = (el.getAttribute("data-include-seconds") || "false") === "true";
    var min = parseInt(el.getAttribute("data-min") || "0", 10);
    var max = parseInt(el.getAttribute("data-max") || "359999", 10);
    var targetId = el.getAttribute("data-target-id");
    var target = targetId && document.getElementById(targetId);
    if (!target) return;
  var st = ensureState(el);
  var parsed = parseDisplay(el.value, includeSeconds);
    if (parsed == null) parsed = parseInt(target.value || "0", 10) || 0;
  var seg = st.selectedSeg;
    var p = fromSeconds(parsed);
    if (seg === 0) p.h = clamp(p.h + delta, 0, 999999999);
    else if (seg === 1) p.m = clamp(p.m + delta, 0, 59);
    else p.s = clamp(p.s + delta, 0, 59);
    var next = toSeconds(p.h, p.m, includeSeconds ? p.s : 0);
    next = clamp(next, min, max);
    target.value = String(next);
    el.value = format(next, includeSeconds);
    var evt = new Event("change", { bubbles: true });
    target.dispatchEvent(evt);
  // keep selection on same segment
  selectSegment(el, seg, includeSeconds);
  }

  function initOne(el) {
    if (el._durationPickerInit) return;
    el._durationPickerInit = true;
    var includeSeconds = (el.getAttribute("data-include-seconds") || "false") === "true";
    var targetId = el.getAttribute("data-target-id");
    var target = targetId && document.getElementById(targetId);
    if (!target) return;

  // initialize from data-initial or hidden target
    var initial = parseInt(el.getAttribute("data-initial") || target.value || "0", 10) || 0;
    el.value = format(initial, includeSeconds);
    target.value = String(initial);
  var st = ensureState(el);
  selectSegment(el, st.selectedSeg, includeSeconds);

  el.addEventListener("blur", function () { sync(el); });
    el.addEventListener("change", function () { sync(el); });
    el.addEventListener("input", function () {
      // light normalize on the fly: only allow digits and colons
      var v = el.value.replace(/[^0-9:]/g, "");
      var parts = v.split(":");
      if (parts.length > (includeSeconds ? 3 : 2)) {
        parts = parts.slice(0, includeSeconds ? 3 : 2);
      }
      el.value = parts.join(":");
    });

    // Track clicked segment and keep it selected
    el.addEventListener("click", function () {
      var seg = getCursorSegment(el, includeSeconds);
      var st = ensureState(el);
      st.selectedSeg = seg;
      // select full segment so arrows apply persistently
      selectSegment(el, seg, includeSeconds);
    });

    // Keyboard arrows
    el.addEventListener("keydown", function (e) {
      if (e.key === "ArrowUp") {
        e.preventDefault();
        adjustBy(el, 1);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        adjustBy(el, -1);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        // update selected segment based on caret move
        setTimeout(function () {
          var st = ensureState(el);
          st.selectedSeg = getCursorSegment(el, includeSeconds);
        }, 0);
      }
    });

    // Buttons
    var wrapper = el.closest('[data-duration-picker-wrapper]');
    if (wrapper) {
      var incBtn = wrapper.querySelector('[data-dp-action="inc"]');
      var decBtn = wrapper.querySelector('[data-dp-action="dec"]');
      if (incBtn) incBtn.addEventListener("click", function () { el.focus(); adjustBy(el, 1); });
      if (decBtn) decBtn.addEventListener("click", function () { el.focus(); adjustBy(el, -1); });
    }
  }

  function initAll() {
    document.querySelectorAll('input[data-duration-picker="true"]').forEach(initOne);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
  } else {
    initAll();
  }

  // Expose a tiny API for dynamic content
  window.TimeDurationPicker = {
    init: initAll,
    initOne: initOne,
    format: format,
    parse: parseDisplay,
  };
})();
