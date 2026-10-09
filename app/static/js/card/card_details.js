
$(function () {

  $(document).on("click", "#cardTitleDisplay, #editCardTitleBtn", function () {
    var $cardTitle = $(this).attr("id") === "editCardTitleBtn"
      ? $("#cardTitleDisplay")
      : $(this);

    if ($cardTitle.find("input").length) return;

    var cardId = $cardTitle.data("card-id");
    var currentTitle = $cardTitle.text().trim();

    var $input = $('<input type="text" id="cardTitleInput" class="form-control">').val(currentTitle);
    $cardTitle.empty().append($input);

    $input.css({ "width": "100%"});

    $input.focus().select();

    $input.on("blur", function () {
      $(this).css("width", "100%");
      saveCardTitle();
    });

    $input.on("keypress", function (e) {
      if (e.which === 13) { e.preventDefault(); saveCardTitle(); }
    });

    function saveCardTitle() {
      var newTitle = $input.val().trim();
      if (newTitle && newTitle !== currentTitle) {
        $.ajax({
          url: "/update-card-description/" + cardId + "/",
          method: "POST",
          data: JSON.stringify({ title: newTitle }),
          contentType: "application/json",
          headers: { "X-CSRFToken": getCsrfToken() },
          success: function () {
            $cardTitle.text(newTitle);
            $("#cardDetailLabel").text(newTitle);
            $(".card-item[data-card-id='" + cardId + "'] .card-content")
              .text(newTitle).closest(".card-item").attr("data-card-title", newTitle);
          },
          error: function (xhr) {
            alert(responseError(xhr, "Failed to update card title. Please try again."));
            $cardTitle.text(currentTitle);
          },
        });
      } else {
        $cardTitle.text(currentTitle);
      }
      $input.off("blur keypress");
    }
  });

  $("#editBoardTitleBtn").on("click", function () {
    var $boardTitle = $("#boardTitle");
    var currentTitle = $boardTitle.text().trim();

    var $input = $('<input type="text" id="boardTitleInput" class="form-control form-control-lg">').val(currentTitle);
    $boardTitle.empty().append($input);
    $input.focus().select();
    $input.on("blur", saveBoardTitle);
    $input.on("keypress", function (e) { if (e.which === 13) saveBoardTitle(); });

    function saveBoardTitle() {
      var newTitle = $input.val().trim();
      if (newTitle && newTitle !== currentTitle) {
        var boardId = window.location.pathname.match(/\/board\/(\d+)\//)[1];
        $.ajax({
          url: "/update-board-title/" + boardId + "/",
          method: "POST",
          data: JSON.stringify({ title: newTitle }),
          contentType: "application/json",
          headers: { "X-CSRFToken": getCsrfToken() },
          success: function () { $boardTitle.text(newTitle); },
          error: function (xhr) {
            alert(responseError(xhr, "Failed to update board title. Please try again."));
            $boardTitle.text(currentTitle);
          },
        });
      } else {
        $boardTitle.text(currentTitle);
      }
      $input.off("blur keypress");
    }
  });

  $(document).on("click", ".deleteCardBtn, #dropdownDeleteCardBtn", function () {
    var cardId = $(this).data("card-id");
    var cardTitle = $(".card-title-text").text() || "Untitled Card";
    $("#cardToDelete .card-title-preview").text(cardTitle);
    $("#confirmDeleteCardBtn").data("card-id", cardId);
    showModal(document.getElementById("deleteCardModal"));
  });

  $(document).on("click", "#confirmDeleteCardBtn", function () {
    var cardId = $(this).data("card-id");

    $.ajax({
      url: "/delete-card/" + cardId + "/",
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        $(".card-item[data-card-id='" + cardId + "']").remove();
        hideModal(document.getElementById("deleteCardModal"));
        hideModal(document.getElementById("cardDetailModal"));
      },
      error: function (xhr) {
        console.error("Error deleting card:", xhr.responseText);
      },
    });
  });

  $(document).on("click", '.cancelDeleteCardBtn, [data-bs-dismiss="modal"]', function () {
    $("#deleteCardModal").modal("hide");
    $("#confirmDeleteCardBtn").removeData("card-id");
  });

  function updateButtonStates() {
    var swimlaneCount = document.querySelectorAll(".swimlane-row").length;
    var columnCount = document.querySelectorAll(".column-header").length;
    var maxSwimlanes = boardLimit("Swimlanes");
    var maxColumns = boardLimit("Columns");

    var $swimlaneBtn = $("#addSwimlaneBtn");
    if (swimlaneCount >= maxSwimlanes) {
      $swimlaneBtn.prop("disabled", true).removeClass("btn-outline-primary")
        .addClass("btn-outline-secondary").attr("title", "Maximum swimlanes reached (" + maxSwimlanes + "/" + maxSwimlanes + ")");
    } else {
      $swimlaneBtn.prop("disabled", false).removeClass("btn-outline-secondary")
        .addClass("btn-outline-primary").attr("title", "Add new swimlane (" + swimlaneCount + "/" + maxSwimlanes + ")");
    }
    var swimlaneCountEl = document.getElementById("swimlaneCurrentCount");
    if (swimlaneCountEl) swimlaneCountEl.textContent = swimlaneCount;

    var $columnBtn = $("#addColumnBtn");
    if (columnCount >= maxColumns) {
      $columnBtn.prop("disabled", true).removeClass("btn-outline-primary")
        .addClass("btn-outline-secondary").attr("title", "Maximum columns reached (" + maxColumns + "/" + maxColumns + ")");
    } else {
      $columnBtn.prop("disabled", false).removeClass("btn-outline-secondary")
        .addClass("btn-outline-primary").attr("title", "Add new column (" + columnCount + "/" + maxColumns + ")");
    }
  }

  window.updateButtonStates = updateButtonStates;

  updateButtonStates();

  var observer = new MutationObserver(updateButtonStates);
  observer.observe(document.querySelector(".kanban-board"), { childList: true, subtree: true });

});
