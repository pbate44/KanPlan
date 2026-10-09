
import { validateAndPreviewImage } from './dash_img_upload.js';

export function setupDragAndDrop() {
    const $uploadArea = $('#uploadArea');
    
    $uploadArea.on('dragover dragenter', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).addClass('dragover');
    });
    
    $uploadArea.on('dragleave dragend', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).removeClass('dragover');
    });
    
    $uploadArea.on('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).removeClass('dragover');
        
        const files = e.originalEvent.dataTransfer.files;
        if (files.length > 0) {
            const file = files[0];
            if (file.type.startsWith('image/')) {
                validateAndPreviewImage(file);
                const dt = new DataTransfer();
                dt.items.add(file);
                $('#imageFile')[0].files = dt.files;
            }
        }
    });
}