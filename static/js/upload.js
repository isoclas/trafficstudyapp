// Enhanced file uploader with multi-file drag-and-drop support
document.addEventListener('htmx:load', initUploader);
document.addEventListener('DOMContentLoaded', initUploader);

function initUploader() {
    const dropZone = document.getElementById('file-drop-zone');
    if (!dropZone) return;

    if (dropZone.dataset.uploaderInitialized === 'true') {
        console.log('[initUploader] Already initialized for this drop zone. Skipping.');
        return;
    }

    const fileInput = document.getElementById('fileInput');
    const fileTypeInput = document.getElementById('file_type');
    const uploadForm = document.getElementById('upload-form');


    if (!fileInput || !uploadForm) {
        console.warn('[initUploader] Missing fileInput or uploadForm for a dropZone. Uploader may not fully function.');
        return; 
    }
    
    console.log('[initUploader] Initializing for drop zone:', dropZone.id);

    let files = [];
    let currentUploadIndex = 0;
    let isUploading = false;

    function detectFileType(file) {
        console.log("[detectFileType] Processing file:", file.name);
        const fileName = file.name.toLowerCase();
        console.log("[detectFileType] Lowercase fileName:", fileName);

        let detectedType = 'am_csv'; // default type

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
                            detectedType = 'am_csv'; // default for CSV
                        }
                    }
                }
            }
            console.log("[detectFileType] CSV detected as:", detectedType);
        } else {
            console.error("[detectFileType] Invalid file type. Only .csv and .txt files are allowed:", file.name);
            return null;
        }
        console.log("[detectFileType] Final detection for", file.name, "->", detectedType);
        return detectedType;
    }

    function handleFiles(selectedFiles) {
        console.log("[handleFiles] Received selectedFiles count:", selectedFiles.length, selectedFiles);
        if (!selectedFiles || !selectedFiles.length) return;
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

    // drag and drop events
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

    dropZone.addEventListener('drop', e => {
        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });

    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleFiles(fileInput.files);
            fileInput.value = '';
        }
    });

    dropZone.dataset.uploaderInitialized = 'true';
    console.log('[initUploader] Marked as initialized:', dropZone.id);

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
                return; 
            }

            const fileObj = files[currentUploadIndex];
            console.log(`Uploading file ${currentUploadIndex + 1}/${files.length}: ${fileObj.file.name} as ${fileObj.type}`);

            const formData = new FormData();
            formData.append('file', fileObj.file);
            formData.append('file_type', fileObj.type);

            let uploadUrl = uploadForm.getAttribute('action');

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

            fetch(uploadUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'HX-Request': 'true'
                }
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => { 
                        throw new Error(`HTTP error! status: ${response.status}, body: ${text}`);
                    });
                }
                return response.text();
            })
            .then(html => {
                console.log(`File ${currentUploadIndex + 1} uploaded successfully`);
                
                // Update the target with the HTML response from the server after each upload
                const targetSelector = uploadForm.getAttribute('hx-target');
                if (targetSelector) {
                    const targetElement = document.querySelector(targetSelector);
                    if (targetElement) {
                        targetElement.innerHTML = html; // Manually set the HTML
                        htmx.process(targetElement);    // Tell HTMX to process this new content
                    } else {
                        console.error('HTMX target not found:', targetSelector);
                    }
                } else {
                    console.error('No hx-target found on upload form.');
                }
                
                currentUploadIndex++;
                if (currentUploadIndex >= files.length) {
                    console.log('All files processed, HTMX target updated and processed.');
                    isUploading = false;
                    files = []; 
                } else {
                    setTimeout(uploadNext, 100);
                }
            })
            .catch(error => {
                const fileNameForError = fileObj && fileObj.file ? fileObj.file.name : "UNKNOWN (fileObj undefined)";
                console.error(`Upload error for file index ${currentUploadIndex}, name: ${fileNameForError}:`, error);
                alert(`Error uploading ${fileNameForError}: ${error.message}`);
                currentUploadIndex++;
                setTimeout(uploadNext, 500);
            });
        }

        uploadNext();
    }

    uploadForm.addEventListener('submit', e => {
        e.preventDefault();
    });
}
