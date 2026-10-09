
function setupLogFormSubmission() {
  var $form = $("#logEntryForm");
  if (!$form.length) return;

  var textarea = $form.find("#logEntryTextarea, #id_text").get(0);

  function autoSize(el) {
    if (!el) return;
    el.style.height = "auto";
    var cs = getComputedStyle(el);
    var maxH = parseFloat(cs.maxHeight);
    var target = el.scrollHeight;
    el.style.height = (isFinite(maxH) ? Math.min(target, maxH) : target) + "px";
    el.style.overflowY = (el.scrollHeight > 200) ? "auto" : "hidden";
  }

  if (textarea) {
    autoSize(textarea);
    ["input", "change"].forEach(function (evt) {
      textarea.addEventListener(evt, function () { autoSize(textarea); });
    });
    $form.on("reset", function () {
      requestAnimationFrame(function () { autoSize(textarea); });
    });
  }

  $form.off("submit");

  $form.on("submit", function (e) {
    e.preventDefault();

    var $submitBtn = $form.find('[type="submit"]');
    var data = $form.serialize();
    var cardId = $form.data("cardId") ||
      $form.find('input[name="card_id"]').val() ||
      window.cardId || null;

    $submitBtn.prop("disabled", true);

    $.ajax({
      url: $form.attr("action") || window.location.pathname,
      method: "POST",
      data: data,
      dataType: "json",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .done(function (json) {
        if (json.status !== "success" || !json.entry) {
          console.error("Unexpected response:", json);
          alert("Something went wrong saving the log entry.");
          return;
        }

        var entry = json.entry;
        var createdAt = entry.created_at || "";

        var html =
          '<li class="cardmodal__logentries-list" data-entry-id="' + entry.id + '">' +
          '<article class="cardmodal__logentry" aria-labelledby="entry-' + entry.id + '-title">' +
          '<header class="cardmodal__logentry-header">' +
          '<time datetime="' + createdAt + '">' + createdAt + '</time>' +
          '<div class="log-entry-actions">' +
          '<button type="button" class="edit-log-entry" data-entry-id="' + entry.id + '"' +
          ' title="Edit this log entry" aria-label="Edit log entry from ' + createdAt + '">' +
          '<i class="bi bi-pencil" aria-hidden="true"></i></button>' +
          '<button type="button" class="delete-log-entry" data-entry-id="' + entry.id + '"' +
          (cardId ? ' data-card-id="' + cardId + '"' : '') +
          ' title="Delete this log entry" aria-label="Delete log entry from ' + createdAt + '">' +
          '<i class="bi bi-trash" aria-hidden="true"></i></button>' +
          '</div>' +
          '</header>' +
          '<div class="cardmodal__logentry-text" id="entry-' + entry.id + '-title"><pre></pre></div>' +
          '</article></li>';

        var $logEntriesList = $("#logEntriesList");
        var $items = $logEntriesList.children("li");
        if (!$items.length || ($items.length === 1 && $items.first().hasClass("cardmodal__logentries-list-empty"))) {
          $logEntriesList.empty();
        }

        $logEntriesList.prepend(html);
        $logEntriesList.find('[data-entry-id="' + entry.id + '"] pre').text(entry.text);

        $form.get(0).reset();
        autoSize(textarea);

        $(".log-entries-container").scrollTop(0);

        var $logCountBadge = $(".log-counter span").first();
        if ($logCountBadge.length) {
          $logCountBadge.text(
            $logEntriesList.children("li").not(".cardmodal__logentries-list-empty").length
          );
        }
      })
      .fail(function (xhr, status, err) {
        console.error("Error saving log entry:", xhr.responseText || err);
        alert("Failed to save log entry. Please try again.");
      })
      .always(function () {
        $submitBtn.prop("disabled", false);
      });
  });

  $form.find("#logEntryTextarea, #id_text").off("keydown").on("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      $(this).closest("form").trigger("submit");
    }
  });
}

