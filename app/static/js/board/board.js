
$(function () {
  var cardClickedDirectly = false;

  function showCardModal() {
    var el = document.getElementById("cardDetailModal");
    if (!el) return;
    showModal(el);
  }

  $(document).on("click", ".card-item", function () {
    cardClickedDirectly = true;

    var cardTitle = $(this).data("card-title");
    var href = $(this).data("href");

    $("#cardDetailLabel").text(cardTitle);
    $("#cardDetailContent").html(
      '<div class="text-center p-4"><div class="spinner-border" role="status"></div><p>Loading...</p></div>'
    );

    $.ajax({
      url: href,
      headers: { "X-Requested-With": "XMLHttpRequest" },
      success: function (html) {
        $("#cardDetailContent").html(html);
        showCardModal();
        if (typeof setupLogFormSubmission === "function") setupLogFormSubmission();
        if (typeof initializePriorityDisplay === "function") initializePriorityDisplay();

        var cardId = document.querySelector(".card-detail-container")?.dataset.cardId;
        if (cardId && typeof loadSubtasks === "function") loadSubtasks(cardId);
      },
      error: function () {
        $("#cardDetailContent").html(
          '<div class="alert alert-danger m-3">Error loading card details</div>'
        );
        showCardModal();
      },
    });
  });

  $("#cardDetailModal").on("show.bs.modal", function (e) {
    if (cardClickedDirectly) return;
    var trigger = e.relatedTarget;
    if (!trigger) return;

    var $t = $(trigger);
    var url = $t.attr("href");
    var title = $t.data("card-title");
    $(".modal-title").text(title);

    $("#cardDetailContent").html(
      '<div class="text-center"><div class="spinner-border" role="status"></div><p>Loading...</p></div>'
    );

    $.ajax({
      url: url,
      headers: { "X-Requested-With": "XMLHttpRequest" },
      success: function (html) {
        $("#cardDetailContent").html(html);
        if (typeof setupLogFormSubmission === "function") setupLogFormSubmission();
        if (typeof initializePriorityDisplay === "function") initializePriorityDisplay();

        var cardId = document.querySelector(".card-detail-container")?.dataset.cardId;
        if (cardId && typeof loadSubtasks === "function") loadSubtasks(cardId);
      },
      error: function () {
        $("#cardDetailContent").html(
          '<div class="alert alert-danger">Error loading card details</div>'
        );
      },
    });
  });

  $("#addCardModal").on("hidden.bs.modal", function () {
    $("body").removeClass("modal-open");
    $(".modal-backdrop").remove();
    $("#addCardPriorityGrid .add-card-priority-btn").removeClass("active").css({ "background-color": "", color: "" });
    $("#addCardColorGrid .card-color-swatch").removeClass("selected");
  });

  $("#cardDetailModal").on("hidden.bs.modal", function () {
    $("body").removeClass("modal-open");
    $(".modal-backdrop").remove();
    cardClickedDirectly = false;
  });

  $(document).on("click", ".addCardButton", function (e) {
    e.preventDefault();

    var boardWrapper = document.querySelector(".board-wrapper");
    if (boardWrapper && boardWrapper.querySelectorAll(".card-item").length >= boardLimit("Cards")) {
      showErrorToast("Card limit reached", "Boards are limited to " + boardLimit("Cards") + " cards.");
      return;
    }

    var $btn = $(this);
    var columnId = $btn.data("column-id");
    var columnName = $btn.data("column-name");

    $("#columnId").val(columnId);
    $("#swimlaneId").val("");
    $("#columnNameDisplay").text(columnName);
    $("#cardTitle").val("");
    $("#cardDescription").val("");
    $("#addCardColor").val("");
    $("#addCardPriority").val("0");
    $("#addCardColorGrid .card-color-swatch").removeClass("selected");
    $("#addCardPriorityGrid .add-card-priority-btn").removeClass("active");

    showModal(document.getElementById("addCardModal"));
    setTimeout(function () { $("#cardTitle").trigger("focus"); }, 300);
  });

  $(document).on("click", "#addCardColorGrid .card-color-swatch", function () {
    $("#addCardColorGrid .card-color-swatch").removeClass("selected");
    $(this).addClass("selected");
    $("#addCardColor").val($(this).data("color"));
  });

  $(document).on("click", "#addCardPriorityGrid .add-card-priority-btn", function () {
    $("#addCardPriorityGrid .add-card-priority-btn").removeClass("active");
    $(this).addClass("active");
    $("#addCardPriority").val($(this).data("value"));
  });

  function buildCardHtml(card) {
    var safeTitle = escapeHtml(card.title);
    var priorityColor = card.priority <= 3 ? "#28a745" : card.priority <= 7 ? "#ffc107" : "#dc3545";
    var priorityTextColor = card.priority > 3 && card.priority <= 7 ? "black" : "white";

    var styleAttr = card.color && !card.css_class
      ? 'style="background-color: ' + card.color + '; position: relative;"'
      : 'style="position: relative;"';

    var priorityBadge = card.priority > 0
      ? '<span class="priority-badge" style="position:absolute;top:2px;right:2px;background-color:' + priorityColor +
        ';color:' + priorityTextColor + ';border-radius:50%;width:20px;height:20px;font-size:12px;text-align:center;line-height:20px;">' +
        card.priority + '</span>'
      : "";

    return '<li class="card-item' + (card.css_class ? " " + card.css_class : "") + '"' +
      ' data-card-id="' + card.id + '"' +
      ' data-href="/cards/' + card.id + '/"' +
      ' data-card-title="' + safeTitle + '"' +
      ' data-priority="' + (card.priority || 0) + '"' +
      ' ' + styleAttr + '>' +
      '<div class="card-content" title="' + safeTitle + '">' + safeTitle + '</div>' +
      priorityBadge + '</li>';
  }
  window.buildCardHtml = buildCardHtml;

  $("#addCardForm").on("submit", function (e) {
    e.preventDefault();

    var columnId = $("#columnId").val();
    var title = $("#cardTitle").val().trim();
    var description = $("#cardDescription").val().trim();
    var color = $("#addCardColor").val();
    var priority = parseInt($("#addCardPriority").val() || "0", 10);
    var $submit = $(this).find('button[type="submit"]');

    if (!title) { alert("Please enter a card title."); return; }

    $submit.prop("disabled", true).html(
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...'
    );

    var swimlaneId = $("#swimlaneId").val();
    var payload = { column_id: columnId, title: title, description: description, priority: priority };
    if (color) payload.color = color;
    if (swimlaneId) payload.swimlane_id = swimlaneId;

    fetch("/add-card/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        if (!r.ok) return r.text().then(function (txt) { throw new Error(responseError(txt)); });
        return r.json();
      })
      .then(function (data) {
        if (data.status !== "success") throw new Error(data.message || "Failed to add card");

        var card = data.card;
        var cardHtml = buildCardHtml(card);

        var $container = $(".card-list[data-column-id='" + card.column_id + "'][data-swimlane-id='" + card.swimlane_id + "']");

        if ($container.length !== 1) {
          throw new Error("Card created but container not found (column: " + columnId + "). Please refresh.");
        }

        $container.append(cardHtml);
        refreshSortable($container[0]);

        $("#cardTitle").val("");
        $("#cardDescription").val("");
        $("#addCardColor").val("");
        $("#addCardPriority").val("0");
        hideModal(document.getElementById("addCardModal"));
      })
      .catch(function (err) {
        console.error("Error adding card:", err);
        alert("Failed to add card: " + err.message);
      })
      .finally(function () {
        $submit.prop("disabled", false).text("Save Card");
      });
  });

  window._boardSortables = [];

  window.refreshSortable = function refreshSortable(containerEl) {
    if (typeof initSortables === "function") {
      initSortables();
    }
  };

  $("#cardDetailModal").on("shown.bs.modal", function () {
    if (typeof setupCardDetailModal === "function") setupCardDetailModal();
    if (typeof setupLogFormSubmission === "function") setupLogFormSubmission();
  });

});

function updateColumnGridLayout() {
  var kanbanBoard = document.querySelector(".kanban-board");
  if (!kanbanBoard) return;

  var remainingColumns = document.querySelectorAll(".column-header").length;

  kanbanBoard.style.setProperty("--board-columns", remainingColumns);
  kanbanBoard.dataset.columns = remainingColumns;

  kanbanBoard.style.display = "none";
  kanbanBoard.offsetHeight;
  kanbanBoard.style.display = "";

  kanbanBoard.style.gridTemplateColumns = remainingColumns > 0
    ? "160px repeat(" + remainingColumns + ", 1fr)"
    : "160px 1fr";

  document.dispatchEvent(new CustomEvent("boardLayoutChanged", {
    detail: { columnCount: remainingColumns },
  }));

  if (typeof updateButtonStates === "function") updateButtonStates();
}