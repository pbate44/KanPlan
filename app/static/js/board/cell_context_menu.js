
(function () {

  var $menu = $("#cellContextMenu");
  var targetColumnId   = null;
  var targetSwimlaneId = null;
  var targetColumnName = null;

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
    targetColumnId   = null;
    targetSwimlaneId = null;
    targetColumnName = null;
  }

  $(document).on("contextmenu", ".board-cell", function (e) {
    if ($(e.target).closest(".card-item").length) return;

    e.preventDefault();

    var $cell = $(this);
    targetColumnId   = $cell.data("column-id");
    targetSwimlaneId = $cell.data("swimlane-id");
    targetColumnName = $cell.data("column-name");

    showMenu(e.clientX, e.clientY);
  });

  $(document).on("click", function (e) {
    if (!$(e.target).closest("#cellContextMenu").length) {
      hideMenu();
    }
  });

  $(document).on("keydown", function (e) {
    if (e.key === "Escape") hideMenu();
  });

  $("#cellCtxAddCard").on("click", function () {
    if (!targetColumnId) return;

    var columnId   = targetColumnId;
    var swimlaneId = targetSwimlaneId;
    var columnName = targetColumnName || "Column";

    hideMenu();

    var boardWrapper = document.querySelector(".board-wrapper");
    if (boardWrapper && boardWrapper.querySelectorAll(".card-item").length >= boardLimit("Cards")) {
      showErrorToast("Card limit reached", "Boards are limited to " + boardLimit("Cards") + " cards.");
      return;
    }

    $("#columnId").val(columnId);
    $("#swimlaneId").val(swimlaneId);
    $("#columnNameDisplay").text(columnName);
    $("#cardTitle").val("");
    $("#cardDescription").val("");
    $("#addCardColor").val("");
    $("#addCardPriority").val("0");

    $("#addCardColorGrid .card-color-swatch").removeClass("selected");
    $("#addCardPriorityGrid .add-card-priority-btn").removeClass("active");
    $("#addCardPriorityGrid .add-card-priority-btn[data-value='0']").addClass("active");

    showModal(document.getElementById("addCardModal"));
    setTimeout(function () { $("#cardTitle").trigger("focus"); }, 300);
  });

}());
