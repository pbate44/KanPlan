
var apiRequest = function (url, body) {
  return fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify(body)
  });
};

var initSortables = (function () {
  var initialized = new WeakSet();

  return function () {
    document.querySelectorAll('.card-list').forEach(function (el) {
      if (initialized.has(el)) return;
      initialized.add(el);

      new Sortable(el, {
        group: 'cards',
        animation: 0,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        handle: '.card-item',
        onEnd: function (evt) {
          var cardId = evt.item.dataset.cardId;
          var newColumnId = evt.to.dataset.columnId;
          var oldColumnId = evt.from.dataset.columnId;
          var newSwimlane = evt.to.dataset.swimlaneId || null;

          var destCardIds = Array.from(evt.to.children).map(function (el) {
            return el.dataset.cardId;
          });

          var srcCardIds = Array.from(evt.from.children).map(function (el) {
            return el.dataset.cardId;
          });

          evt.item.dataset.swimlaneId = newSwimlane;

          // One after another: the sort order only covers cards already in the
          // column, so the card has to be moved first.
          var ensureOk = function (res) {
            if (!res.ok) return res.text().then(function (text) { throw new Error(responseError(text)); });
            return res;
          };
          apiRequest('/update-card-position-manual/', {
            card_id: cardId,
            position: Array.from(evt.to.children).indexOf(evt.item),
            column: newColumnId,
            swimlane_id: newSwimlane
          })
            .then(ensureOk)
            .then(function () {
              return apiRequest('/save-column-sort-order/', {
                column_id: newColumnId,
                card_orders: destCardIds
              }).then(ensureOk);
            })
            .then(function () {
              if (!oldColumnId || oldColumnId === newColumnId) return;
              return apiRequest('/save-column-sort-order/', {
                column_id: oldColumnId,
                card_orders: srcCardIds
              }).then(ensureOk);
            })
            .catch(function (err) {
              showErrorToast("Couldn't save the move", err.message + " Refresh the page to see the saved order.");
            });
        }
      });
    });
  };
})();

window.initSortables = initSortables;

