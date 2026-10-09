// Shared helpers come from utilities/common.js, loaded globally by base.html.
export const { escapeHtml, formatFileSize, debounce, getCsrfToken, responseError } = window;

export function showToast(type, message) {
    return window.showToast(type, '', message, 4000);
}


export function validateBoardForm(data) {
    let isValid = true;

    $('.form-control').removeClass('is-invalid');
    $('.invalid-feedback').hide();

    if (!data.name || data.name.length < 1) {
        $('#boardName, #editBoardName').addClass('is-invalid')
            .siblings('.invalid-feedback').text('Board name is required.').show();
        isValid = false;
    } else if (data.name.length > 100) {
        $('#boardName, #editBoardName').addClass('is-invalid')
            .siblings('.invalid-feedback').text('Board name must be less than 100 characters.').show();
        isValid = false;
    }
    
    return isValid;
}

export function showFormErrors($form, errors) {
    $('.form-control').removeClass('is-invalid');
    $('.invalid-feedback').hide();
    
    // Errors that aren't about one field (e.g. the board limit) show under the name.
    const nameError = errors.name || errors.message;
    if (nameError) {
        $form.find('input[name="name"]').addClass('is-invalid')
            .siblings('.invalid-feedback').text(nameError).show();
    }
    
    if (errors.description) {
        $form.find('textarea[name="description"]').addClass('is-invalid')
            .siblings('.invalid-feedback').text(errors.description).show();
    }
}

export function setButtonLoading($button, loading) {
    if (loading) {
        $button.prop('disabled', true);
        $button.find('.btn-text').addClass('d-none');
        $button.find('.btn-loading').removeClass('d-none');
    } else {
        $button.prop('disabled', false);
        $button.find('.btn-text').removeClass('d-none');
        $button.find('.btn-loading').addClass('d-none');
    }
}

export function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString();
}


export function loadUserPreferences() {
    const savedSort = localStorage.getItem('boardSort');
    if (savedSort) {
        $(`input[name="sortBy"][value="${savedSort}"]`).prop('checked', true);
    }
}

export function createBoardTileHtml(board) {
    const updatedAt = board.updated_at || board.created_at || new Date().toISOString();
    const createdAt = board.created_at || new Date().toISOString();

    const description = board.description ? 
        (board.description.length > 100 ? 
            board.description.substring(0, 97) + '...' : 
            board.description) : '';

    const timeAgo = formatTimeAgo(updatedAt);

    const imageHtml = board.image_url ? 
        `<img src="${board.image_url}" alt="${escapeHtml(board.name)}" class="board-image">` :
        `<div class="board-image-placeholder"><i class="bi bi-kanban"></i></div>`;

    const descriptionHtml = description ? 
        `<p class="board-description">${escapeHtml(description)}</p>` : '';

    const removeImageOption = board.image_url ? 
        `<li>
            <a class="dropdown-item remove-image-btn" href="#" data-board-id="${board.id}">
                <i class="bi bi-image-alt me-2"></i>Remove Image
            </a>
        </li>` : '';

    const escapedName = escapeHtml(board.name);
    const escapedDescription = escapeHtml(board.description || '');
    
    return `
    <div class="board-tile" data-board-id="${board.id}" data-created="${createdAt}" data-updated="${updatedAt}">
        <div class="board-tile-content">
            <!-- Board Image -->
            <div class="board-image-container">
                ${imageHtml}
                <div class="board-image-overlay"></div>
            </div>

            <!-- Board Info -->
            <div class="board-info">
                <h3 class="board-title">${escapedName}</h3>
                ${descriptionHtml}
                <div class="board-meta">
                    <small class="text-muted">
                        <i class="bi bi-clock me-1"></i>
                        Updated ${timeAgo}
                    </small>
                </div>
            </div>

            <!-- Board Actions -->
            <div class="board-actions">
                <div class="dashboard-dropdown dropdown">
                    <button class="btn btn-sm btn-outline-light board-menu-btn" type="button" 
                            data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="bi bi-three-dots"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end dashboard-edit">
                        <li>
                            <a class="dropdown-item edit-board-btn" href="#" 
                                data-board-id="${board.id}"
                                data-board-name="${escapedName}"
                                data-board-description="${escapedDescription}">
                                <i class="bi bi-pencil me-2"></i>Edit Board
                            </a>
                        </li>
                        <li>
                            <a class="dropdown-item upload-image-btn" href="#" 
                                data-board-id="${board.id}">
                                <i class="bi bi-image me-2"></i>Change Image
                            </a>
                        </li>
                        ${removeImageOption}
                        <li><hr class="dropdown-divider"></li>
                        <li>
                            <a class="dropdown-item text-danger delete-board-btn" href="#" 
                                data-board-id="${board.id}"
                                data-board-name="${escapedName}">
                                <i class="bi bi-trash me-2"></i>Delete Board
                            </a>
                        </li>
                    </ul>
                </div>
            </div>

            <!-- Click Overlay for Navigation -->
            <a href="/board/${board.id}/" class="board-click-overlay"></a>
        </div>
    </div>`;
}

