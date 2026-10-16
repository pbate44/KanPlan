
// Log entries are stored as plain text with markdown-style markers:
//   **bold**  *italic*  __underline__  ~~strike~~  `code`
//   [big]larger[/big]  [small]smaller[/small]  "- " bullet lines
// The text is HTML-escaped before any markers are turned into tags.

var LOG_INLINE_RULES = [
  [/\*\*\*(?=\S)(.*?\S)\*\*\*/g, "<strong><em>$1</em></strong>"],
  [/\*\*(?=\S)(.*?\S)\*\*/g,     "<strong>$1</strong>"],
  [/__(?=\S)(.*?\S)__/g,         "<u>$1</u>"],
  [/~~(?=\S)(.*?\S)~~/g,         "<s>$1</s>"],
  [/\*(?=\S)(.*?\S)\*/g,         "<em>$1</em>"],
];

var LOG_SIZE_TAG = /\[(big|small)\]((?:(?!\[\/?(?:big|small)\]).)*?)\[\/\1\]/g;

function escapeLogHtml(text) {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderLogInline(line) {
  var codes = [];
  line = line.replace(/`([^`]+)`/g, function (_, code) {
    codes.push(code);
    return "\u0000" + (codes.length - 1) + "\u0000";
  });

  LOG_INLINE_RULES.forEach(function (rule) {
    line = line.replace(rule[0], rule[1]);
  });

  // Replace innermost size tags first so nested sizes compound.
  for (var i = 0; i < 10; i++) {
    var next = line.replace(LOG_SIZE_TAG, '<span class="log-md__$1">$2</span>');
    if (next === line) break;
    line = next;
  }

  return line.replace(/\u0000(\d+)\u0000/g, function (_, n) {
    return "<code>" + codes[n] + "</code>";
  });
}

function renderLogMarkdown(text) {
  var lines = escapeLogHtml(String(text || "").replace(/\u0000/g, "")).split("\n");
  var out = [], para = [], items = [];

  function flushPara() {
    if (para.length) out.push('<div class="log-md__p">' + para.join("\n") + "</div>");
    para = [];
  }
  function flushList() {
    if (items.length) out.push('<ul class="log-md__list"><li>' + items.join("</li><li>") + "</li></ul>");
    items = [];
  }

  lines.forEach(function (line) {
    var bullet = /^\s*[-*] +(.*)$/.exec(line);
    if (bullet) {
      flushPara();
      items.push(renderLogInline(bullet[1]));
    } else {
      flushList();
      para.push(renderLogInline(line));
    }
  });
  flushPara();
  flushList();

  return '<div class="log-md">' + out.join("") + "</div>";
}

// Renders `raw` into an entry's text container and keeps the raw text for editing.
function renderLogEntryText($textDiv, raw) {
  $textDiv.data("raw", raw).html(renderLogMarkdown(raw));
}

function renderLogEntries() {
  $(".cardmodal__logentry-text").each(function () {
    var $textDiv = $(this);
    var $pre = $textDiv.children("pre");
    if ($pre.length) renderLogEntryText($textDiv, $pre.text());
  });
}


// ── Formatting toolbar ────────────────────────────────────────────────────

var LOG_TEXTAREAS = "#logEntryTextarea, .log-entry-edit-textarea";
var _lastLogTextarea = null;

// Replaces [start, end) with `text` in a way that keeps native undo working.
function replaceLogRange(ta, start, end, text) {
  ta.focus();
  ta.setSelectionRange(start, end);
  if (!document.execCommand("insertText", false, text)) {
    ta.setRangeText(text, start, end, "end");
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

// For single-character markers ("*"), a run of 2 is bold rather than italic,
// so the marker only counts as present when the run length is odd.
function hasMarkerRun(run, marker) {
  if (run.length < marker.length) return false;
  return marker.length === 1 ? run.length % 2 === 1 : true;
}

function markerRunBefore(value, pos, ch) {
  var n = 0;
  while (pos - n - 1 >= 0 && value[pos - n - 1] === ch) n++;
  return value.slice(pos - n, pos);
}

function markerRunAfter(value, pos, ch) {
  var n = 0;
  while (pos + n < value.length && value[pos + n] === ch) n++;
  return value.slice(pos, pos + n);
}

function isWrappedOutside(value, start, end, open, close) {
  if (open.length && open[0] === close[0] && /^[*_~`]+$/.test(open)) {
    return hasMarkerRun(markerRunBefore(value, start, open[0]), open) &&
           hasMarkerRun(markerRunAfter(value, end, open[0]), open);
  }
  return value.slice(start - open.length, start) === open &&
         value.slice(end, end + close.length) === close;
}

