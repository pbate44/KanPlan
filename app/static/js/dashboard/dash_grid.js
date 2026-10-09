
import { createBoardTileHtml } from './dash_utils.js';

export function addBoardToGrid(board) {
    const tileHtml = createBoardTileHtml(board);
    if ($('.board-tile').length === 0) {
        $('.empty-state').remove();
    }
    $('#boardsGrid').prepend(tileHtml);
    $('.board-tile').first().hide().fadeIn(300);
}

export function updateBoardInGrid(board) {
    const $tile = $(`.board-tile[data-board-id="${board.id}"]`);
    $tile.find('.board-title').text(board.name);
    $tile.find('.board-description').text(board.description);
    $tile.find('.edit-board-btn')
        .data('board-name', board.name)
        .data('board-description', board.description);
}

export function updateBoardImageInGrid(boardId, imageUrl) {
    const $tile = $(`.board-tile[data-board-id="${boardId}"]`);
    const $container = $tile.find('.board-image-container');
    
    if (imageUrl) {
        var $img = $('<img class="board-image" alt="Board Image">').attr('src', imageUrl);
        $container.empty().append($img, $('<div class="board-image-overlay"></div>'));
        const $menu = $tile.find('.dropdown-menu');
        if (!$menu.find('.remove-image-btn').length) {
            $menu.find('.upload-image-btn').after(`
                <li>
                    <a class="dropdown-item remove-image-btn" href="#" data-board-id="${boardId}">
                        <i class="bi bi-image-alt me-2"></i>Remove Image
                    </a>
                </li>
            `);
        }
    } else {
        $container.html(`
            <div class="board-image-placeholder">
                <i class="bi bi-kanban"></i>
            </div>
            <div class="board-image-overlay"></div>
        `);
        $tile.find('.remove-image-btn').parent().remove();
    }
}

export function removeBoardFromGrid(boardId) {
    const $tile = $(`.board-tile[data-board-id="${boardId}"]`);
    $tile.fadeOut(300, function() {
        $(this).remove();
        updateEmptyState();
    });
}

export function updateEmptyState() {
    const visibleTiles = $('.board-tile:visible').length;
    // Tiles that exist but are hidden mean the search matched nothing.
    const filtered = $('.board-tile').length > 0;

    $('.empty-state').remove();
    if (visibleTiles > 0) return;

    $('#boardsGrid').append(filtered ? `
        <div class="empty-state">
            <div class="empty-state-icon"><i class="bi bi-search" aria-hidden="true"></i></div>
            <h3>No boards found</h3>
            <p>Try adjusting your search</p>
        </div>
    ` : `
        <div class="empty-state">
            <div class="empty-state-icon"><i class="bi bi-kanban" aria-hidden="true"></i></div>
            <h3>No boards yet</h3>
            <p>Create your first board to get started with KanPlan</p>
            <button type="button" class="create-first-board" id="createFirstBoardBtn">
                <i class="bi bi-plus-circle"></i>Create Your First Board
            </button>
        </div>
    `);
}
