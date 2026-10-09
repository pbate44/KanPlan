
import { updateEmptyState } from './dash_grid.js';

export function initializeSearchAndFilter() {
    const initialSort = localStorage.getItem('boardSort') || 'updated';
    $(`input[name="sortBy"][value="${initialSort}"]`).prop('checked', true);
    handleSort();
}

export function handleSearch() {
    const searchTerm = $('#boardSearch').val().toLowerCase();
    
    $('.board-tile').each(function() {
        const $tile = $(this);
        const boardName = $tile.find('.board-title').text().toLowerCase();
        const boardDescription = $tile.find('.board-description').text().toLowerCase();
        const matches = boardName.includes(searchTerm) || boardDescription.includes(searchTerm);
        $tile.toggle(matches);
    });
    updateEmptyState();
}

export function handleSort() {
    const sortBy = $('input[name="sortBy"]:checked').val();
    localStorage.setItem('boardSort', sortBy);
    const $grid = $('#boardsGrid');
    const $tiles = $('.board-tile').detach();
    $tiles.sort(function(a, b) {
        const $a = $(a);
        const $b = $(b);
        switch (sortBy) {
            case 'name':
                return $a.find('.board-title').text().localeCompare($b.find('.board-title').text());
            case 'created':
                return new Date($b.data('created')) - new Date($a.data('created'));
            case 'updated':
            default:
                return new Date($b.data('updated')) - new Date($a.data('updated'));
        }
    });
    
    $grid.append($tiles);
}