function isWrappedInside(sel, open, close) {
  if (sel.length < open.length + close.length) return false;
  if (open[0] === close[0] && /^[*_~`]+$/.test(open)) {
    return hasMarkerRun(markerRunAfter(sel, 0, open[0]), open) &&
           hasMarkerRun(markerRunBefore(sel, sel.length, open[0]), open);
  }
  return sel.indexOf(open) === 0 && sel.slice(-close.length) === close;
}

// Wraps each line of the selection separately so bullets and line breaks
// stay outside the markers.
function wrapLines(sel, open, close) {
  return sel.split("\n").map(function (line) {
    var m = /^(\s*(?:[-*] +)?)(.*?)(\s*)$/.exec(line);
    return m[2] ? m[1] + open + m[2] + close + m[3] : line;
  }).join("\n");
}

function unwrapSelection(ta, open, close) {
  var v = ta.value, s = ta.selectionStart, e = ta.selectionEnd;
  var sel = v.slice(s, e);
  if (isWrappedOutside(v, s, e, open, close)) {
    replaceLogRange(ta, s - open.length, e + close.length, sel);
    ta.setSelectionRange(s - open.length, e - open.length);
    return true;
  }
  if (isWrappedInside(sel, open, close)) {
    var inner = sel.slice(open.length, sel.length - close.length);
    replaceLogRange(ta, s, e, inner);
    ta.setSelectionRange(s, s + inner.length);
    return true;
  }
  return false;
}

function wrapSelection(ta, open, close) {
  var v = ta.value, s = ta.selectionStart, e = ta.selectionEnd;
  var sel = v.slice(s, e);
  if (!sel) {
    replaceLogRange(ta, s, e, open + close);
    ta.setSelectionRange(s + open.length, s + open.length);
    return;
  }
  if (sel.indexOf("\n") === -1) {
    replaceLogRange(ta, s, e, open + sel + close);
    ta.setSelectionRange(s + open.length, e + open.length);
    return;
  }
  var wrapped = wrapLines(sel, open, close);
  replaceLogRange(ta, s, e, wrapped);
  ta.setSelectionRange(s, s + wrapped.length);
}

function toggleWrap(ta, open, close) {
  if (!unwrapSelection(ta, open, close)) wrapSelection(ta, open, close);
}

// A+ first removes a [small] wrapper before adding [big], and A- the reverse.
function changeSize(ta, grow) {
  var add    = grow ? "big" : "small";
  var remove = grow ? "small" : "big";
  if (!unwrapSelection(ta, "[" + remove + "]", "[/" + remove + "]")) {
    wrapSelection(ta, "[" + add + "]", "[/" + add + "]");
  }
}

function toggleBullets(ta) {
  var v = ta.value;
  var start = v.lastIndexOf("\n", ta.selectionStart - 1) + 1;
  var end = v.indexOf("\n", ta.selectionEnd);
  if (end === -1) end = v.length;

  var lines = v.slice(start, end).split("\n");
  var allBulleted = lines.every(function (l) { return !l.trim() || /^\s*- /.test(l); });
  var next = lines.map(function (l) {
    if (allBulleted) return l.replace(/^(\s*)- /, "$1");
    return !l.trim() || /^\s*- /.test(l) ? l : "- " + l;
  }).join("\n");

  replaceLogRange(ta, start, end, next);
  ta.setSelectionRange(start, start + next.length);
}

var LOG_FORMATS = {
  bold:      function (ta) { toggleWrap(ta, "**", "**"); },
  italic:    function (ta) { toggleWrap(ta, "*", "*"); },
  underline: function (ta) { toggleWrap(ta, "__", "__"); },
  strike:    function (ta) { toggleWrap(ta, "~~", "~~"); },
  code:      function (ta) { toggleWrap(ta, "`", "`"); },
  bigger:    function (ta) { changeSize(ta, true); },
  smaller:   function (ta) { changeSize(ta, false); },
  bullets:   toggleBullets,
};

function activeLogTextarea() {
  if (_lastLogTextarea && document.body.contains(_lastLogTextarea)) return _lastLogTextarea;
  return document.getElementById("logEntryTextarea");
}

$(document).on("focusin", LOG_TEXTAREAS, function () {
  _lastLogTextarea = this;
});

// mousedown is cancelled so the textarea keeps focus and its selection.
$(document).on("mousedown", ".log-format-btn", function (e) {
  e.preventDefault();
});

$(document).on("click", ".log-format-btn", function () {
  var ta = activeLogTextarea();
  var format = LOG_FORMATS[$(this).data("format")];
  if (ta && format) format(ta);
});

$(document).on("keydown", LOG_TEXTAREAS, function (e) {
  if (!(e.metaKey || e.ctrlKey) || e.altKey) return;
  var key = e.key.toLowerCase();
  var format = null;

  if (!e.shiftKey && key === "b") format = "bold";
  else if (!e.shiftKey && key === "i") format = "italic";
  else if (!e.shiftKey && key === "u") format = "underline";
  else if (!e.shiftKey && key === "e") format = "code";
  else if (e.shiftKey && key === "x") format = "strike";
  else if (e.shiftKey && (key === ">" || key === ".")) format = "bigger";
  else if (e.shiftKey && (key === "<" || key === ",")) format = "smaller";

  if (format) {
    e.preventDefault();
    LOG_FORMATS[format](this);
  }
});
