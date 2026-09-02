// Render hasil ringkasan (respons backend) ke panel Summary.

function fillList(ulEl, items, emptyText){
  ulEl.innerHTML = '';
  if(!items || !items.length){
    const li = document.createElement('li');
    li.textContent = emptyText;
    li.style.color = 'var(--ink-faint)';
    ulEl.appendChild(li);
    return;
  }
  items.forEach(text => {
    const li = document.createElement('li');
    li.textContent = text;
    ulEl.appendChild(li);
  });
}

function renderSummaryResult(data){
  document.getElementById('metaPages').textContent = data.page_count;
  const totalTime = (data.extraction_seconds || 0) + (data.summarization_seconds || 0);
  document.getElementById('metaTime').textContent = totalTime.toFixed(1) + 's';
  document.getElementById('metaWords').textContent =
    (data.summary_word_count || 0).toLocaleString('id-ID');
  document.getElementById('metaModel').textContent = data.model || '—';

  const chunkNote = document.getElementById('chunkNote');
  if(data.chunk_count && data.chunk_count > 1){
    chunkNote.textContent = `⚡ Diproses dalam ${data.chunk_count} bagian (chunking)`;
    chunkNote.style.display = 'inline-flex';
  } else {
    chunkNote.style.display = 'none';
  }

  const warningsNote = document.getElementById('warningsNote');
  if(data.warnings && data.warnings.length){
    warningsNote.textContent = data.warnings.join(' ');
    warningsNote.style.display = 'block';
  } else {
    warningsNote.style.display = 'none';
  }

  const summary = data.summary || {};
  document.getElementById('sumExec').textContent =
    summary.executive_summary || '(Tidak ada ringkasan.)';
  fillList(document.getElementById('sumKeyPoints'), summary.key_points, 'Tidak ada key points.');
  fillList(document.getElementById('sumFindings'), summary.main_findings, 'Tidak ada temuan spesifik.');
  document.getElementById('sumConclusion').textContent =
    summary.conclusion || '(Tidak ada kesimpulan.)';

  resultContent.classList.add('show');
}
