(function () {
  if (window.__grammarAssistant) {
    window.__grammarAssistant.toggle();
    return;
  }

  var API = window.GA_API_BASE || "http://127.0.0.1:8000";
  try {
    API = localStorage.getItem("ga_api_base") || API;
  } catch (error) {
    /* localStorage can be unavailable on some pages */
  }
  API = String(API).replace(/\/$/, "");

  var MAX_CHARS = 60000;
  var empty = { suggestion: 1, warning: 2, error: 3 };

  function style(element, props) {
    for (var key in props) {
      if (Object.prototype.hasOwnProperty.call(props, key)) element.style[key] = props[key];
    }
    return element;
  }

  function button(label, props) {
    var node = document.createElement("button");
    node.type = "button";
    node.textContent = label;
    style(
      node,
      Object.assign(
        {
          border: "1px solid #d8dce3",
          background: "#ffffff",
          color: "#1a1d23",
          borderRadius: "7px",
          padding: "5px 9px",
          font: "600 12px/1.2 system-ui, sans-serif",
          cursor: "pointer",
        },
        props || {}
      )
    );
    return node;
  }

  function utf16Map(text) {
    var points = Array.from(text);
    var map = new Uint32Array(points.length + 1);
    var offset = 0;
    for (var i = 0; i < points.length; i += 1) {
      map[i] = offset;
      offset += points[i].length;
    }
    map[points.length] = offset;
    return map;
  }

  var host = document.createElement("div");
  style(host, {
    position: "fixed",
    right: "18px",
    bottom: "18px",
    zIndex: "2147483647",
    width: "min(380px, calc(100vw - 36px))",
    fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
  });
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var panel = style(document.createElement("div"), {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    background: "#ffffff",
    color: "#1a1d23",
    border: "1px solid #dfe2e8",
    borderRadius: "14px",
    boxShadow: "0 18px 50px rgba(15, 20, 30, 0.25)",
    padding: "12px",
    maxHeight: "min(70vh, 560px)",
  });

  var header = style(document.createElement("div"), {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
  });
  var title = style(document.createElement("strong"), {
    font: "600 13px/1.3 system-ui, sans-serif",
  });
  title.textContent = "Grammar Assistant";
  var close = button("Close", { padding: "3px 8px" });
  header.append(title, close);

  var editor = document.createElement("textarea");
  editor.placeholder = "Paste or select text, then check.";
  editor.spellcheck = false;
  style(editor, {
    width: "100%",
    boxSizing: "border-box",
    minHeight: "110px",
    maxHeight: "220px",
    resize: "vertical",
    border: "1px solid #dfe2e8",
    borderRadius: "9px",
    padding: "8px 10px",
    font: "13px/1.55 system-ui, sans-serif",
    color: "#1a1d23",
    background: "#fbfcfd",
    outline: "none",
  });

  var toolbar = style(document.createElement("div"), {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap",
  });
  var check = button("Check", {
    border: "1px solid #1f6f5c",
    background: "#1f6f5c",
    color: "#ffffff",
  });
  var fixAll = button("Fix all");
  var pdf = button("PDF");
  var openApp = button("Open app");
  var status = style(document.createElement("span"), {
    marginLeft: "auto",
    font: "400 11px/1.3 system-ui, sans-serif",
    color: "#6b7280",
  });
  status.textContent = "Ready";
  toolbar.append(check, fixAll, pdf, openApp, status);

  var results = style(document.createElement("div"), {
    display: "flex",
    flexDirection: "column",
    gap: "7px",
    overflowY: "auto",
    minHeight: "28px",
  });
  var hint = style(document.createElement("p"), {
    margin: "0",
    font: "400 12px/1.45 system-ui, sans-serif",
    color: "#6b7280",
  });
  hint.textContent = "Select text on the page before opening, or paste it above.";
  results.append(hint);

  panel.append(header, editor, toolbar, results);
  root.append(panel);

  var selected = "";
  try {
    selected = String(window.getSelection ? window.getSelection() : "").trim();
  } catch (error) {
    selected = "";
  }
  if (selected) editor.value = selected.slice(0, MAX_CHARS);

  function setStatus(message, bad) {
    status.textContent = message;
    status.style.color = bad ? "#dc2626" : message === "Checking..." ? "#1f6f5c" : "#6b7280";
  }

  function renderIssues(text, issues) {
    results.replaceChildren();
    if (!issues.length) {
      var clean = style(document.createElement("p"), {
        margin: "0",
        font: "400 12px/1.45 system-ui, sans-serif",
        color: "#196149",
      });
      clean.textContent = "No issues found.";
      results.append(clean);
      return;
    }
    var map = utf16Map(text);
    issues.forEach(function (issue) {
      var card = style(document.createElement("div"), {
        border: "1px solid #e5e8ee",
        borderLeft: "3px solid #b45309",
        borderRadius: "8px",
        padding: "7px 9px",
        background: "#ffffff",
      });
      var meta = style(document.createElement("div"), {
        display: "flex",
        justifyContent: "space-between",
        gap: "8px",
        font: "700 10px/1.4 system-ui, sans-serif",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: "#6b7280",
      });
      var kind = document.createElement("span");
      kind.textContent = issue.type;
      var level = document.createElement("span");
      level.textContent = issue.severity;
      meta.append(kind, level);

      var message = style(document.createElement("div"), {
        marginTop: "3px",
        font: "400 12px/1.45 system-ui, sans-serif",
      });
      message.textContent = issue.message;

      var quote = style(document.createElement("div"), {
        marginTop: "5px",
        padding: "4px 6px",
        borderRadius: "5px",
        background: "#f6f7f9",
        font: "11px/1.4 ui-monospace, Consolas, monospace",
        color: "#3d424b",
        overflowWrap: "anywhere",
      });
      quote.textContent = issue.text || "(insertion point)";

      var actions = style(document.createElement("div"), {
        display: "flex",
        gap: "5px",
        flexWrap: "wrap",
        marginTop: "6px",
      });
      issue.suggestions.slice(0, 3).forEach(function (suggestion) {
        var apply = button(suggestion === "" ? "Delete" : suggestion, {
          border: "1px solid #b7dccd",
          background: "#eef7f3",
          color: "#17594a",
          padding: "3px 7px",
        });
        apply.addEventListener("click", function () {
          if (editor.value !== text) {
            analyzeText();
            return;
          }
          var current = editor.value;
          var start = map[Math.min(issue.start, map.length - 1)] || 0;
          var end = map[Math.min(issue.end, map.length - 1)] || start;
          editor.value = current.slice(0, start) + suggestion + current.slice(end);
          analyzeText();
        });
        actions.append(apply);
      });

      card.append(meta, message, quote, actions);
      results.append(card);
    });
  }

  function analyzeText() {
    var text = editor.value;
    if (!text.trim()) {
      setStatus("Add some text", true);
      return;
    }
    if (text.length > MAX_CHARS) {
      setStatus("Too long", true);
      return;
    }
    setStatus("Checking...");
    check.disabled = true;
    fetch(API + "/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, include_stats: false, use_remote: true }),
    })
      .then(function (response) {
        if (!response.ok) throw new Error("status " + response.status);
        return response.json();
      })
      .then(function (body) {
        var issues = body.issues.filter(function (issue) {
          return empty[issue.severity] >= empty.warning;
        });
        renderIssues(text, issues);
        setStatus(issues.length ? issues.length + " issues" : "No issues");
      })
      .catch(function (error) {
        results.replaceChildren();
        var failed = style(document.createElement("p"), {
          margin: "0",
          font: "400 12px/1.45 system-ui, sans-serif",
          color: "#a62a20",
        });
        failed.textContent =
          "Could not reach the assistant at " + API + ". Start the server and allow this site in GA_CORS_ORIGINS, or open the app instead.";
        var row = style(document.createElement("div"), { display: "flex", gap: "6px", flexWrap: "wrap" });
        var open = button("Open app", { border: "1px solid #1f6f5c", color: "#17594a" });
        open.addEventListener("click", openFullApp);
        row.append(open);
        results.append(failed, row);
        setStatus("Offline", true);
      })
      .finally(function () {
        check.disabled = false;
      });
  }

  function openFullApp() {
    var url = API + "/?text=" + encodeURIComponent(editor.value.slice(0, MAX_CHARS));
    window.open(url, "_blank", "noopener");
  }

  function downloadPdf() {
    var text = editor.value;
    if (!text.trim()) {
      setStatus("Add some text", true);
      return;
    }
    setStatus("Preparing PDF...");
    fetch(API + "/api/export/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    })
      .then(function (response) {
        if (!response.ok) throw new Error("status " + response.status);
        return response.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement("a");
        link.href = url;
        link.download = "grammar-assistant.pdf";
        document.documentElement.append(link);
        link.click();
        link.remove();
        setTimeout(function () {
          URL.revokeObjectURL(url);
        }, 2000);
        setStatus("PDF saved");
      })
      .catch(function () {
        setStatus("PDF failed", true);
      });
  }

  function fixAllText() {
    var text = editor.value;
    if (!text.trim()) {
      setStatus("Add some text", true);
      return;
    }
    setStatus("Fixing...");
    fetch(API + "/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text, include_stats: false, use_remote: true }),
    })
      .then(function (response) {
        if (!response.ok) throw new Error("status " + response.status);
        return response.json();
      })
      .then(function (body) {
        if (editor.value !== text) {
          analyzeText();
          return;
        }
        var map = utf16Map(text);
        var allowed = { spelling: 1, grammar: 1, punctuation: 1 };
        var edits = [];
        for (var index = 0; index < body.issues.length; index += 1) {
          var issue = body.issues[index];
          if (!allowed[issue.type] || !issue.suggestions || !issue.suggestions.length) continue;
          if (empty[issue.severity] < empty.warning) continue;
          var start = map[Math.min(issue.start, map.length - 1)] || 0;
          var end = map[Math.min(issue.end, map.length - 1)] || start;
          var replacement = issue.suggestions[0];
          if (text.slice(start, end) === replacement) continue;
          edits.push({ start: start, end: end, replacement: replacement });
        }
        edits.sort(function (a, b) {
          return a.start - b.start || b.end - a.end;
        });
        var chosen = [];
        var lastEnd = 0;
        for (var i = 0; i < edits.length; i += 1) {
          if (edits[i].start < lastEnd) continue;
          chosen.push(edits[i]);
          lastEnd = Math.max(lastEnd, edits[i].end);
        }
        if (!chosen.length) {
          setStatus("No fixes found");
          return;
        }
        var corrected = text;
        for (var j = chosen.length - 1; j >= 0; j -= 1) {
          corrected =
            corrected.slice(0, chosen[j].start) + chosen[j].replacement + corrected.slice(chosen[j].end);
        }
        editor.value = corrected;
        setStatus("Fixed " + chosen.length);
        analyzeText();
      })
      .catch(function () {
        setStatus("Fix failed", true);
      });
  }

  check.addEventListener("click", analyzeText);
  fixAll.addEventListener("click", fixAllText);
  pdf.addEventListener("click", downloadPdf);
  openApp.addEventListener("click", openFullApp);
  close.addEventListener("click", function () {
    host.remove();
    window.__grammarAssistant = null;
  });
  editor.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      analyzeText();
    }
  });

  window.__grammarAssistant = {
    toggle: function () {
      host.style.display = host.style.display === "none" ? "block" : "none";
    },
  };

  document.documentElement.append(host);
  if (selected) analyzeText();
})();
