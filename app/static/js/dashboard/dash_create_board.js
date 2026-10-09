
import { getCsrfToken, responseError, validateBoardForm, setButtonLoading, showFormErrors } from './dash_utils.js';
import { addBoardToGrid } from './dash_grid.js';


export function openCreateBoardModal() {
  const createBoardBtn = document.getElementById('createBoardBtn');
  const createBoardModalEl = document.getElementById('createBoardModal');

  if (!createBoardBtn || !createBoardModalEl) return;

  const createBoardModal = bootstrap.Modal.getOrCreateInstance(createBoardModalEl);

  const cleanupBackdrops = () => {
    if (!document.querySelector('.modal.show')) {
      document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
      document.body.classList.remove('modal-open');
      document.body.style.removeProperty('padding-right');
    }
  };

  createBoardModalEl.addEventListener('hidden.bs.modal', cleanupBackdrops);

  const dashboardContainer = createBoardBtn.closest('.dashboard-container');
  if (!dashboardContainer) return;

  const form = document.getElementById('createBoardForm');
  form?.reset();
  $('.invalid-feedback').hide();
  $('.form-control').removeClass('is-invalid');

  createBoardModal.show();
  return;
}


    

export function handleCreateBoard(e) {
    e.preventDefault();
    
    const $form = $(this);
    const $submitBtn = $('#createBoardSubmit');
    const formData = {
        name: $('#boardName').val().trim(),
        description: $('#boardDescription').val().trim()
    };
    
    if (!validateBoardForm(formData)) {
        return;
    }
    
    setButtonLoading($submitBtn, true);
    
    $.ajax({
        url: '/boards/create/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        headers: { 'X-CSRFToken': getCsrfToken() },
        success: function(data) {
            $('#createBoardModal').modal('hide');
            
            setTimeout(() => {
            if (!$('.modal.show').length) {
                $('body').removeClass('modal-open').css('padding-right', '');
                $('.modal-backdrop').remove();
            }
            }, 250);

            addBoardToGrid(data.board);
        },
        error: function(xhr) {
            const message = responseError(xhr, 'Failed to create board');
            showFormErrors($form, { message });
        },
        complete: function() {
            setButtonLoading($submitBtn, false);
        }
    });
}