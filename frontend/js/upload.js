// Tahap 1: dropzone, validasi file di sisi client, drag & drop.

function formatSize(bytes){
  if(bytes < 1024*1024) return (bytes/1024).toFixed(0) + ' KB';
  return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

function showError(message){
  errorMsg.textContent = message;
  errorMsg.classList.add('show');
  dropzone.classList.add('has-error');
}

function clearError(){
  errorMsg.classList.remove('show');
  dropzone.classList.remove('has-error');
}

function resetResultPanel(){
  resultEmpty.style.display = 'flex';
  resultLoading.classList.remove('show');
  resultContent.classList.remove('show');
  resultError.classList.remove('show');
}

function handleFile(file){
  clearError();

  if(file.type !== 'application/pdf'){
    showError('Please upload a PDF document.');
    return;
  }
  if(file.size > MAX_SIZE_MB * 1024 * 1024){
    showError(`File size must be below ${MAX_SIZE_MB} MB.`);
    return;
  }

  currentFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatSize(file.size);
  emptyState.style.display = 'none';
  fileChip.style.display = 'flex';
  dropzone.classList.add('has-file');
  summarizeBtn.disabled = false;
  resetResultPanel();
}

function clearFile(){
  currentFile = null;
  fileInput.value = '';
  emptyState.style.display = 'block';
  fileChip.style.display = 'none';
  dropzone.classList.remove('has-file');
  summarizeBtn.disabled = true;
  clearError();
  resetResultPanel();
}

// Click / browse
browseBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
dropzone.addEventListener('click', () => { if(!currentFile) fileInput.click(); });
fileInput.addEventListener('change', () => { if(fileInput.files[0]) handleFile(fileInput.files[0]); });

// Drag & drop
['dragenter','dragover'].forEach(evt => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault(); e.stopPropagation();
    if(!currentFile) dropzone.classList.add('dragover');
  });
});
['dragleave','drop'].forEach(evt => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault(); e.stopPropagation();
    dropzone.classList.remove('dragover');
  });
});
dropzone.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if(file) handleFile(file);
});

removeFile.addEventListener('click', (e) => { e.stopPropagation(); clearFile(); });
