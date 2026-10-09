
(function () {

  var $menu = $("#cardContextMenu");
  var currentCardId = null;

  function showMenu(x, y) {
    $menu.css({ left: 0, top: 0, display: "block" });

    var menuW = $menu.outerWidth();
    var menuH = $menu.outerHeight();
    var left  = (x + menuW > window.innerWidth)  ? x - menuW : x;
    var top   = (y + menuH > window.innerHeight) ? y - menuH : y;

    $menu.css({ left: left, top: top });
  }

  function hideMenu() {
    $menu.hide();
    currentCardId = null;
  }

  $(document).on("contextmenu", ".card-item", function (e) {
    e.preventDefault();
    e.stopPropagation();

    currentCardId = $(this).data("card-id");

    showMenu(e.clientX, e.clientY);
  });

  $(document).on("click", function (e) {
    if (!$(e.target).closest("#cardContextMenu").length) {
      hideMenu();
    }
  });

  $(document).on("keydown", function (e) {
    if (e.key === "Escape") hideMenu();
  });

  $("#ctxMenuChangeTitle").on("click", function () {
    if (!currentCardId) return;
    var cardId = currentCardId;
    hideMenu();

    var currentTitle = $(".card-item[data-card-id='" + cardId + "']").data("card-title") || "";
    $("#ctxTitleInput").val(currentTitle);
    $("#ctxTitleModal").data("card-id", cardId);
    showModal(document.getElementById("ctxTitleModal"));
    setTimeout(function () { $("#ctxTitleInput").focus().select(); }, 200);
  });

  $("#ctxTitleSaveBtn").on("click", function () {
    var cardId = $("#ctxTitleModal").data("card-id");
    var newTitle = $("#ctxTitleInput").val().trim();
    if (!newTitle) return;

    $.ajax({
      url: "/update-card-description/" + cardId + "/",
      method: "POST",
      data: JSON.stringify({ title: newTitle }),
      contentType: "application/json",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        $(".card-item[data-card-id='" + cardId + "']")
          .data("card-title", newTitle)
          .attr("data-card-title", newTitle)
          .find(".card-content").text(newTitle);
        hideModal(document.getElementById("ctxTitleModal"));
      },
      error: function (xhr) {
        alert(responseError(xhr, "Failed to update title. Please try again."));
      },
    });
  });

  $("#ctxTitleInput").on("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); $("#ctxTitleSaveBtn").trigger("click"); }
    if (e.key === "Escape") { hideModal(document.getElementById("ctxTitleModal")); }
  });

  var ctxSelectedColor    = null;
  var ctxSelectedCSSClass = null;

  $("#ctxMenuChangeColor").on("click", function () {
    if (!currentCardId) return;
    var cardId = currentCardId;
    hideMenu();

    var currentCSSClass = $(".card-item[data-card-id='" + cardId + "']").data("css-class") || "";
    ctxSelectedColor    = $(".card-item[data-card-id='" + cardId + "']").data("card-color") || null;
    ctxSelectedCSSClass = currentCSSClass || null;

    $("#ctxColorGrid .card-color-swatch").removeClass("selected");
    if (currentCSSClass) {
      $("#ctxColorGrid .card-color-swatch[data-css-class='" + currentCSSClass + "']").addClass("selected");
    }

    $("#ctxColorModal").data("card-id", cardId);
    showModal(document.getElementById("ctxColorModal"));
  });

  $(document).on("click", "#ctxColorGrid .card-color-swatch", function () {
    $("#ctxColorGrid .card-color-swatch").removeClass("selected");
    $(this).addClass("selected");
    ctxSelectedColor    = $(this).data("color");
    ctxSelectedCSSClass = $(this).data("css-class");
  });

  $("#ctxColorSaveBtn").on("click", function () {
    var cardId = $("#ctxColorModal").data("card-id");
    if (!ctxSelectedColor && !ctxSelectedCSSClass) {
      alert("Please select a color.");
      return;
    }

    var $btn = $(this);
    $btn.prop("disabled", true).text("Saving…");

    $.ajax({
      url: "/update-card-color/" + cardId + "/",
      method: "POST",
      data: JSON.stringify({ color: ctxSelectedColor, css_class: ctxSelectedCSSClass }),
      contentType: "application/json",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        updateCardColorOnBoard(cardId, ctxSelectedColor, ctxSelectedCSSClass);
        hideModal(document.getElementById("ctxColorModal"));
        ctxSelectedColor = null;
        ctxSelectedCSSClass = null;
      },
      error: function (xhr) {
        alert(responseError(xhr, "Failed to update color. Please try again."));
      },
      complete: function () {
        $btn.prop("disabled", false).text("Save");
      },
    });
  });

  var ctxSelectedPriority = null;

  $("#ctxMenuChangePriority").on("click", function () {
    if (!currentCardId) return;
    var cardId = currentCardId;
    hideMenu();

    var currentPriority = parseInt($(".card-item[data-card-id='" + cardId + "']").data("priority")) || 0;
    ctxSelectedPriority = currentPriority;

    $(".ctx-priority-btn").removeClass("active").css({ "background-color": "#f8f9fa", color: "#333" });
    if (currentPriority > 0) {
      applyPriorityStyle($(".ctx-priority-btn[data-value='" + currentPriority + "']").addClass("active"), currentPriority);
    }

    $("#ctxPriorityModal").data("card-id", cardId);
    showModal(document.getElementById("ctxPriorityModal"));
  });

  $(document).on("click", ".ctx-priority-btn", function () {
    $(".ctx-priority-btn").removeClass("active").css({ "background-color": "", color: "" });
    ctxSelectedPriority = parseInt($(this).data("value"));
    applyPriorityStyle($(this).addClass("active"), ctxSelectedPriority);
  });

  function applyPriorityStyle($btn, priority) {
    var bg, text;
    if (priority <= 3)      { bg = "#28a745"; text = "white"; }
    else if (priority <= 7) { bg = "#ffc107"; text = "black"; }
    else                    { bg = "#dc3545"; text = "white"; }
    $btn.css({ "background-color": bg, color: text });
  }

  $("#ctxPrioritySaveBtn").on("click", function () {
    var cardId = $("#ctxPriorityModal").data("card-id");
    if (!ctxSelectedPriority) { alert("Please select a priority."); return; }
    savePriority(cardId, ctxSelectedPriority);
    hideModal(document.getElementById("ctxPriorityModal"));
  });

  $("#ctxMenuDeleteCard").on("click", function () {
    if (!currentCardId) return;
    var cardId = currentCardId;
    hideMenu();

    var cardTitle = $(".card-item[data-card-id='" + cardId + "']").data("card-title") || "Untitled Card";
    $("#ctxDeleteCardTitle").text(cardTitle);
    $("#ctxConfirmDeleteBtn").data("card-id", cardId);
    showModal(document.getElementById("ctxDeleteCardModal"));
  });

  $("#ctxConfirmDeleteBtn").on("click", function () {
    var cardId = $(this).data("card-id");

    $.ajax({
      url: "/delete-card/" + cardId + "/",
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        $(".card-item[data-card-id='" + cardId + "']").remove();
        hideModal(document.getElementById("ctxDeleteCardModal"));
      },
      error: function (xhr) {
        console.error("Error deleting card:", xhr.responseText);
      },
    });
  });

}());