document.addEventListener('DOMContentLoaded', function () {
  initSortables();
  updateSwimlaneGridLayout();

  var addSwimlaneBtn = document.getElementById('addSwimlaneBtn');

  addSwimlaneBtn?.addEventListener('click', function () {
    showModal(document.getElementById('addSwimlaneModal'));
  });

  document.getElementById('addSwimlaneForm')
    .addEventListener('submit', function (e) {
      e.preventDefault();
      var boardId = location.pathname.split('/')[2];
      var name = e.target.swimlaneName.value.trim();
      var count = document.querySelectorAll('.swimlane-row').length;
      var maxSwimlanes = boardLimit('Swimlanes');
      if (count >= maxSwimlanes) return alert('Maximum of ' + maxSwimlanes + ' swimlanes allowed per board');

      var submitBtn = e.target.querySelector('button[type="submit"]');
      var originalText = submitBtn.textContent;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';

      apiRequest('/add-swimlane/', { board_id: boardId, name: name })
        .then(function (res) {
          if (!res.ok) return res.text().then(function (text) { throw new Error(responseError(text)); });
          return res.json();
        })
        .then(function (data) {
          var swimlane = data.swimlane;
          bootstrap.Modal.getInstance(document.getElementById('addSwimlaneModal')).hide();

          var swimlaneRow = document.createElement('div');
          swimlaneRow.className = 'swimlane-row';
          swimlaneRow.dataset.swimlaneId = swimlane.id;

          var safeName = escapeHtml(swimlane.name);
          var swimlaneHeader =
            '<div class="swimlane-header">' +
            '<span class="swimlane-name">' + safeName + '</span>' +
            '<div class="swimlane-actions">' +
            '<button title="Delete swimlane" class="delete-swimlane-btn" ' +
            'data-swimlane-id="' + swimlane.id + '" data-swimlane-name="' + safeName + '">' +
            '<i class="bi bi-trash"></i></button></div></div>';

          var columns = document.querySelectorAll('.column-header');
          var cardCells = '';
          columns.forEach(function (column) {
            var columnId = column.dataset.columnId;
            var columnColor = column.dataset.columnColor;
            cardCells +=
              '<div class="board-cell" data-column-id="' + columnId + '" data-swimlane-id="' + swimlane.id + '"' +
              ' data-column-color="' + (columnColor || '') + '">' +
              '<ul class="card-list" data-column-id="' + columnId + '" data-swimlane-id="' + swimlane.id + '"></ul></div>';
          });

          swimlaneRow.innerHTML = swimlaneHeader + cardCells;
          document.querySelector('.kanban-board').appendChild(swimlaneRow);
          requestAnimationFrame(function () { updateSwimlaneGridLayout(); });

          var kanbanBoard = document.querySelector('.kanban-board');
          kanbanBoard.dataset.columns = columns.length;

          var cardSwimlaneSelect = document.querySelector('#cardSwimlane');
          if (cardSwimlaneSelect) {
            cardSwimlaneSelect.insertAdjacentHTML('beforeend',
              '<option value="' + swimlane.id + '">' + safeName + '</option>');
          }

          initSortables();
          e.target.reset();

          if (typeof updateButtonStates === 'function') updateButtonStates();
        })
        .catch(function (err) {
          alert(err.message || 'Failed to add swimlane. Please try again.');
        })
        .finally(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
        });
    });

  document.querySelector('.kanban-board').addEventListener('click', function (e) {
    var swimlaneNameEl = e.target.closest('.swimlane-name');
    var delBtn = e.target.closest('.swimlane-actions .delete-swimlane-btn');

    if (swimlaneNameEl) {
      var swimlaneRow = swimlaneNameEl.closest('.swimlane-row');
      var currentName = swimlaneNameEl.textContent.trim();
      swimlaneNameEl.innerHTML = '<input type="text" class="swimlane-name-input form-control form-control-sm" value="' + escapeHtml(currentName) + '">';
      var input = swimlaneNameEl.querySelector('input');
      input.focus();
      input.select();

      var saveSwimlaneName = function () {
        var newName = input.value.trim();
        if (newName && newName !== currentName) {
          var swimlaneId = swimlaneRow.dataset.swimlaneId;
          apiRequest('/update-swimlane-name/' + swimlaneId + '/', { name: newName })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              swimlaneNameEl.textContent = data.name;
              var selectOption = document.querySelector('#cardSwimlane option[value="' + swimlaneId + '"]');
              if (selectOption) selectOption.textContent = data.name;
              var deleteBtn = swimlaneRow.querySelector('.delete-swimlane-btn');
              if (deleteBtn) deleteBtn.dataset.swimlaneName = data.name;
            })
            .catch(function () {
              swimlaneNameEl.textContent = currentName;
            });
        } else {
          swimlaneNameEl.textContent = currentName;
        }
      };

      input.addEventListener('blur', saveSwimlaneName, { once: true });
      input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') input.blur();
        if (ev.key === 'Escape') swimlaneNameEl.textContent = currentName;
      });
      return;
    }

    if (delBtn) {
      var swimlaneId = delBtn.dataset.swimlaneId;
      var swimlaneName = delBtn.dataset.swimlaneName;

      document.getElementById('deleteSwimlaneNameDisplay').textContent = swimlaneName;
      var confirmBtn = document.getElementById('confirmDeleteSwimlane');
      confirmBtn.dataset.swimlaneId = swimlaneId;
      confirmBtn.dataset.swimlaneName = swimlaneName;

      showModal(document.getElementById('deleteSwimlaneModal'));
    }
  });

  document.getElementById('confirmDeleteSwimlane').addEventListener('click', function () {
    var self = this;
    var swimlaneId = self.dataset.swimlaneId;
    var originalContent = self.innerHTML;

    self.disabled = true;
    self.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Deleting...';

    var cancelBtn = document.querySelector('#deleteSwimlaneModal .btn-outline-secondary');
    var originalCancelState = cancelBtn?.disabled ?? false;

    if (cancelBtn) cancelBtn.disabled = true;

    apiRequest('/delete-swimlane/' + swimlaneId + '/', {})
      .then(function (res) {
        if (!res.ok) return res.text().then(function (text) { throw new Error(responseError(text)); });
        return res.json();
      })
      .then(function () {
        var swimlaneRow = document.querySelector('.swimlane-row[data-swimlane-id="' + swimlaneId + '"]');
        if (swimlaneRow) {
          swimlaneRow.remove();
          updateSwimlaneGridLayout();
        }
        if (typeof updateButtonStates === 'function') updateButtonStates();

        bootstrap.Modal.getInstance(document.getElementById('deleteSwimlaneModal')).hide();
      })
      .catch(function (err) {
        alert(err.message || 'Failed to delete swimlane. Please try again.');
      })
      .finally(function () {
        self.disabled = false;
        self.innerHTML = originalContent;

        if (cancelBtn) cancelBtn.disabled = originalCancelState;
      });
  });
});

