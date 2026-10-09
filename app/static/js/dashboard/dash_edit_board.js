
import { getCsrfToken, responseError, formatDate, validateBoardForm, setButtonLoading, showFormErrors } from './dash_utils.js';
import { updateBoardInGrid } from './dash_grid.js';

export function openEditBoardModal(boardId, boardName, boardDescription) {
    $('#editBoardId').val(boardId);
    $('#editBoardName').val(boardName);
    $('#editBoardDescription').val(boardDescription);
    $('.invalid-feedback').hide();
    $('.form-control').removeClass('is-invalid');
    loadBoardStatistics(boardId);
    $('#editBoardModal').modal('show');
}

export function loadBoardStatistics(boardId) {
    $.ajax({
        url: `/boards/${boardId}/details/`,
        method: 'GET',
        headers: { 'X-CSRFToken': getCsrfToken() },
        success: function(data) {
            const board = data.board;
            $('#boardCardCount').text(board.card_count || '-');
            $('#boardColumnCount').text(board.column_count || '-');
            $('#boardCreatedDate').text(formatDate(board.created_at));
        },
        error: function() {
            $('#boardCardCount, #boardColumnCount, #boardCreatedDate').text('-');
        }
    });
}

export function handleEditBoard(e) {
    e.preventDefault();
    const $form = $(this);
    const $submitBtn = $('#editBoardSubmit');
    const boardId = $('#editBoardId').val();
    const formData = {
        name: $('#editBoardName').val().trim(),
        description: $('#editBoardDescription').val().trim()
    };
    
    if (!validateBoardForm(formData)) {
        return;
    }
    
    setButtonLoading($submitBtn, true);
    
    $.ajax({
        url: `/boards/${boardId}/update/`,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        headers: { 'X-CSRFToken': getCsrfToken() },
        success: function(data) {
            $('#editBoardModal').modal('hide');
            updateBoardInGrid(data.board);
        },

        error: function(xhr) {
            const message = responseError(xhr, 'Failed to update board');
            showFormErrors($form, { message });
        },
        
        complete: function() {
            setButtonLoading($submitBtn, false);
        }
    });
}