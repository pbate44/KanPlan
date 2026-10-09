
function showModal(el) {
  if (!el) return;
  bootstrap.Modal.getOrCreateInstance(el).show();
}

function hideModal(el) {
  if (!el) return;
  var instance = bootstrap.Modal.getInstance(el);
  if (instance) instance.hide();
}

// Limits set by the server, published on the board page's .board-wrapper.
function boardLimit(name) {
  var wrapper = document.querySelector(".board-wrapper");
  return wrapper ? parseInt(wrapper.dataset["max" + name], 10) : Infinity;
}