export function formatTimeAgo(dateString) {
    const now = new Date();
    const date = new Date(dateString);
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) {
        return 'just now';
    }
    
    const diffInMinutes = Math.floor(diffInSeconds / 60);
    if (diffInMinutes < 60) {
        return `${diffInMinutes} minute${diffInMinutes === 1 ? '' : 's'} ago`;
    }
    
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) {
        return `${diffInHours} hour${diffInHours === 1 ? '' : 's'} ago`;
    }
    
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 30) {
        return `${diffInDays} day${diffInDays === 1 ? '' : 's'} ago`;
    }
    
    const diffInMonths = Math.floor(diffInDays / 30);
    if (diffInMonths < 12) {
        return `${diffInMonths} month${diffInMonths === 1 ? '' : 's'} ago`;
    }
    
    const diffInYears = Math.floor(diffInMonths / 12);
    return `${diffInYears} year${diffInYears === 1 ? '' : 's'} ago`;
}

export const DashboardLoader = {
    isLoading: true,
    loadingSteps: {
        domReady: false,
        jsInitialized: false,
        imagesLoaded: false
    },

    init() {
        this.showLoader();
        this.setupLoadingChecks();

        setTimeout(() => {
            if (this.isLoading) {
                this.hideLoader();
            }
        }, 10000);
    },

    setupLoadingChecks() {

    },

    showLoader() {

        const userTheme = localStorage.getItem('theme');
        const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (userTheme) {
            document.documentElement.setAttribute('data-bs-theme', userTheme);
        } else if (prefersDarkMode) {
            document.documentElement.setAttribute('data-bs-theme', 'dark');
        }
        
        const loader = document.getElementById('dashboardLoader');
        if (loader) {
            loader.style.display = 'flex';
        }
    },

    hideLoader() {
        const loader = document.getElementById('dashboardLoader');
        if (loader) {
            loader.classList.add('fade-out');
            setTimeout(() => {
                loader.style.display = 'none';
            }, 500);
        }
        this.isLoading = false;
    },

    checkIfAllLoaded() {
        const allLoaded = Object.values(this.loadingSteps).every(step => step);
        if (allLoaded && this.isLoading) {
            this.hideLoader();
        }
    },

    setStepComplete(step) {
        if (this.loadingSteps.hasOwnProperty(step)) {
            this.loadingSteps[step] = true;
            this.checkIfAllLoaded();
        }
    }
};

export function checkImagesLoaded() {
    const images = document.querySelectorAll('.board-image');
    let loadedCount = 0;
    const totalImages = images.length;

    if (totalImages === 0) {
        DashboardLoader.setStepComplete('imagesLoaded');
        return;
    }

    function imageLoaded() {
        loadedCount++;
        if (loadedCount === totalImages) {
            DashboardLoader.setStepComplete('imagesLoaded');
        }
    }

    images.forEach(img => {
        if (img.complete) {
            imageLoaded();
        } else {
            img.addEventListener('load', imageLoaded);
            img.addEventListener('error', imageLoaded);
        }
    });

    setTimeout(() => {
        DashboardLoader.setStepComplete('imagesLoaded');
    }, 5000);
}
