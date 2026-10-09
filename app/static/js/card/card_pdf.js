
$(document).on("click", "#exportCardLogBtn", function () {
  var $btn = $(this);
  var originalHtml = $btn.html();
  $btn.html('<i class="bi bi-hourglass-split me-2"></i>Generating PDF...');
  $btn.prop("disabled", true);
  setTimeout(function () {
    $btn.html(originalHtml);
    $btn.prop("disabled", false);
  }, 2000);
});