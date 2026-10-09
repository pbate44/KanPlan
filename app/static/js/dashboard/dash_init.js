import * as create from "./dash_create_board.js";
import * as del from "./dash_delete_board.js";
import * as dragdrop from "./dash_drag_drop.js";
import * as edits from "./dash_edit_board.js";
import * as grid from "./dash_grid.js";
import * as imgs from "./dash_img_upload.js";
import * as searchs from "./dash_searchfilt.js";
import * as utils from "./dash_utils.js";

document.addEventListener('DOMContentLoaded', function() {
    utils.DashboardLoader.init();
    utils.DashboardLoader.setStepComplete('domReady');
    initializeDashboard();
});


function initializeDashboard() {
    setupEventListeners();
    searchs.initializeSearchAndFilter();
    utils.loadUserPreferences();
    utils.checkImagesLoaded();
    utils.DashboardLoader.setStepComplete('jsInitialized');
}

function setupEventListeners() {
    
    $(document).on('click', '#createBoardBtn, #createFirstBoardBtn', function() {
        create.openCreateBoardModal();
    });
    
    $(document).on('click', '.edit-board-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const boardId = $(this).data('board-id');
        const boardName = $(this).data('board-name');
        const boardDescription = $(this).data('board-description');
        edits.openEditBoardModal(boardId, boardName, boardDescription);
    });
    
    $(document).on('click', '.delete-board-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const boardId = $(this).data('board-id');
        const boardName = $(this).data('board-name');
        del.openDeleteBoardModal(boardId, boardName);
    });
    
    $(document).on('click', '.upload-image-btn', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const boardId = $(this).data('board-id');
        imgs.openUploadImageModal(boardId);
    });
    
    $(document).on('click', '.remove-image-btn', function(e) { // Remove image button
        e.preventDefault();
        e.stopPropagation();
        const boardId = $(this).data('board-id');
        imgs.removeBoardImage(boardId);
    });

    $(document).on('submit', '#createBoardForm', create.handleCreateBoard);
    $(document).on('submit', '#editBoardForm', edits.handleEditBoard);
    $(document).on('submit', '#uploadImageForm', imgs.handleImageUpload);
    $(document).on('click', '#confirmDeleteBoard', del.handleDeleteBoard);
    $(document).on('input', '#boardSearch', utils.debounce(searchs.handleSearch, 300));
    $(document).on('change', 'input[name="sortBy"]', searchs.handleSort);
    $(document).on('change', '#imageFile', imgs.handleImageFileSelect);
    $(document).on('click', '#uploadArea', function() {
        $('#imageFile')[0].click();
    });
    $(document).on('click', '#removePreview', imgs.removeImagePreview);
    $(document).on('input', '#deleteConfirmInput', del.validateDeleteConfirmation);
    dragdrop.setupDragAndDrop();
}