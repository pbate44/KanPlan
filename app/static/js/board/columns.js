
$(function () {

  $(document).on("click", ".column-name", function () {
    var $columnName = $(this);
    var columnId = $columnName.data("column-id");
    var currentName = $columnName.text().trim();

    $columnName.html(
      '<input type="text" class="column-name-input form-control form-control-sm" value="' + escapeHtml(currentName) + '">'
    );
    var $input = $columnName.find("input");

    $input.focus().select();
    $input.on("blur", saveColumnName);
    $input.on("keypress", function (e) {
      if (e.which === 13) saveColumnName();
    });

    function saveColumnName() {
      var newName = $input.val().trim();
      if (newName && newName !== currentName) {
        $.ajax({
          url: "/update-column-name/" + columnId + "/",
          method: "POST",
          data: JSON.stringify({ name: newName }),
          contentType: "application/json",
          headers: { "X-CSRFToken": getCsrfToken() },
          success: function () {
            $columnName.text(newName);
            $('button[data-column-id="' + columnId + '"]').attr("data-column-name", newName);
          },
          error: function (xhr) {
            alert(responseError(xhr, "Failed to update column name. Please try again."));
            $columnName.text(currentName);
          },
        });
      } else {
        $columnName.text(currentName);
      }
      $input.off("blur keypress");
    }
  });

  $("#addColumnBtn").on("click", function (e) {
    showModal(document.getElementById("addColumnModal"));
  });

  $("#addColumnForm").on("submit", function (e) {
    e.preventDefault();

    var name = $("#columnName").val().trim();
    var boardId = $(this).data("board-id");

    if (!boardId) {
      var urlMatch = window.location.pathname.match(/\/boards\/(\d+)\//);
      if (urlMatch && urlMatch[1]) {
        boardId = urlMatch[1];
        $(this).attr("data-board-id", boardId);
      }
    }

    if (!boardId) {
      console.error("Missing board_id when submitting Add Column");
      return;
    }

    $.ajax({
      url: "/add-column/",
      method: "POST",
      data: JSON.stringify({ board_id: boardId, name: name }),
      contentType: "application/json",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function (data) {
        if (data.status === "success") {
          $("#addColumnModal").modal("hide");
          window.location.reload();
        }
        updateColumnDeleteButtons();
      },
      error: function (xhr) {
        alert(responseError(xhr, "Failed to create column. Please try again."));
      },
    });
  });

  var pendingColumnDeletion = null;

  $(document).on("click", ".delete-column-btn, .dropdown-item-danger", function () {
    var columnId = $(this).data("column-id");
    var columnName = $(this).data("column-name");

    pendingColumnDeletion = { columnId: columnId, columnName: columnName };
    $("#deleteColumnName").text(columnName);

    showModal(document.getElementById("deleteColumnModal"));
  });

  $("#confirmDeleteColumn").on("click", function () {
    if (!pendingColumnDeletion) return;

    var columnId = pendingColumnDeletion.columnId;

    $.ajax({
      url: "/delete-column/" + columnId + "/",
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      success: function () {
        $(".column-header[data-column-id='" + columnId + "']").fadeOut("fast", function () {
          $(this).remove();
          updateColumnGridLayout();
          updateColumnDeleteButtons();
        });

        $(".board-cell[data-column-id='" + columnId + "']").fadeOut("fast", function () {
          $(this).remove();
          updateColumnGridLayout();
        });
        
        hideModal(document.getElementById("deleteColumnModal"));
      },
      error: function (xhr) {
        alert(responseError(xhr, "Failed to delete column. Please try again."));
      },
    });
  });

  $("#deleteColumnModal").on("hidden.bs.modal", function () {
    pendingColumnDeletion = null;
  });

  $("#addColumnModal").on("hidden.bs.modal", function () {
    $("#columnName").val("").removeClass("is-invalid");
    $("#submitColumnBtn").prop("disabled", false).html('<i class="bi bi-plus-lg me-1"></i>Add Column');
  });


  function updateColumnDeleteButtons() {
    const columnHeaders = document.querySelectorAll('.column-header');
    const deleteButtons = document.querySelectorAll('.delete-column-btn');
    
    if (columnHeaders.length <= 1) {
      deleteButtons.forEach(btn => btn.style.display = 'none');
    } else {
      deleteButtons.forEach(btn => btn.style.display = '');
    }
  }

  
  function updateColumnGridLayout() {
    const board = document.querySelector('.kanban-board');
    const wrapper = document.querySelector('.board-wrapper');
    if (!board) return;

    const newCount = document.querySelectorAll('.column-header').length;
    board.dataset.columns = newCount;
    wrapper.dataset.currentColumns = newCount;
    // A column change can add or remove the board's horizontal scrollbar,
    // which the swimlane fill height accounts for.
    updateSwimlaneGridLayout();
  }

});