$(document).on("click", ".delete-log-entry", function () {
  var entryId = $(this).data("entry-id");
  if (!confirm("Are you sure you want to delete this log entry?")) return;

  $.ajax({
    url: "/delete-log-entry/" + entryId + "/",
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    success: function () {
      var $entryItem = $(".cardmodal__logentries-list[data-entry-id='" + entryId + "']");
      $entryItem.fadeOut(200, function () {
        $(this).remove();
        var remaining = $("#logEntriesList").children("li").length;
        $(".log-counter span").text(remaining);
        if (remaining === 0) {
          $("#logEntriesList").html(
            '<li class="cardmodal__logentries-list-empty"><p class="text-muted">No log entries yet.</p></li>'
          );
        }
      });
    },
    error: function (xhr) {
      alert(responseError(xhr, "Failed to delete log entry. Please try again."));
    },
  });
});

$(document).on("click", ".edit-log-entry", function () {
  var $btn = $(this);
  var entryId = $btn.data("entry-id");
  var $article = $btn.closest(".cardmodal__logentry");
  var $textDiv = $article.find(".cardmodal__logentry-text");

  if ($textDiv.hasClass("is-editing")) return;

  var originalText = $textDiv.find("pre").text();
  $textDiv.data("original-text", originalText);

  $textDiv.addClass("is-editing");
  $textDiv.html(
    '<textarea class="log-entry-edit-textarea">' + $("<div>").text(originalText).html() + '</textarea>' +
    '<div class="log-entry-edit-actions">' +
    '<button type="button" class="save-log-entry" data-entry-id="' + entryId + '" title="Save"><i class="bi bi-check-lg" aria-hidden="true"></i></button>' +
    '<button type="button" class="cancel-log-entry" title="Cancel"><i class="bi bi-x-lg" aria-hidden="true"></i></button>' +
    '</div>'
  );

  var $textarea = $textDiv.find(".log-entry-edit-textarea");
  $textarea.get(0).style.height = "auto";
  $textarea.get(0).style.height = $textarea.get(0).scrollHeight + "px";
  $textarea.focus().get(0).select();

  $textarea.on("input", function () {
    this.style.height = "auto";
    this.style.height = this.scrollHeight + "px";
  });

  $textarea.on("keydown", function (e) {
    if (e.key === "Escape") {
      cancelEdit($textDiv, originalText);
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      saveEdit(entryId, $textDiv, $textarea.val(), originalText);
    }
  });
});

$(document).on("click", ".cancel-log-entry", function () {
  var $textDiv = $(this).closest(".cardmodal__logentry-text");
  var originalText = $textDiv.data("original-text") || "";
  cancelEdit($textDiv, originalText);
});

$(document).on("click", ".save-log-entry", function () {
  var $btn = $(this);
  var entryId = $btn.data("entry-id");
  var $textDiv = $btn.closest(".cardmodal__logentry-text");
  var newText = $textDiv.find(".log-entry-edit-textarea").val();
  var originalText = $textDiv.data("original-text") || "";
  saveEdit(entryId, $textDiv, newText, originalText);
});

function cancelEdit($textDiv, originalText) {
  $textDiv.removeClass("is-editing");
  $textDiv.html("<pre></pre>");
  $textDiv.find("pre").text(originalText);
}

function saveEdit(entryId, $textDiv, newText, originalText) {
  newText = newText.trim();
  if (!newText) return;
  if (newText === originalText) {
    cancelEdit($textDiv, originalText);
    return;
  }

  $.ajax({
    url: "/update-log-entry/" + entryId + "/",
    method: "POST",
    contentType: "application/json",
    data: JSON.stringify({ text: newText }),
    headers: { "X-CSRFToken": getCsrfToken() },
    success: function (data) {
      cancelEdit($textDiv, data.text);
    },
    error: function (xhr) {
      alert(responseError(xhr, "Failed to save log entry. Please try again."));
    },
  });
}
