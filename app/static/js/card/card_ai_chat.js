
var _chatScrollObserver  = null;
var _currentSessionId    = null;
var _webSearchEnabled    = false;
var _selectedAttachments = {};
var _filePopupOpen       = false;

function setNewChatEnabled(enabled) {
  $("#new-chat-session").prop("disabled", !enabled);
}

function setWebSearch(enabled) {
  _webSearchEnabled = enabled;
  var $btn = $("#ai-web-search-toggle");
  $btn.attr("aria-pressed", enabled ? "true" : "false");
  $btn.toggleClass("ai-web-search-toggle--active", enabled);
}

function renderMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,     '<em>$1</em>')
    .replace(/`(.+?)`/g,       '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

$(function () {

  function scrollToBottom() {
    var el = document.querySelector("#ai-chat-body");
    if (el) setTimeout(function () { el.scrollTop = el.scrollHeight; }, 150);
  }

  function loadChatHistory(cardId, sessionId) {
    $("#loading-spinner").removeClass("d-none");
    $("#ai-chat-messages .user-message, #ai-chat-messages .assistant-message, #ai-chat-messages .system-message").remove();

    var url = "/card/" + cardId + "/ai-chat/history/";
    if (sessionId) url += "?session_id=" + sessionId;

    $.ajax({
      url: url,
      method: "GET",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        $("#loading-spinner").addClass("d-none");
        var hasRealMessages = data.messages.some(function (m) { return m.role === 'user' || m.role === 'assistant'; });
        setNewChatEnabled(hasRealMessages);
        if (data.messages.length === 0) {
          $("#ai-chat-messages").append(
            '<div class="system-message"><p>Hello! I\'m your AI assistant. I can help answer questions about this card. How can I help you today?</p></div>'
          );
          return;
        }
        data.messages.forEach(function (msg) {
          appendMessage(msg.role, msg.content);
        });
        scrollToBottom();
      },
      error: function (xhr) {
        $("#loading-spinner").addClass("d-none");
        $("#ai-chat-messages").append(
          '<div class="system-message text-danger"><p>Error loading chat history. Please try refreshing.</p></div>'
        );
        console.error("Error loading chat history:", xhr.responseText);
      },
    });
  }

  function appendMessage(role, content, attachmentNames) {
    if (role === "system") {
      $("#ai-chat-messages").append($('<div class="system-message"><p></p></div>').find('p').text(content).end());
    } else if (role === "user") {
      var $msg = $('<div class="user-message"></div>').text(content);
      if (attachmentNames && attachmentNames.length > 0) {
        var $att = $('<div class="user-message__attachment"></div>').append($('<i class="bi bi-paperclip"></i>'));
        $att.append(document.createTextNode(' ' + attachmentNames.join(', ')));
        $msg.append($att);
      }
      $("#ai-chat-messages").append($msg);
    } else if (role === "assistant") {
      $("#ai-chat-messages").append('<div class="assistant-message">' + renderMarkdown(content) + '</div>');
    }
  }

  function updateAttachBadge() {
    var count = Object.keys(_selectedAttachments).length;
    var $badge = $("#ai-attach-badge");
    var $btn   = $("#ai-attach-toggle");
    if (count > 0) {
      $badge.text(count).removeClass("d-none");
      $btn.addClass("ai-attach-toggle--active");
    } else {
      $badge.addClass("d-none");
      $btn.removeClass("ai-attach-toggle--active");
    }
  }

  function clearAttachmentSelection() {
    _selectedAttachments = {};
    updateAttachBadge();
  }

  function closeFilePopup() {
    _filePopupOpen = false;
    $("#ai-file-popup").addClass("d-none");
    $("#ai-attach-toggle").attr("aria-pressed", "false");
  }

  function openFilePopup(cardId) {
    _filePopupOpen = true;
    $("#ai-file-popup").removeClass("d-none");
    $("#ai-attach-toggle").attr("aria-pressed", "true");

    var $list = $("#ai-file-popup-list").html('<div class="ai-file-popup__empty">Loading...</div>');

    $.ajax({
      url: "/cards/" + cardId + "/attachments/",
      method: "GET",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        var attachments = data.attachments || [];
        $list.empty();
        if (attachments.length === 0) {
          $list.html('<div class="ai-file-popup__empty">No files attached to this card.</div>');
          return;
        }
        attachments.forEach(function (a) {
          var isSelected = !!_selectedAttachments[String(a.id)];
          $list.append(
            $('<div class="ai-file-item' + (isSelected ? ' ai-file-item--selected' : '') + '"></div>')
              .data("id", String(a.id))
              .data("filename", a.filename)
              .append(
                $('<i class="bi bi-paperclip"></i>'),
                $('<span class="ai-file-item__name"></span>').text(a.filename),
                $('<i class="bi bi-check2 ai-file-item__check"></i>')
              )
          );
        });
      },
      error: function () {
        $list.html('<div class="ai-file-popup__empty">Error loading files.</div>');
      }
    });
  }

  $(document).on("click", "#ai-attach-toggle", function (e) {
    e.stopPropagation();
    var cardId = $("#ai-chat-panel").attr("data-card-id");
    if (!cardId) return;
    if (_filePopupOpen) { closeFilePopup(); } else { openFilePopup(cardId); }
  });

  $(document).on("click", ".ai-file-item", function () {
    var $item    = $(this);
    var id       = $item.data("id");
    var filename = $item.data("filename");
    if (_selectedAttachments[id]) {
      delete _selectedAttachments[id];
      $item.removeClass("ai-file-item--selected");
    } else {
      _selectedAttachments[id] = filename;
      $item.addClass("ai-file-item--selected");
    }
    updateAttachBadge();
  });

  $(document).on("click", function (e) {
    if (_filePopupOpen && !$(e.target).closest("#ai-file-popup, #ai-attach-toggle").length) {
      closeFilePopup();
    }
  });

  function openChatPanel(cardId) {
    $("#ai-chat-panel").attr("data-card-id", cardId).addClass("open");
    $(".card-detail-container").addClass("modal-left-half");
    $("#cardDetailModal .modal-dialog").addClass("modal-left-half");

    loadMostRecentSession(cardId);

    var msgContainer = document.querySelector("#ai-chat-messages");
    if (msgContainer && !_chatScrollObserver) {
      _chatScrollObserver = new MutationObserver(function () {
        var isAtBottom = msgContainer.scrollHeight - msgContainer.scrollTop <= msgContainer.clientHeight + 5;
        if (isAtBottom) msgContainer.scrollTop = msgContainer.scrollHeight;
      });
      _chatScrollObserver.observe(msgContainer, { childList: true });
    }
    setTimeout(function () { $("#ai-chat-input").focus(); }, 300);
  }

  function loadMostRecentSession(cardId) {
    $.ajax({
      url: "/card/" + cardId + "/ai-chat/sessions/",
      method: "GET",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        if (data.sessions && data.sessions.length > 0) {
          _currentSessionId = data.sessions[0].id;
        } else {
          _currentSessionId = null;
        }
        loadChatHistory(cardId, _currentSessionId);
      },
      error: function () {
        _currentSessionId = null;
        loadChatHistory(cardId, null);
      }
    });
  }

  $(document).on("click", "#ai-chat-toggle, #openAIChatBtn", function () {
    var cardId = $(this).data("card-id") || $("#ai-chat-panel").attr("data-card-id");
    var isOpen = $("#ai-chat-panel").hasClass("open");

    if (isOpen) {
      closeChatPanel();
    } else {
      openChatPanel(cardId);
    }
  });

  function closeChatPanel() {
    $("#ai-chat-panel").removeClass("open");
    $(".card-detail-container").removeClass("modal-left-half");
    $("#cardDetailModal .modal-dialog").removeClass("modal-left-half");
    setWebSearch(false);
    closeFilePopup();
    clearAttachmentSelection();
    showChatView();
  }

  $(document).on("click", "#close-ai-chat", function () {
    closeChatPanel();
  });

  $(document).on("shown.bs.modal", "#cardDetailModal", function (e) {
    if (e.target !== this) return;
    var $panel = $("#ai-chat-panel");
    if ($panel.attr("data-always-open") === "1" && !$panel.hasClass("open")) {
      var cardId = $panel.attr("data-card-id") || $(".card-detail-container").data("card-id");
      if (cardId) openChatPanel(String(cardId));
    }
  });

  $(document).on("hidden.bs.modal", "#cardDetailModal", function (e) {
    if (e.target !== this) return;
    $("#ai-chat-panel").removeClass("open");
    $(".card-detail-container").removeClass("modal-left-half");
    $("#cardDetailModal .modal-dialog").removeClass("modal-left-half");
    $("#cardOptionsDropdown").removeClass("d-none");
    showChatView();
    _currentSessionId = null;
    if (_chatScrollObserver) {
      _chatScrollObserver.disconnect();
      _chatScrollObserver = null;
    }
  });

  $(document).on("click", "#new-chat-session", function () {
    var cardId = $("#ai-chat-panel").attr("data-card-id");
    if (!cardId) return;

    $.ajax({
      url: "/card/" + cardId + "/ai-chat/sessions/new/",
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        _currentSessionId = data.session.id;
        setNewChatEnabled(false);
        showChatView();
        $("#ai-chat-messages .user-message, #ai-chat-messages .assistant-message, #ai-chat-messages .system-message").remove();
        $("#ai-chat-messages").append(
          '<div class="system-message"><p>Hello! I\'m your AI assistant. I can help answer questions about this card. How can I help you today?</p></div>'
        );
        setTimeout(function () { $("#ai-chat-input").focus(); }, 100);
      },
      error: function (xhr) {
        console.error("Error creating new session:", xhr.responseText);
      }
    });
  });

  function showChatView() {
    $("#ai-sessions-view").addClass("d-none");
    $("#ai-chat-body").removeClass("d-none");
    $("#ai-chat-form").removeClass("d-none");
  }

  function showHistoryView(cardId) {
    $("#ai-chat-body").addClass("d-none");
    $("#ai-chat-form").addClass("d-none");
    $("#ai-sessions-view").removeClass("d-none");
    loadSessionsList(cardId);
  }

  $(document).on("click", "#view-chat-history", function () {
    var cardId = $("#ai-chat-panel").attr("data-card-id");
    if (!cardId) return;
    showHistoryView(cardId);
  });

  $(document).on("click", "#back-to-chat", function () {
    showChatView();
  });

  function loadSessionsList(cardId) {
    $("#ai-sessions-list").html('<div class="ai-sessions-loading">Loading sessions...</div>');

    $.ajax({
      url: "/card/" + cardId + "/ai-chat/sessions/",
      method: "GET",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        renderSessionsList(cardId, data.sessions || []);
      },
      error: function () {
        $("#ai-sessions-list").html('<div class="ai-sessions-empty">Error loading sessions.</div>');
      }
    });
  }

  function renderSessionsList(cardId, sessions) {
    var $list = $("#ai-sessions-list").empty();

    if (sessions.length === 0) {
      $list.append('<div class="ai-sessions-empty"><i class="bi bi-chat-square-dots"></i><p>No chat history yet.</p></div>');
      return;
    }

    sessions.forEach(function (s) {
      var date    = new Date(s.updated_at);
      var dateStr = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
      var msgText = s.message_count === 1 ? "1 message" : s.message_count + " messages";
      var isCurrent = (s.id === _currentSessionId);

      var $row = $(
        '<div class="ai-session-row' + (isCurrent ? ' ai-session-row--active' : '') + '" data-session-id="' + s.id + '">' +
          '<div class="ai-session-row__info">' +
            '<span class="ai-session-row__date">' + dateStr + '</span>' +
            '<span class="ai-session-row__count">' + msgText + '</span>' +
          '</div>' +
          '<button class="ai-session-delete-btn" data-session-id="' + s.id + '" title="Delete this chat">' +
            '<i class="bi bi-trash"></i>' +
          '</button>' +
        '</div>'
      );

      $row.on("click", function (e) {
        if ($(e.target).closest('.ai-session-delete-btn').length) return;
        _currentSessionId = s.id;
        showChatView();
        loadChatHistory(cardId, s.id);
      });

      $row.find('.ai-session-delete-btn').on("click", function (e) {
        e.stopPropagation();
        deleteSession(cardId, s.id, $row);
      });

      $list.append($row);
    });
  }

  function deleteSession(cardId, sessionId, $row) {
    $.ajax({
      url: "/card/" + cardId + "/ai-chat/sessions/" + sessionId + "/delete/",
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        $row.remove();
        if ($("#ai-sessions-list").children().length === 0) {
          $("#ai-sessions-list").html('<div class="ai-sessions-empty"><i class="bi bi-chat-square-dots"></i><p>No chat history yet.</p></div>');
        }

        if (sessionId === _currentSessionId) {
          _currentSessionId = null;
          $("#ai-chat-messages .user-message, #ai-chat-messages .assistant-message, #ai-chat-messages .system-message").remove();
          $("#ai-chat-messages").append(
            '<div class="system-message"><p>Hello! I\'m your AI assistant. I can help answer questions about this card. How can I help you today?</p></div>'
          );
        }
      },
      error: function (xhr) {
        console.error("Error deleting session:", xhr.responseText);
      }
    });
  }

  $(document).on("click", "#ai-web-search-toggle", function () {
    setWebSearch(!_webSearchEnabled);
  });

  $(document).on('keydown', '#ai-chat-input', function (e) {
    if ((e.key === 'Enter' || e.key === 'NumpadEnter') && !e.shiftKey) {
      e.preventDefault();
      var form = document.getElementById('ai-chat-form');
      if (!form) return;
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }
  });

  $(document).on("submit", "#ai-chat-form", function (e) {
    e.preventDefault();

    var question     = $("#ai-chat-input").val().trim();
    var cardId       = $("#ai-chat-panel").attr("data-card-id");
    if (!question || !cardId) return;

    var attachmentIds   = Object.keys(_selectedAttachments).map(Number);
    var attachmentNames = Object.values(_selectedAttachments);

    appendMessage('user', question, attachmentNames.length > 0 ? attachmentNames : null);

    var loadingMsgId = "loading-" + Date.now();
    $("#ai-chat-messages").append(
      '<div id="' + loadingMsgId + '" class="assistant-message"><div class="typing-indicator"><span></span><span></span><span></span></div></div>'
    );
    scrollToBottom();

    $("#ai-chat-input").val("");
    closeFilePopup();
    clearAttachmentSelection();

    var searchWasEnabled = _webSearchEnabled;
    if (searchWasEnabled) setWebSearch(false);

    $.ajax({
      url: "/card/" + cardId + "/ai-chat/",
      method: "POST",
      contentType: "application/json",
      data: JSON.stringify({ question: question, session_id: _currentSessionId, web_search: searchWasEnabled, attachment_ids: attachmentIds }),
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        if (data.session_id) _currentSessionId = data.session_id;
        $("#" + loadingMsgId).remove();
        appendMessage('assistant', data.response);
        setNewChatEnabled(true);
        scrollToBottom();
      },
      error: function (xhr) {
        $("#" + loadingMsgId).remove();
        var errorMessage = responseError(xhr, "Sorry, I encountered an error. Please try again.");
        var $errDiv = $('<div class="d-inline-block bg-danger text-white p-2 rounded"></div>').text(errorMessage);
        $("#ai-chat-messages").append($('<div class="assistant-message"></div>').append($errDiv));
        scrollToBottom();
      },
    });
  });

  $(window).on("resize", function () {
    if ($("#ai-chat-panel").hasClass("open")) scrollToBottom();
  });

});

function updateLogEntriesList(cardId) {
  $.ajax({
    url: "/cards/" + cardId + "/",
    headers: { "X-Requested-With": "XMLHttpRequest" },
    success: function (html) {
      var $newContent = $(html);
      $("#logEntriesList").html($newContent.find("#logEntriesList").html());
    },
  });
}
