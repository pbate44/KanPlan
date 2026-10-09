
var cardSelectedColor = null;
var cardSelectedCSSClass = null;

$(document).on("click", "#changeCardColorBtn", function () {
  $(".priority-section").hide();
  var $picker = $(".color-picker-section").show();
  $picker[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
});

$(document).on("click", ".card-color-swatch", function () {
  $(".card-color-swatch").removeClass("selected").css("border", "2px solid transparent");
  $(this).addClass("selected").css("border", "3px solid purple");
  cardSelectedColor = $(this).data("color");
  cardSelectedCSSClass = $(this).data("css-class");
});

$(document).on("mouseenter", ".card-color-swatch", function () {
  $(this).css("transform", "scale(1.1)");
});
$(document).on("mouseleave", ".card-color-swatch", function () {
  $(this).css("transform", "scale(1.0)");
});

$(document).on("click", "#saveCardColorBtn", function () {
  var cardId = $(this).data("card-id");

  if (!cardId) {
    alert("Error: Card ID is missing. Please try refreshing the page.");
    return;
  }

  var $btn = $(this);
  var originalText = $btn.text();
  $btn.prop("disabled", true).text("Saving...");

  $.ajax({
    url: "/update-card-color/" + cardId + "/",
    method: "POST",
    data: JSON.stringify({ color: cardSelectedColor, css_class: cardSelectedCSSClass }),
    contentType: "application/json",
    headers: { "X-CSRFToken": getCsrfToken() },
    success: function () {
      var $container = $(".card-detail-container");
      var existingClasses = $container.attr("class") || "";
      $container.attr("class", existingClasses.replace(/card-color-\S+/g, "").trim());
      $container.css({ "background-color": "", color: "", "box-shadow": "" });

      if (cardSelectedCSSClass) {
        $container.addClass(cardSelectedCSSClass);
      } else if (cardSelectedColor) {
        $container.css({
          "background-color": cardSelectedColor,
          color: "var(--text)",
          "box-shadow": "0 3px 8px " + cardSelectedColor + "80",
        });
      }

      $(".card-color-indicator").css("background-color", cardSelectedColor);
      updateCardColorOnBoard(cardId, cardSelectedColor, cardSelectedCSSClass);
      $(".color-picker-section").hide();
    },
    error: function (xhr) {
      alert(responseError(xhr, "Failed to update card color. Please try again."));
    },
    complete: function () {
      $btn.prop("disabled", false).text(originalText);
    },
  });
});

$(document).on("click", "#cancelCardColorBtn", function () {
  $(".card-color-indicator").css("background-color", "");
  $(".color-picker-section").hide();
  $(".card-color-swatch").removeClass("selected");
  cardSelectedColor = null;
  cardSelectedCSSClass = null;
});

function updateCardColorOnBoard(cardId, color, cssClass) {
  var $card = $(".card-item[data-card-id='" + cardId + "']");
  if ($card.length === 0) return;

  var existingClasses = $card.attr("class") || "";
  $card.attr("class", existingClasses.replace(/card-color-\S+/g, "").trim());
  $card.css({ "background-color": "", "box-shadow": "", color: "" });

  if (cssClass) {
    $card.addClass(cssClass);
  } else if (color) {
    $card.css({ "background-color": color, "box-shadow": "0 2px 4px " + color + "80" });
  }

  $card.css("color", "var(--text)");
}

function setupCardDetailModal() {
  $(".color-picker-section").hide();
  $(".card-color-swatch").css({
    cursor: "pointer", display: "inline-block", border: "2px solid transparent",
  });

  var cardId = $(".card-detail-container").data("card-id");
  var currentCSSClass = $(".card-detail-container").data("css-class");

  var saveButton = $("#saveCardColorBtn");
  if (!saveButton.data("card-id") && cardId) {
    saveButton.data("card-id", cardId);
  }

  if (currentCSSClass) {
    $(".card-color-swatch[data-css-class='" + currentCSSClass + "']").each(function () {
      $(this).addClass("selected").css("border", "3px solid #007bff");
      cardSelectedColor = $(this).data("color");
      cardSelectedCSSClass = $(this).data("css-class");
    });
  }
}
