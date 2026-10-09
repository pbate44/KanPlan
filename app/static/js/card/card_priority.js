
function initializePriorityDisplay() {
  var activeBtn = document.querySelector(".priority-btn.active");
  if (!activeBtn) return;

  var priority = parseInt(activeBtn.getAttribute("data-value"));
  if (!priority) return;

  document.querySelectorAll(".priority-btn").forEach(function (btn) {
    btn.classList.remove("active");
    btn.style.backgroundColor = "#f8f9fa";
    btn.style.color = "black";
  });

  activeBtn.classList.add("active");
  if (priority <= 3) {
    activeBtn.style.backgroundColor = "#28a745";
    activeBtn.style.color = "white";
  } else if (priority <= 7) {
    activeBtn.style.backgroundColor = "#ffc107";
    activeBtn.style.color = "black";
  } else {
    activeBtn.style.backgroundColor = "#dc3545";
    activeBtn.style.color = "white";
  }
}

$(document).on("click", ".priority-btn", function () {
  $(".priority-btn").removeClass("active").css({ "background-color": "#f8f9fa", color: "black" });

  var value = $(this).data("value");
  $(this).addClass("active");

  var bgColor, textColor;
  if (value <= 3)      { bgColor = "#28a745"; textColor = "white"; }
  else if (value <= 7) { bgColor = "#ffc107"; textColor = "black"; }
  else                 { bgColor = "#dc3545"; textColor = "white"; }

  $(this).css({ "background-color": bgColor, color: textColor });
});

$(document).on("click", "#savePriorityBtn", function () {
  var cardId = $(this).data("card-id");
  var selectedPriority = $(".priority-btn.active").data("value") || 0;
  if (!selectedPriority) { alert("Please select a priority"); return; }
  savePriority(cardId, selectedPriority);
});

$(document).on("click", ".priority-dropdown .priority-btn", function (e) {
  e.preventDefault();
  e.stopPropagation();

  var $button = $(this);
  var cardId = $button.closest(".priority-selector").data("card-id");
  var selectedPriority = $button.data("value");

  $button.closest(".btn-group").find(".priority-btn").removeClass("active").css({
    "background-color": "#f8f9fa", color: "black",
  });
  $button.addClass("active");

  var bgColor, textColor;
  if (selectedPriority <= 3)      { bgColor = "#28a745"; textColor = "white"; }
  else if (selectedPriority <= 7) { bgColor = "#ffc107"; textColor = "black"; }
  else                            { bgColor = "#dc3545"; textColor = "white"; }

  $button.css({ "background-color": bgColor, color: textColor });
  savePriority(cardId, selectedPriority);
});

function savePriority(cardId, priority) {
  $.ajax({
    url: "/update-card-priority/" + cardId + "/",
    method: "POST",
    data: JSON.stringify({ priority: priority }),
    contentType: "application/json",
    headers: { "X-CSRFToken": getCsrfToken() },
    success: function () {
      if (priority > 0) {
        var badgeColor = priority <= 3 ? "#28a745" : priority <= 7 ? "#ffc107" : "#dc3545";
        var textColor = priority <= 3 || priority > 7 ? "white" : "black";

        var $badge = $(".card-title").siblings(".priority-badge");
        if ($badge.length === 0) {
          $badge = $('<span class="priority-badge me-3 d-flex align-items-center justify-content-center"></span>');
          $badge.css({
            "background-color": badgeColor, color: textColor,
            "border-radius": "50%", width: "28px", height: "28px",
            "font-size": "14px", "font-weight": "600",
            "box-shadow": "0 2px 4px rgba(0,0,0,0.1)",
          });
          $(".card-title").after($badge);
        }
        $badge.text(priority).css({ "background-color": badgeColor, color: textColor });
      } else {
        $(".card-title").siblings(".priority-badge").remove();
      }

      updateCardPriorityDisplay(cardId, priority);
    },
    error: function (xhr) {
      alert(responseError(xhr, "Failed to update priority. Please try again."));
    },
  });
}

function updateCardPriorityDisplay(cardId, priority) {
  var $card = $(".card-item[data-card-id='" + cardId + "']");
  $card.find(".priority-badge").remove();

  if (priority > 0) {
    var bgColor = priority <= 3 ? "#28a745" : priority <= 7 ? "#ffc107" : "#dc3545";

    var $badge = $('<span class="priority-badge">' + priority + '</span>');
    $badge.css({
      position: "absolute", top: "2px", right: "2px",
      "background-color": bgColor,
      color: priority <= 7 && priority > 3 ? "black" : "white",
      "border-radius": "50%", width: "20px", height: "20px",
      "font-size": "12px", "text-align": "center", "line-height": "20px",
    });

    if ($card.css("position") !== "relative") $card.css("position", "relative");
    $card.append($badge);
  }
}

function applyPriorityBadgesToCards() {
  $(".card-item").each(function () {
    var priority = $(this).data("priority");
    if (priority > 0) {
      updateCardPriorityDisplay($(this).data("card-id"), priority);
    }
  });
}

$(function () { applyPriorityBadgesToCards(); });

$(document).on("click", ".toggle-priority-section", function () {
  $(".priority-section").show();
  $(".color-picker-section").hide();
  $("html, body").animate({ scrollTop: $(".priority-section").offset().top - 100 }, 200);
});
