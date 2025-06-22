// Enhanced file uploader with multi-file drag-and-drop support
document.addEventListener('htmx:load', initUploader);
document.addEventListener('DOMContentLoaded', initUploader);

function initUploader() {
    const dropZone = document.getElementById('file-drop-zone');
    if (!dropZone) return; // If no drop zone, do nothing

    // Prevent re-initialization if already done for this dropZone
    if (dropZone.dataset.uploaderInitialized === 'true') {
        console.log('[initUploader] Already initialized for this drop zone. Skipping.');
        return;
    }

    const fileInput = document.getElementById('fileInput');
    const fileTypeInput = document.getElementById('file_type');
    const uploadForm = document.getElementById('upload-form');

    // Only proceed if we have all critical elements for *this specific uploader instance*
    // uploadForm might be null if the dropZone is part of a different form or no form, adjust if needed.
    if (!fileInput || !uploadForm) {
        console.warn('[initUploader] Missing fileInput or uploadForm for a dropZone. Uploader may not fully function.');
        // Depending on requirements, you might still want to initialize parts of it or return.
        // For now, let's assume they are essential for the current logic.
        return; 
    }
    
    console.log('[initUploader] Initializing for drop zone:', dropZone.id);

    // Store multiple files
    let files = [];
    let currentUploadIndex = 0;
    let isUploading = false;

    // Detect file type based on filename
    function detectFileType(file) {
        console.log("[detectFileType] Processing file:", file.name);
        const fileName = file.name.toLowerCase();
        console.log("[detectFileType] Lowercase fileName:", fileName);

        let detectedType = 'am_csv'; // Default type

        if (fileName.endsWith('.txt')) {
            detectedType = 'attout_txt';
            console.log("[detectFileType] Detected as .txt:", detectedType);
        } else if (fileName.endsWith('.csv')) {
            console.log("[detectFileType] Is CSV. Checking PM specific...");
            const isPmSpecific = fileName.includes('_pm') || fileName.includes('pm_') || fileName.includes(' pm.') || fileName.startsWith('pm_');
            console.log(`[detectFileType] - includes('_pm'): ${fileName.includes('_pm')}, includes('pm_'): ${fileName.includes('pm_')}, includes(' pm.'): ${fileName.includes(' pm.')}, startsWith('pm_'): ${fileName.startsWith('pm_')}`);
            console.log("[detectFileType] pmSpecific result:", isPmSpecific);

            if (isPmSpecific) {
                detectedType = 'pm_csv';
            } else {
                console.log("[detectFileType] PM specific false. Checking AM specific...");
                const isAmSpecific = fileName.includes('_am') || fileName.includes('am_') || fileName.includes(' am.') || fileName.startsWith('am_');
                console.log(`[detectFileType] - includes('_am'): ${fileName.includes('_am')}, includes('am_'): ${fileName.includes('am_')}, includes(' am.'): ${fileName.includes(' am.')}, startsWith('am_'): ${fileName.startsWith('am_')}`);
                console.log("[detectFileType] amSpecific result:", isAmSpecific);

                if (isAmSpecific) {
                    detectedType = 'am_csv';
                } else {
                    console.log("[detectFileType] AM specific false. Checking PM general...");
                    const isPmGeneral = fileName.includes('pm');
                    console.log("[detectFileType] pmGeneral result:", isPmGeneral);

                    if (isPmGeneral) {
                        detectedType = 'pm_csv';
                    } else {
                        console.log("[detectFileType] PM general false. Checking AM general...");
                        const isAmGeneral = fileName.includes('am');
                        console.log("[detectFileType] amGeneral result:", isAmGeneral);
                        if (isAmGeneral) {
                            detectedType = 'am_csv';
                        } else {
                            console.log("[detectFileType] No AM/PM CSV indicator, defaulting to am_csv for CSV.");
                            detectedType = 'am_csv'; // Default for CSV
                        }
                    }
                }
            }
            console.log("[detectFileType] CSV detected as:", detectedType);
        } else {
            console.error("[detectFileType] Invalid file type. Only .csv and .txt files are allowed:", file.name);
            return null; // Return null for invalid file types
        }
        console.log("[detectFileType] Final detection for", file.name, "->", detectedType);
        return detectedType;
    }

    // Handle file selection
    function handleFiles(selectedFiles) {
        console.log("[handleFiles] Received selectedFiles count:", selectedFiles.length, selectedFiles);
        if (!selectedFiles || !selectedFiles.length) return;

        // Clear previous batch of files, as uploads are immediate
        files = []; 

        const invalidFiles = [];
        
        Array.from(selectedFiles).forEach(file => {
            const determinedType = detectFileType(file);
            if (determinedType === null) {
                invalidFiles.push(file.name);
            } else {
                files.push({
                    file: file,
                    type: determinedType
                });
            }
        });
        
        // Show error message for invalid files
        if (invalidFiles.length > 0) {
            const errorMessage = `Invalid file type(s): ${invalidFiles.join(', ')}. Only .csv and .txt files are allowed.`;
            alert(errorMessage);
            console.error('[handleFiles]', errorMessage);
        }
        
        // Log the state of the 'files' array after processing
        console.log("[handleFiles] Populated 'files' array (name and detected type):", files.map(f => ({ name: f.file.name, type: f.type })));

        if (files.length > 0 && !isUploading) {
            uploadSequentially();
        }
    }

    // Set up drag and drop events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, e => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        });
    });

    // Handle file drop
    dropZone.addEventListener('drop', e => {
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });

    // Handle click on drop zone
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file input change
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFiles(fileInput.files);
            fileInput.value = ''; // Reset input
        }
    });

    // Mark this dropZone as initialized
    dropZone.dataset.uploaderInitialized = 'true';
    console.log('[initUploader] Marked as initialized:', dropZone.id);

    // Upload files sequentially
    function uploadSequentially() {
        if (isUploading || files.length === 0) return;

        isUploading = true;
        currentUploadIndex = 0;

        console.log(`Starting sequential upload of ${files.length} files`);

        function uploadNext() {
            if (currentUploadIndex >= files.length) {
                // All files uploaded
                console.log('All files uploaded successfully');
                isUploading = false;
                files = [];

                // HTMX should handle the update of the target div automatically
                // based on the response from the upload hx-post.
                // We might need to manually trigger an event if HTMX doesn't pick up the change
                // for the #file-upload-and-actions target from the fetch() call directly,
                // but the form itself has hx-post, so fetch() is a bit different.

                // For now, let's assume the htmx form submission that *triggered* this JS flow (if any)
                // or a subsequent htmx request will refresh the necessary part.
                // The uploadForm is using hx-post, so the last fetch() call's success
                // should result in the form's hx-target being updated by HTMX.
                // If the upload was initiated purely by drag-drop without an explicit htmx form submission event,
                // then the page update relies on the fetch() response being handled by an htmx-aware component, or we need to trigger one.

                // Given the form has hx-post, and we are using fetch for individual files,
                // the hx-target specified on the form will be updated by htmx once the *form's* hx-post completes.
                // Our sequential fetch calls are part of that form's lifecycle if triggered by an htmx interaction.
                // If triggered by pure JS (drag-drop), the form's hx-target won't automatically update unless we make it.

                // The original form uses hx-post. The current JS bypasses that direct hx-post for sequential uploads.
                // The fetch call's response from the server route `upload_file_frontend` is what contains the updated HTML.
                // We need to make sure this HTML is inserted into the hx-target of the form.

                // The `upload_file_frontend` is already designed to return HTML for HTMX requests.
                // The last fetch call in the sequence needs to process this HTML response.
                // Let's make the last fetch() call's .then() handle the htmx target update.

                return; // End of upload sequence
            }

            const fileObj = files[currentUploadIndex];
            console.log(`Uploading file ${currentUploadIndex + 1}/${files.length}: ${fileObj.file.name} as ${fileObj.type}`);

            // Prepare form data
            const formData = new FormData();
            formData.append('file', fileObj.file);
            formData.append('file_type', fileObj.type);

            // Get the form action or construct it from the current URL
            let uploadUrl = uploadForm.getAttribute('action');

            // If the URL is missing, try to construct it from the current URL
            if (!uploadUrl || uploadUrl.includes('null')) {
                console.log('Form action URL is missing, constructing from current URL');
                const currentUrl = window.location.pathname;
                const match = currentUrl.match(/\/study\/(\d+)\/scenario\/(\d+)/);

                if (match && match[1] && match[2]) {
                    const studyId = match[1];
                    const scenarioId = match[2];
                    uploadUrl = `/study/${studyId}/scenario/${scenarioId}/upload`;
                    console.log(`Constructed URL: ${uploadUrl}`);
                } else {
                    console.error('Could not construct upload URL from current URL');
                    alert('Error: Could not determine upload URL. Please refresh the page and try again.');
                    isUploading = false;
                    return;
                }
            }

            // Use fetch for the upload
            fetch(uploadUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'HX-Request': 'true'
                }
            })
            .then(response => {
                if (!response.ok) {
                    // If the last file fails, we still want to allow retry or reflect status, so don't just error out the whole sequence silently.
                    return response.text().then(text => { 
                        throw new Error(`HTTP error! status: ${response.status}, body: ${text}`);
                    });
                }
                return response.text(); // Get the HTML response text
            })
            .then(html => {
                console.log(`File ${currentUploadIndex + 1} uploaded successfully`);
                currentUploadIndex++;
                if (currentUploadIndex >= files.length) {
                    // This was the last file, update the target with the HTML response from the server
                    const targetSelector = uploadForm.getAttribute('hx-target');
                    if (targetSelector) {
                        const targetElement = document.querySelector(targetSelector);
                        if (targetElement) {
                            targetElement.innerHTML = html; // Manually set the HTML
                            htmx.process(targetElement);    // Tell HTMX to process this new content
                        } else {
                            console.error('HTMX target not found:', targetSelector);
                            window.location.reload(); // Fallback to reload if target not found
                        }
                    } else {
                        console.error('No hx-target found on upload form.');
                        window.location.reload(); // Fallback to reload
                    }
                    // Final cleanup after the last file's HTML has been processed.
                    console.log('All files processed, HTMX target updated and processed.');
                    isUploading = false;
                    files = []; 
                    // No return here, allowing the main function to exit.
                } else {
                    setTimeout(uploadNext, 100); // Upload next file after a short delay
                }
            })
            .catch(error => {
                // Log which file this error is associated with, if fileObj is defined
                const fileNameForError = fileObj && fileObj.file ? fileObj.file.name : "UNKNOWN (fileObj undefined)";
                console.error(`Upload error for file index ${currentUploadIndex}, name: ${fileNameForError}:`, error);
                alert(`Error uploading ${fileNameForError}: ${error.message}`);
                currentUploadIndex++;
                setTimeout(uploadNext, 500);
            });
        }

        uploadNext();
    }

    // Prevent default form submission - we handle everything through the button
    uploadForm.addEventListener('submit', e => {
        e.preventDefault();
    });
}
