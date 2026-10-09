
let isLoadingAttachments = false;

function loadAttachments(cardId) {
  if (isLoadingAttachments) {
    return;
  }
  
  isLoadingAttachments = true;
  
  $.ajax({
    url: `/cards/${cardId}/attachments/`,
    method: 'GET',
    success: function(response) {
      const attachments = response.attachments;
      const $attachmentsList = $('#attachmentsList');
      const $attachmentsSection = $('#attachmentsSection');

      $attachmentsList.empty();

      if (attachments.length === 0) {
        $attachmentsSection.addClass('d-none');
        isLoadingAttachments = false;
        return;
      }

      $attachmentsSection.removeClass('d-none');
      
      attachments.forEach(attachment => {
        const safeFilename = escapeHtml(attachment.filename);
        const safeIconClass = escapeHtml(attachment.icon_class);
        const attachmentHtml = `
          <div class="attachment-card" data-attachment-id="${attachment.id}">
            <div class="attachment-icon">
              <i class="bi ${safeIconClass}"></i>
            </div>
            <div class="attachment-info">
              <div class="attachment-name" title="${safeFilename}">${safeFilename}</div>
              <div class="attachment-meta small">${formatFileSize(attachment.file_size)}</div>
            </div>
            <div class="attachment-actions">
              <a href="/attachments/${attachment.id}/view/" target="_blank" class="btn btn-xs btn-outline-primary" title="View file">
                <i class="bi bi-eye"></i>
              </a>
            </div>
          </div>
        `;
        $attachmentsList.append(attachmentHtml);
      });
      
      isLoadingAttachments = false;
    },
    error: function(xhr) {
      console.error('Error loading attachments:', xhr.responseText);
      isLoadingAttachments = false;
    }
  });
}

$(document).on('click', '#uploadAttachmentBtn', function () {
  const cardId = $(this).data('card-id');

  $('#fileUploadForm').data('card-id', cardId);
  $('#fileInput').val('');
  $('#uploadProgressContainer').addClass('d-none');
  $('#uploadProgressBar').css('width', '0%');

  const attachModalEl = document.getElementById('attachmentModal');
  document.body.appendChild(attachModalEl);
  bootstrap.Modal.getOrCreateInstance(attachModalEl, {backdrop: false}).show();
});

$(document).on('change', '#fileInput', function() {
  $('#startUploadBtn').prop('disabled', $(this)[0].files.length === 0);
});

$(document).on('hidden.bs.modal', '#attachmentModal', function() {
  $('#startUploadBtn').prop('disabled', true);
  $('#fileInput').val('');

  if ($('#cardDetailModal').hasClass('show')) {
    if (!$('.modal-backdrop').length) {
      $('body').append('<div class="modal-backdrop fade show"></div>');
    }
  }

  if (this.parentNode === document.body) {
    var inst = bootstrap.Modal.getInstance(this);
    if (inst) inst.dispose();
    // Return it to the card content so it can be opened again.
    var content = document.getElementById('cardDetailContent');
    if (content && $('#cardDetailModal').hasClass('show')) {
      content.appendChild(this);
    } else {
      this.remove();
    }
  }
});

let isUploading = false

$(document).on('click', '#startUploadBtn', function() {
  const $button = $(this);
  const files = $('#fileInput')[0].files;
  const cardId = $('#fileUploadForm').data('card-id');
  
  isUploading = true;
  $button.prop('disabled', true).text('Uploading...');
  
  $('#uploadProgressContainer').removeClass('d-none');

  const totalFiles = files.length;
  let completedFiles = 0;

  const uploadedFiles = new Set();
  
  Array.from(files).forEach((file, index) => {
    const fileId = `${file.name}_${file.size}_${file.lastModified}`;
    
    if (uploadedFiles.has(fileId)) {
      completedFiles++;
      return;
    }
    
    uploadedFiles.add(fileId);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    $.ajax({
      url: `/cards/${cardId}/attachments/upload/`,
      method: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      xhr: function() {
        const xhr = new window.XMLHttpRequest();
        xhr.upload.addEventListener('progress', function(e) {
          if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            $('#uploadProgressBar').css('width', percentComplete + '%');
          }
        }, false);
        return xhr;
      },
      success: function() {
        completedFiles++;
        const totalProgress = (completedFiles / totalFiles) * 100;
        $('#uploadProgressBar').css('width', totalProgress + '%');
        
        if (completedFiles === totalFiles) {
          setTimeout(function() {
            const attachmentModalEl = document.getElementById('attachmentModal');
            bootstrap.Modal.getOrCreateInstance(attachmentModalEl).hide();
            loadAttachments(cardId);
            
            $button.prop('disabled', false).html('<i class="bi bi-upload me-2"></i>Upload Files');
            isUploading = false;
            
            $('#fileInput').val('');
            $('#startUploadBtn').prop('disabled', true);
            $('#uploadProgressContainer').addClass('d-none');
          }, 500);
        }
      },
      error: function(xhr) {
        completedFiles++;

        if (completedFiles === totalFiles) {
          bootstrap.Modal.getOrCreateInstance(document.getElementById('attachmentModal')).hide();

          const errMsg = responseError(xhr, 'Failed to upload "' + file.name + '". Please try again.');
          showErrorToast('Upload failed', errMsg);

          $button.prop('disabled', false).html('<i class="bi bi-upload me-2"></i>Upload Files');
          isUploading = false;
          $('#fileInput').val('');
          $('#startUploadBtn').prop('disabled', true);
          $('#uploadProgressContainer').addClass('d-none');
          $('#uploadProgressBar').css('width', '0%');
        }
      }
    });
  });
});

