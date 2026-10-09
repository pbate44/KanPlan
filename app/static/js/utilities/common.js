// Shared helpers, loaded on every page by base.html. Classic script, so these
// are globals; the dashboard's ES modules re-export them from dash_utils.js.

function getCookie(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    var cookies = document.cookie.split(";");
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function getCsrfToken() {
  var el = document.querySelector("[name=csrfmiddlewaretoken]");
  if (el) return el.value;
  return getCookie("csrftoken") || "";
}

/**
 * The message from a failed request. Accepts a jQuery xhr, a parsed JSON body
 * or response text; the server sends errors as {"status": "error", "message": ...}.
 */
function responseError(source, fallback) {
  var data = source;
  if (source && typeof source.responseText === "string") {
    data = source.responseJSON || source.responseText;
  }
  if (typeof data === "string") {
    try { data = JSON.parse(data); } catch (e) { data = null; }
  }
  return (data && data.message) || fallback || "Something went wrong. Please try again.";
}

function escapeHtml(text) {
  var map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text ?? "").replace(/[&<>"']/g, function (m) { return map[m]; });
}

function debounce(fn, wait) {
  wait = wait || 100;
  var timeout;
  return function () {
    var args = arguments;
    var context = this;
    clearTimeout(timeout);
    timeout = setTimeout(function () { fn.apply(context, args); }, wait);
  };
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' bytes';
  else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  else return (bytes / 1048576).toFixed(1) + ' MB';
}

/**
 * Show a toast notification
 * @param {string} type - The type of toast ('success', 'error', 'warning', 'info')
 * @param {string} title - The title of the toast; empty for a single-line toast
 * @param {string} message - The message content
 * @param {number} delay - Auto-hide delay in milliseconds (default: 5000)
 */
function showToast(type, title, message, delay = 5000) {
  let toastContainer = document.getElementById('app-toasts');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'app-toasts';
    toastContainer.className = 'toast-container position-fixed end-0 p-3';
    toastContainer.style.zIndex = '1080';
    document.body.appendChild(toastContainer);
  }

  const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

  const icons = {
    success: 'bi-check-circle-fill',
    error: 'bi-exclamation-triangle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill'
  };
  const kind = icons[type] ? type : 'info';

  const toastHtml = `
    <div id="${toastId}" class="toast app-toast app-toast--${kind}" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="${delay}">
      <div class="app-toast__inner">
        <i class="bi ${icons[kind]} app-toast__icon"></i>
        <div class="app-toast__body">
          ${title ? `<strong class="app-toast__title">${escapeHtml(title)}</strong>` : ''}
          ${escapeHtml(message)}
        </div>
        <button type="button" class="btn-close app-toast__close" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;

  toastContainer.insertAdjacentHTML('beforeend', toastHtml);

  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement);
  toast.show();

  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.remove();
  });

  return toast;
}

function showSuccessToast(title, message) {
  return showToast('success', title, message);
}

function showErrorToast(title, message) {
  return showToast('error', title, message);
}

function showWarningToast(title, message) {
  return showToast('warning', title, message);
}

function showInfoToast(title, message) {
  return showToast('info', title, message);
}

// Django messages, rendered into #flash-messages by base.html.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('#flash-messages li').forEach(function (li) {
    showToast(li.dataset.level, '', li.textContent.trim());
  });
});
