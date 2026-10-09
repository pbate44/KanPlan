
document.addEventListener('click', function(e) {
  if (e.target.closest('#addSubtaskBtn') || e.target.closest('#subtaskQuickAddBtn')) {
    var subtasksSection = document.getElementById("subtasksSection");
    var newSubtaskForm = document.getElementById("newSubtaskForm");
    var newSubtaskInput = document.getElementById("newSubtaskInput");

    if (subtasksSection) subtasksSection.classList.remove("d-none");

    if (newSubtaskForm && newSubtaskInput) {
      newSubtaskForm.classList.remove("d-none");
      setTimeout(function () { newSubtaskInput.focus(); }, 100);
    }
  }
});

document.addEventListener('click', function(e) {
  if (e.target.closest('#cancelSubtaskBtn')) {
    var newSubtaskForm = document.getElementById("newSubtaskForm");
    var newSubtaskInput = document.getElementById("newSubtaskInput");
    var subtasksSection = document.getElementById("subtasksSection");
    var subtasksList = document.getElementById("subtasksList");

    if (newSubtaskForm && newSubtaskInput) {
      newSubtaskForm.classList.add("d-none");
      newSubtaskInput.value = "";
    }

    if (subtasksSection && subtasksList && !subtasksList.querySelector('.subtask-item')) {
      subtasksSection.classList.add("d-none");
    }
  }
});

document.addEventListener('click', function(e) {
  if (e.target.closest('#saveSubtaskBtn')) {
    var newSubtaskInput = document.getElementById("newSubtaskInput");
    var cardId = document.querySelector(".card-detail-container")?.dataset.cardId;

    if (newSubtaskInput && cardId) {
      var title = newSubtaskInput.value.trim();
      if (title) {
        saveSubtask(cardId, title);
      } else {
        newSubtaskInput.focus();
      }
    }
  }
});

document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && e.target.id === 'newSubtaskInput') {
    e.preventDefault();
    var cardId = document.querySelector(".card-detail-container")?.dataset.cardId;
    var title = e.target.value.trim();
    if (title && cardId) {
      saveSubtask(cardId, title);
    }
  }
});

function loadSubtasks(cardId) {
  fetch('/cards/' + cardId + '/subtasks/', {
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === 'success') {
        renderSubtasks(data.subtasks);
        updateSubtasksCount(data.subtasks);
      }
    })
    .catch(function(err) { console.error('Error loading subtasks:', err); });
}

function saveSubtask(cardId, title) {
  fetch('/cards/' + cardId + '/subtasks/add/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify({ title: title }),
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === 'success') {
        loadSubtasks(cardId);
        var newSubtaskInput = document.getElementById("newSubtaskInput");
        if (newSubtaskInput) {
          newSubtaskInput.value = "";
          newSubtaskInput.focus();
        }
      } else {
        showErrorToast("Couldn't add subtask", responseError(data));
      }
    })
    .catch(function(err) { console.error('Error saving subtask:', err); });
}

function toggleSubtask(cardId, subtaskId) {
  fetch('/subtasks/' + subtaskId + '/toggle/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === 'success') {
        loadSubtasks(cardId);
      }
    })
    .catch(function(err) { console.error('Error toggling subtask:', err); });
}

function deleteSubtask(cardId, subtaskId) {
  fetch('/subtasks/' + subtaskId + '/delete/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === 'success') {
        loadSubtasks(cardId);
      }
    })
    .catch(function(err) { console.error('Error deleting subtask:', err); });
}

function renderSubtasks(subtasks) {
  var subtasksList = document.getElementById("subtasksList");
  var subtasksSection = document.getElementById("subtasksSection");
  if (!subtasksList) return;

  if (subtasks.length === 0) {
    subtasksList.innerHTML = '';
    if (subtasksSection) subtasksSection.classList.add("d-none");
    return;
  }

  if (subtasksSection) subtasksSection.classList.remove("d-none");

  var sortedSubtasks = subtasks.slice().sort(function (a, b) {
    if (a.is_complete === b.is_complete) return 0;
    return a.is_complete ? 1 : -1;
  });

  var cardId = document.querySelector(".card-detail-container")?.dataset.cardId;

  subtasksList.innerHTML = sortedSubtasks.map(function (subtask) {
    return '<div class="subtask-item d-flex align-items-center ' +
      (subtask.is_complete ? "completed" : "") + '" data-subtask-id="' + subtask.id + '">' +
      '<div class="form-check subtask-tickbox">' +
      '<input class="form-check-input subtask-checkbox" type="checkbox" ' +
      (subtask.is_complete ? "checked" : "") +
      " onchange=\"toggleSubtask('" + cardId + "', '" + subtask.id + "')\">" +
      '</div>' +
      '<div class="subtask-content flex-grow-1 ' +
      (subtask.is_complete ? "text-decoration-line-through text-muted" : "") + '">' +
      '<span class="subtask-name">' + escapeHtml(subtask.title) + '</span></div>' +
      '<button class="btn btn-sm btn-link p-1 edit-subtask-btn" ' +
      "onclick=\"editSubtask('" + cardId + "', '" + subtask.id + "', this)\" title=\"Edit subtask\">" +
      '<i class="bi bi-pencil"></i></button>' +
      '<button class="btn btn-sm btn-link text-danger p-1 delete-subtask-btn" ' +
      "onclick=\"deleteSubtask('" + cardId + "', '" + subtask.id + "')\" title=\"Delete subtask\">" +
      '<i class="bi bi-trash"></i></button></div>';
  }).join("");
}

function editSubtask(cardId, subtaskId, btn) {
  var item = btn.closest('.subtask-item');
  var nameEl = item.querySelector('.subtask-name');
  if (!nameEl || item.querySelector('.subtask-edit-input')) return;

  var input = document.createElement('input');
  input.type = 'text';
  input.className = 'subtask-edit-input';
  input.value = nameEl.textContent.trim();
  input.maxLength = 255;
  nameEl.replaceWith(input);
  input.focus();
  input.select();

  btn.querySelector('i').className = 'bi bi-check-lg';
  btn.title = 'Save subtask';
  btn.onclick = function(e) {
    e.stopPropagation();
    saveSubtaskEdit(cardId, subtaskId, input);
  };

  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); saveSubtaskEdit(cardId, subtaskId, input); }
    if (e.key === 'Escape') { loadSubtasks(cardId); }
  });
}

function saveSubtaskEdit(cardId, subtaskId, input) {
  var title = input.value.trim();
  if (!title) { input.focus(); return; }
  updateSubtask(cardId, subtaskId, title);
}

function updateSubtask(cardId, subtaskId, title) {
  fetch('/subtasks/' + subtaskId + '/update/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify({ title: title }),
  })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === 'success') {
        loadSubtasks(cardId);
      } else {
        showErrorToast("Couldn't update subtask", responseError(data));
      }
    })
    .catch(function(err) { console.error('Error updating subtask:', err); });
}

function updateSubtasksCount(subtasks) {
  var countBadge = document.querySelector(".subtasks-count");
  if (!countBadge) return;

  var completedCount = subtasks.filter(function (s) { return s.is_complete; }).length;
  var totalCount = subtasks.length;

  countBadge.textContent = completedCount + "/" + totalCount;
}