$(document).on('click', '#confirmDeleteBtn', function() {
  const attachmentId = $(this).data('attachment-id');
  const cardId = $(this).data('card-id');
  const $button = $(this);
  
  $button.prop('disabled', true).html('<i class="bi bi-hourglass-split me-1"></i>Deleting...');
  
  $.ajax({
    url: `/attachments/${attachmentId}/delete/`,
    method: 'POST',
    headers: {
      'X-CSRFToken': getCsrfToken()
    },
    success: function() {
      $('#deleteAttachmentModal').modal('hide');
      loadAttachments(cardId);
    },
    error: function(xhr) {
      console.error('Error deleting attachment:', xhr.responseText);
    },
    complete: function() {
      $button.prop('disabled', false).html('<i class="bi bi-trash me-1"></i>Yes, Delete');
    }
  });
});

$(document).on('shown.bs.modal', '#cardDetailModal', function() {
  const cardId = $('.card-detail-container').data('card-id');
  if (cardId) {
    loadAttachments(cardId);
  }
});

$(document).on('contextmenu', '.attachment-card', function(e) {
  e.preventDefault();
  
  const attachmentId = $(this).data('attachment-id');
  const filename = $(this).find('.attachment-name').attr('title') || $(this).find('.attachment-name').text();
  
  $('.attachment-context-menu').remove();
  
  const contextMenu = $(`
    <div class="attachment-context-menu" data-attachment-id="${attachmentId}">
      <div class="context-menu-item view-attachment">
        <i class="bi bi-eye me-2"></i>View File
      </div>
      <div class="context-menu-item delete-attachment-context">
        <i class="bi bi-trash me-2"></i>Delete File
      </div>
    </div>
  `);
  
  contextMenu.css({
    position: 'fixed',
    left: e.clientX + 'px',
    top: e.clientY + 'px',
    zIndex: 9999
  });
  
  $('body').append(contextMenu);
  contextMenu.data('filename', filename);
  contextMenu.fadeIn(150);
});

$(document).on('click', function(e) {
  if (!$(e.target).closest('.attachment-context-menu').length) {
    $('.attachment-context-menu').fadeOut(100, function() {
      $(this).remove();
    });
  }
});

$(document).on('click', '.view-attachment', function() {
  const attachmentId = $(this).closest('.attachment-context-menu').data('attachment-id');
  window.open(`/attachments/${attachmentId}/view/`, '_blank');
  $('.attachment-context-menu').remove();
});

$(document).on('click', '.delete-attachment-context', function() {
  const $contextMenu = $(this).closest('.attachment-context-menu');
  const attachmentId = $contextMenu.data('attachment-id');
  const filename = $contextMenu.data('filename');
  const cardId = $('.card-detail-container').data('card-id');
  
  $contextMenu.remove();

  $('#fileToDelete .filename').text(filename);
  $('#confirmDeleteBtn').data('attachment-id', attachmentId).data('card-id', cardId);
  
  const delModalEl = document.getElementById('deleteAttachmentModal');
  document.body.appendChild(delModalEl);
  bootstrap.Modal.getOrCreateInstance(delModalEl, {backdrop: false}).show();
});

$(document).on('hidden.bs.modal', '#deleteAttachmentModal', function() {
  if ($('#cardDetailModal').hasClass('show')) {
    if (!$('.modal-backdrop').length) {
      $('body').append('<div class="modal-backdrop fade show"></div>');
    }
  }

  if (this.parentNode === document.body) {
    var inst = bootstrap.Modal.getInstance(this);
    if (inst) inst.dispose();
    // Return it to the card content so it can be opened again.
    var content = document.getElementById('cardDetailContent');
    if (content && $('#cardDetailModal').hasClass('show')) {
      content.appendChild(this);
    } else {
      this.remove();
    }
  }
});