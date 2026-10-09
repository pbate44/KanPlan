
import { getCsrfToken, responseError, setButtonLoading, showToast, formatFileSize } from './dash_utils.js';
import { updateBoardImageInGrid } from './dash_grid.js';

export function openUploadImageModal(boardId) {
    $('#uploadBoardId').val(boardId);
    $('#uploadImageForm')[0].reset();
    $('#imagePreview').addClass('d-none');
    $('#uploadArea').removeClass('d-none');
    $('#uploadImageSubmit').prop('disabled', true);
    $('#uploadImageModal').modal('show');
}

export function handleImageFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        validateAndPreviewImage(file);
    }
}

export function validateAndPreviewImage(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        showToast('error', 'Invalid file type. Please upload a JPEG, PNG, GIF, or WebP image.');
        return;
    }
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('error', 'File size too large. Maximum size is 5MB.');
        return;
    }
    const reader = new FileReader();
    reader.onload = function(e) {
        $('#previewImage').attr('src', e.target.result); 
        $('#fileName').text(file.name);
        $('#fileSize').text(formatFileSize(file.size)); 
        $('#uploadArea').addClass('d-none');
        $('#imagePreview').removeClass('d-none');
        $('#uploadImageSubmit').prop('disabled', false);
        };
    reader.readAsDataURL(file);
}

export function removeImagePreview() {
    $('#imageFile').val('');
    $('#imagePreview').addClass('d-none');
    $('#uploadArea').removeClass('d-none');
    $('#uploadImageSubmit').prop('disabled', true);
}

export function handleImageUpload(e) {
    e.preventDefault();
    
    const $form = $(this);
    const $submitBtn = $('#uploadImageSubmit');
    const boardId = $('#uploadBoardId').val();
    const formData = new FormData();
    const imageFile = $('#imageFile')[0].files[0];
    
    if (!imageFile) {
        showToast('error', 'Please select an image file.');
        return;
    }
    
    formData.append('image', imageFile);
    
    setButtonLoading($submitBtn, true);
    showUploadProgress(true);
    
    $.ajax({
        url: `/boards/${boardId}/upload-image/`,
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        headers: { 'X-CSRFToken': getCsrfToken() },

        xhr: function() {
            const xhr = new window.XMLHttpRequest();
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    updateUploadProgress(percentComplete);
                }
            });
            return xhr;
        },

        success: function(data) {
            $('#uploadImageModal').modal('hide');
            updateBoardImageInGrid(boardId, data.image_url);
        },

        error: function(xhr) {
            const message = responseError(xhr, 'Failed to upload image');
            showToast('error', message);
        },

        complete: function() {
            setButtonLoading($submitBtn, false);
            showUploadProgress(false);
        }
    });
}

export function showUploadProgress(show) {
    if (show) {
        $('#uploadProgress').removeClass('d-none');
        $('.progress-bar').css('width', '0%');
    } else {
        $('#uploadProgress').addClass('d-none');
    }
}

export function updateUploadProgress(percent) {
    $('.progress-bar').css('width', percent + '%');
}

export function removeBoardImage(boardId) {
    
    $.ajax({
        url: `/boards/${boardId}/remove-image/`,
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },

        success: function(data) {
            updateBoardImageInGrid(boardId, null);
        },

        error: function(xhr) {
            const message = responseError(xhr, 'Failed to remove image');
            showToast('error', message);
        }
    });
}