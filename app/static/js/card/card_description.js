
function setDescriptionMenuLabel(hasText) {
  var $btn = $(".toggle-description-section");
  if ($btn.length) {
    $btn.html(
      '<i class="bi bi-file-text me-2" aria-hidden="true"></i>' +
      (hasText ? "Edit" : "Add") + " Description"
    );
  }
}

var DESC_MAX_LINES = 5;

function descLineCount(val) {
  return (val.match(/\n/g) || []).length + 1;
}

function buildEditorHTML(text) {
  var safe = (text || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  var lines = descLineCount(text || "");
  return '<div class="desc-editor">' +
    '<label class="visually-hidden" for="descriptionTextarea">Card description</label>' +
    '<textarea class="desc-editor__textarea" id="descriptionTextarea" rows="5">' + safe + '</textarea>' +
    '<div class="desc-editor__footer">' +
    '<span class="desc-line-counter">' + lines + ' / ' + DESC_MAX_LINES + ' lines</span>' +
    '<div class="desc-editor__actions">' +
    '<button type="button" class="btn save-description">Save</button>' +
    '<button type="button" class="btn cancel-description">Cancel</button>' +
    '</div></div></div>';
}

function renderReadView($editable, text) {
  if (text && text.trim().length) {
    var safe = $("<div>").text(text).html().replace(/\n/g, "<br>");
    $editable.html('<p class="card-desc__text">' + safe + '</p>');
    $editable.closest(".card-desc").removeClass("is-empty");
    setDescriptionMenuLabel(true);
  } else {
    $editable.closest(".card-desc").addClass("is-empty");
    setDescriptionMenuLabel(false);
  }
  $editable.removeClass("editing").attr("aria-busy", "false");

  var body = document.getElementById("card-desc");
  if (body) body.style.border = "";
}

$(document).on("click", ".card-desc__editable", function () {
  var $editable = $(this);
  if ($editable.hasClass("editing")) return;

  var $p = $editable.find("p");
  var currentText = $p.length
    ? $p.html().replace(/<br\s*\/?>/gi, "\n").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim()
    : $editable.text().trim();

  $editable.data("original-text", currentText);
  $editable.addClass("editing").attr("aria-busy", "true");
  $editable.html(buildEditorHTML(currentText));

  var body = document.getElementById("card-desc");
  if (body) body.style.border = "1px solid var(--border-hi)";
  
  var textarea = document.getElementById("descriptionTextarea");
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);
});

$(document).on("keydown", ".card-desc__editable", function (e) {
  if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    $(this).trigger("click");
  }
});

$(document).on("keydown", "#descriptionTextarea", function (e) {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    $(".save-description").trigger("click");
    return;
  }
  if (e.key === "Enter" && !e.ctrlKey && !e.metaKey) {
    if (descLineCount(this.value) >= DESC_MAX_LINES) {
      e.preventDefault();
    }
  }
});

$(document).on("input", "#descriptionTextarea", function () {
  var lines = descLineCount(this.value);
  var $counter = $(".desc-line-counter");
  $counter.text(lines + " / " + DESC_MAX_LINES + " lines");
  $counter.toggleClass("desc-line-counter--full", lines >= DESC_MAX_LINES);
});

$(document).on("click", ".save-description", function () {
  var $descParent = $(this).closest(".card-desc");
  var $editable = $(this).closest(".card-desc__editable");
  var cardId = $editable.data("card-id");
  var newDescription = $("#descriptionTextarea").val().trim();

  $editable.attr("aria-busy", "true");

  $.ajax({
    url: "/update-card-description/" + cardId + "/",
    method: "POST",
    data: JSON.stringify({ description: newDescription }),
    contentType: "application/json",
    headers: { "X-CSRFToken": getCsrfToken() },
    success: function () {
      if (!newDescription) {
        $editable.data("original-text", "");
        $descParent.hide().addClass("is-empty");
        setDescriptionMenuLabel(false);
        var body = document.getElementById("card-desc");
        if (body) body.style.border = "";
        return;
      }
      renderReadView($editable, newDescription);
    },
    error: function (xhr) {
      alert(responseError(xhr, "Failed to update description. Please try again."));
      $editable.removeClass("editing").attr("aria-busy", "false").html("");
    },
  });
});

$(document).on("click", ".cancel-description", function (e) {
  e.preventDefault();
  e.stopPropagation();

  var $descParent = $(this).closest(".card-desc");
  var $editable = $(this).closest(".card-desc__editable");
  var originalText = $editable.data("original-text") || "";

  if (!originalText) {
    $editable.removeClass("editing").attr("aria-busy", "false").html("");
    $editable.data("original-text", "");
    $descParent.hide().addClass("is-empty");
    var body = document.getElementById("card-desc");
    if (body) body.style.border = "";
    return;
  }
  
  renderReadView($editable, originalText);
});

$(document).on("click", ".toggle-description-section", function (e) {
  e.stopPropagation();
  e.preventDefault();

  var $descParent = $(".card-desc");
  $descParent.show().removeClass("is-empty");

  var $editable = $(".card-desc__editable");
  if (!$editable.length) return;

  if ($editable.hasClass("editing")) {
    $("#descriptionTextarea").trigger("focus");
    return;
  }

  $editable.trigger("click");
  $(".dropdown-menu.show").removeClass("show");
});
