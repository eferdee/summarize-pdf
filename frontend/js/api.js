// Tahap 3: panggilan nyata ke backend FastAPI (PDF -> Text -> Summary via LLM).

const loadingSteps = [
  'Mengunggah PDF...',
  'Mengekstrak teks dari PDF...',
  'Meringkas dengan AI...',
  'Menyusun hasil...'
];

summarizeBtn.addEventListener('click', () => {
  if(!currentFile) return;
  // Halaman baru boleh discroll begitu proses Summarize dimulai.
  document.body.classList.add('scroll-enabled');
  runSummarize();
});

async function runSummarize(){
  resultEmpty.style.display = 'none';
  resultContent.classList.remove('show');
  resultError.classList.remove('show');
  resultLoading.classList.add('show');

  summarizeBtn.disabled = true;
  summarizeBtn.classList.add('loading');
  document.getElementById('summarizeBtnText').textContent = 'Processing...';

  let stepIndex = 0;
  loadingStep.textContent = loadingSteps[0];
  const stepInterval = setInterval(() => {
    stepIndex = (stepIndex + 1) % loadingSteps.length;
    loadingStep.textContent = loadingSteps[stepIndex];
  }, 900);

  try {
    const formData = new FormData();
    formData.append('file', currentFile);

    const res = await fetch(`${API_BASE}/api/summarize`, {
      method: 'POST',
      body: formData
    });

    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      throw new Error('The server sent an unexpected response. Please try again.');
    }

    if(!res.ok){
      // Backend selalu mengirim pesan error yang aman ditampilkan (lihat main.py).
      throw new Error(data.detail || 'Unable to generate summary. Please try again.');
    }

    renderSummaryResult(data);
  } catch(err){
    document.getElementById('errorText').textContent =
      err.message === 'Failed to fetch'
        ? 'Cannot reach the backend. Make sure the FastAPI server is running.'
        : err.message;
    resultError.classList.add('show');
  } finally {
    clearInterval(stepInterval);
    resultLoading.classList.remove('show');
    summarizeBtn.disabled = false;
    summarizeBtn.classList.remove('loading');
    document.getElementById('summarizeBtnText').textContent = 'Summarize';
  }
}

retryBtn.addEventListener('click', () => {
  resultError.classList.remove('show');
  runSummarize();
});