var SWIMLANE_FILL_THRESHOLD = 3;

function updateSwimlaneGridLayout() {
  var kanbanBoard = document.querySelector('.kanban-board');
  if (!kanbanBoard) return;

  var count = document.querySelectorAll('.swimlane-row').length;
  kanbanBoard.dataset.swimlanes = count;

  var minH = getComputedStyle(document.documentElement)
    .getPropertyValue('--swimlane-min-height').trim() || '120px';

  if (count > 0 && count <= SWIMLANE_FILL_THRESHOLD) {
    var wrapper = document.querySelector('.board-wrapper');
    var boardTop = kanbanBoard.getBoundingClientRect().top + window.scrollY;
    var wrapperPadBottom = wrapper ? parseFloat(getComputedStyle(wrapper).paddingBottom) : 0;
    // The wrapper's horizontal scrollbar (shown when columns overflow) sits
    // below the board; leave room for it, and floor so sub-pixel offsets
    // can't push the page a pixel past the viewport.
    var scrollbarH = wrapper ? wrapper.offsetHeight - wrapper.clientHeight : 0;
    var viewportH = document.documentElement.clientHeight;
    var availableH = Math.max(
      Math.floor(viewportH - boardTop - wrapperPadBottom - scrollbarH),
      count * parseInt(minH, 10)
    );
    kanbanBoard.style.height = availableH + 'px';
    kanbanBoard.style.gridTemplateRows = 'min-content repeat(' + count + ', 1fr)';
    kanbanBoard.classList.add('kanban-board--fill');
  } else if (count > SWIMLANE_FILL_THRESHOLD) {
    kanbanBoard.style.height = '';
    kanbanBoard.style.gridTemplateRows =
      'min-content repeat(' + count + ', minmax(' + minH + ', auto))';
    kanbanBoard.classList.remove('kanban-board--fill');
  } else {
    kanbanBoard.style.height = '';
    kanbanBoard.style.gridTemplateRows = 'min-content auto';
    kanbanBoard.classList.remove('kanban-board--fill');
  }

  document.querySelectorAll('.delete-swimlane-btn').forEach(function (btn) {
    btn.style.display = count > 1 ? '' : 'none';
  });

  document.dispatchEvent(new CustomEvent('boardLayoutChanged', {
    detail: { swimlaneCount: count }
  }));

  if (typeof updateButtonStates === 'function') updateButtonStates();
}

window.addEventListener('resize', function () {
  var count = document.querySelectorAll('.swimlane-row').length;
  if (count > 0 && count <= SWIMLANE_FILL_THRESHOLD) updateSwimlaneGridLayout();
});