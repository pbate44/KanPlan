$(function () {
  var $panel = $("#board-ai-panel");
  if (!$panel.length) return;

  var boardId    = $panel.data("board-id");
  var baseUrl    = "/board/" + boardId + "/ai-chat/";
  var sessionId  = null;
  var webSearch  = false;
  var loaded     = false;

  var WELCOME = "Hello! I'm your board assistant. I can answer questions about this board, " +
                "and create, move or delete cards when you ask. How can I help?";

  var ACTION_ICONS = {
    card_created:     "bi-plus-square",
    card_moved:       "bi-arrow-right-square",
    delete_request:   "bi-trash",
    delete_done:      "bi-trash",
    delete_cancelled: "bi-x-circle",
  };

  function post(url, body) {
    return $.ajax({
      url: url,
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify(body || {}),
      headers: { "X-CSRFToken": getCsrfToken() },
    });
  }

  function scrollToBottom() {
    var el = document.getElementById("board-ai-body");
    if (el) el.scrollTop = el.scrollHeight;
  }

  function setNewChatEnabled(enabled) {
    $("#board-ai-new").prop("disabled", !enabled);
  }

  function setWebSearch(enabled) {
    webSearch = enabled;
    $("#board-ai-web-search")
      .attr("aria-pressed", enabled ? "true" : "false")
      .toggleClass("board-ai-icon-btn--active", enabled);
  }

  // ── Messages ────────────────────────────────────────────────────────────────

  function clearMessages() {
    $("#board-ai-messages").empty();
  }

  function appendSystem(text) {
    $("#board-ai-messages").append($('<div class="system-message"><p></p></div>').find("p").text(text).end());
  }

  function appendMessage(msg) {
    var $list = $("#board-ai-messages");
    if (msg.role === "system") {
      appendSystem(msg.content);
    } else if (msg.role === "user") {
      $list.append($('<div class="user-message"></div>').text(msg.content));
    } else if (msg.role === "assistant") {
      $list.append('<div class="assistant-message">' + renderMarkdown(msg.content) + "</div>");
    } else if (msg.role === "action") {
      $list.append(renderAction(msg));
    }
  }

  function renderAction(msg) {
    var data = msg.data || {};
    var $el = $('<div class="board-ai-action"></div>')
      .attr("data-message-id", msg.id)
      .addClass("board-ai-action--" + (data.type || "other"))
      .append($('<i class="bi" aria-hidden="true"></i>').addClass(ACTION_ICONS[data.type] || "bi-lightning"))
      .append($('<span class="board-ai-action__text"></span>').text(msg.content));

    if (data.type === "delete_request") {
      var $footer = $('<div class="board-ai-action__footer"></div>');
      if (data.status === "pending") {
        $footer.append(
          $('<button type="button" class="board-ai-action__btn board-ai-action__btn--danger board-ai-confirm"></button>')
            .text(data.card_ids.length === 1 ? "Delete card" : "Delete " + data.card_ids.length + " cards"),
          $('<button type="button" class="board-ai-action__btn board-ai-cancel">Cancel</button>')
        );
      } else {
        $footer.append(
          $('<span class="board-ai-action__status"></span>').text(data.status === "confirmed" ? "Confirmed" : "Cancelled")
        );
      }
      $el.append($footer);
    }
    return $el;
  }

  // ── Keeping the board in step with the assistant's changes ──────────────────

  function cardList(columnId, swimlaneId) {
    return $(".card-list[data-column-id='" + columnId + "'][data-swimlane-id='" + swimlaneId + "']");
  }

  var needsRefresh = false;

  function applyToBoard(msg) {
    var data = msg.data || {};
    var card = data.card;

    if (data.type === "card_created") {
      var $list = cardList(card.column_id, card.swimlane_id);
      if ($list.length !== 1) { needsRefresh = true; return; }
      $list.append($(buildCardHtml(card)).attr("data-swimlane-id", card.swimlane_id));
    } else if (data.type === "card_moved") {
      var $card = $(".card-item[data-card-id='" + card.id + "']");
      var $target = cardList(card.column_id, card.swimlane_id);
      if (!$card.length || $target.length !== 1) { needsRefresh = true; return; }
      $card.attr("data-swimlane-id", card.swimlane_id).appendTo($target);
    } else if (data.type === "delete_done") {
      (data.card_ids || []).forEach(function (id) {
        $(".card-item[data-card-id='" + id + "']").remove();
      });
    }
  }

  function applyAllToBoard(actions) {
    needsRefresh = false;
    actions.forEach(applyToBoard);
    if (typeof refreshSortable === "function") refreshSortable();
    if (needsRefresh) {
      showWarningToast("Board changed", "Refresh the page to see all of the assistant's changes.");
    }
  }

  // ── Sessions and history ────────────────────────────────────────────────────

  function loadHistory(id) {
    clearMessages();
    $("#board-ai-messages").append(
      '<div class="board-ai-loading"><div class="spinner-border spinner-border-sm" role="status"></div><span>Loading chat…</span></div>'
    );
    $.ajax({
      url: baseUrl + "history/" + (id ? "?session_id=" + id : ""),
      method: "GET",
      success: function (data) {
        clearMessages();
        sessionId = data.session_id;
        if (!data.messages.length) appendSystem(WELCOME);
        data.messages.forEach(appendMessage);
        setNewChatEnabled(data.messages.some(function (m) { return m.role === "user"; }));
        loaded = true;
        scrollToBottom();
      },
      error: function () {
        clearMessages();
        $("#board-ai-messages").append(
          '<div class="system-message text-danger"><p>Couldn\'t load the chat. Please refresh the page.</p></div>'
        );
      },
    });
  }

  function showChatView() {
    $("#board-ai-sessions-view").addClass("d-none");
    $("#board-ai-body, #board-ai-form").removeClass("d-none");
  }

  function showSessionsView() {
    $("#board-ai-body, #board-ai-form").addClass("d-none");
    $("#board-ai-sessions-view").removeClass("d-none");
    var $list = $("#board-ai-sessions-list").html('<div class="ai-sessions-loading">Loading sessions…</div>');

    $.ajax({
      url: baseUrl + "sessions/",
      method: "GET",
      success: function (data) { renderSessions(data.sessions || []); },
      error: function () { $list.html('<div class="ai-sessions-empty">Error loading sessions.</div>'); },
    });
  }

  function renderEmptySessions() {
    $("#board-ai-sessions-list").html(
      '<div class="ai-sessions-empty"><i class="bi bi-chat-square-dots"></i><p>No chat history yet.</p></div>'
    );
  }

  function renderSessions(sessions) {
    var $list = $("#board-ai-sessions-list").empty();
    if (!sessions.length) { renderEmptySessions(); return; }

    sessions.forEach(function (s) {
      var dateStr = new Date(s.updated_at).toLocaleString(undefined, {
        month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
      });
      var $row = $('<div class="ai-session-row"></div>')
        .toggleClass("ai-session-row--active", s.id === sessionId)
        .append(
          $('<div class="ai-session-row__info"></div>').append(
            $('<span class="ai-session-row__date"></span>').text(dateStr),
            $('<span class="ai-session-row__count"></span>').text(
              s.message_count === 1 ? "1 message" : s.message_count + " messages"
            )
          ),
          $('<button type="button" class="ai-session-delete-btn" title="Delete this chat"><i class="bi bi-trash"></i></button>')
        );

      $row.on("click", function (e) {
        if ($(e.target).closest(".ai-session-delete-btn").length) return;
        showChatView();
        loadHistory(s.id);
      });

      $row.find(".ai-session-delete-btn").on("click", function (e) {
        e.stopPropagation();
        post(baseUrl + "sessions/" + s.id + "/delete/").done(function () {
          $row.remove();
          if (!$("#board-ai-sessions-list").children().length) renderEmptySessions();
          if (s.id === sessionId) {
            sessionId = null;
            clearMessages();
            appendSystem(WELCOME);
            setNewChatEnabled(false);
          }
        }).fail(function (xhr) {
          showErrorToast("Couldn't delete the chat", responseError(xhr));
        });
      });

      $list.append($row);
    });
  }

  // ── Panel ───────────────────────────────────────────────────────────────────

  function openPanel() {
    $panel.addClass("open");
    $("body").addClass("board-ai-open");
    $("#board-ai-toggle").attr("aria-expanded", "true");
    if (!loaded) loadHistory(null);
    setTimeout(function () { $("#board-ai-input").trigger("focus"); }, 300);
  }

  function closePanel() {
    $panel.removeClass("open");
    $("body").removeClass("board-ai-open");
    $("#board-ai-toggle").attr("aria-expanded", "false");
    setWebSearch(false);
    showChatView();
  }

  $("#board-ai-toggle").on("click", function () {
    if ($panel.hasClass("open")) closePanel(); else openPanel();
  });
  $("#board-ai-close").on("click", closePanel);
  $("#board-ai-history").on("click", showSessionsView);
  $("#board-ai-back").on("click", showChatView);
  $("#board-ai-web-search").on("click", function () { setWebSearch(!webSearch); });

  $("#board-ai-new").on("click", function () {
    post(baseUrl + "sessions/new/").done(function (data) {
      sessionId = data.session.id;
      showChatView();
      clearMessages();
      appendSystem(WELCOME);
      setNewChatEnabled(false);
      $("#board-ai-input").trigger("focus");
    }).fail(function (xhr) {
      showErrorToast("Couldn't start a new chat", responseError(xhr));
    });
  });

  // ── Asking ──────────────────────────────────────────────────────────────────

  $("#board-ai-input").on("keydown", function (e) {
    if ((e.key === "Enter" || e.key === "NumpadEnter") && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("board-ai-form").requestSubmit();
    }
  });

  $("#board-ai-form").on("submit", function (e) {
    e.preventDefault();
    var $input = $("#board-ai-input");
    var question = $input.val().trim();
    if (!question || $("#board-ai-submit").prop("disabled")) return;

    appendMessage({ role: "user", content: question });
    var $typing = $('<div class="assistant-message"><div class="typing-indicator"><span></span><span></span><span></span></div></div>');
    $("#board-ai-messages").append($typing);
    scrollToBottom();

    $input.val("");
    $("#board-ai-submit").prop("disabled", true);
    var searchWasEnabled = webSearch;
    if (searchWasEnabled) setWebSearch(false);

    post(baseUrl, { question: question, session_id: sessionId, web_search: searchWasEnabled })
      .done(function (data) {
        sessionId = data.session_id;
        $typing.remove();
        (data.actions || []).forEach(appendMessage);
        appendMessage({ role: "assistant", content: data.response });
        applyAllToBoard(data.actions || []);
        setNewChatEnabled(true);
      })
      .fail(function (xhr) {
        $typing.remove();
        var $err = $('<div class="d-inline-block bg-danger text-white p-2 rounded"></div>')
          .text(responseError(xhr, "Sorry, I encountered an error. Please try again."));
        $("#board-ai-messages").append($('<div class="assistant-message"></div>').append($err));
      })
      .always(function () {
        $("#board-ai-submit").prop("disabled", false);
        scrollToBottom();
      });
  });

  // ── Delete confirmations ────────────────────────────────────────────────────

  $("#board-ai-messages").on("click", ".board-ai-confirm, .board-ai-cancel", function () {
    var $action  = $(this).closest(".board-ai-action");
    var decision = $(this).hasClass("board-ai-confirm") ? "confirm" : "cancel";
    $action.find("button").prop("disabled", true);

    post(baseUrl + "actions/" + $action.data("message-id") + "/" + decision + "/")
      .done(function (data) {
        $action.replaceWith(renderAction(data.request));
        appendMessage(data.action);
        applyAllToBoard([data.action]);
        scrollToBottom();
      })
      .fail(function (xhr) {
        $action.find("button").prop("disabled", false);
        showErrorToast("Couldn't " + (decision === "confirm" ? "delete the cards" : "cancel"), responseError(xhr));
      });
  });
});
