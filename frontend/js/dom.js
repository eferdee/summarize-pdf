// Referensi elemen DOM yang dipakai bersama oleh upload.js, render.js, dan api.js.
// File ini harus dimuat sebelum ketiga file tersebut.

const dropzone   = document.getElementById('dropzone');
const fileInput  = document.getElementById('fileInput');
const browseBtn  = document.getElementById('browseBtn');
const emptyState = document.getElementById('dz-empty-state');
const fileChip   = document.getElementById('fileChip');
const fileName   = document.getElementById('fileName');
const fileSize   = document.getElementById('fileSize');
const removeFile = document.getElementById('removeFile');
const errorMsg   = document.getElementById('errorMsg');
const summarizeBtn = document.getElementById('summarizeBtn');

const resultEmpty   = document.getElementById('resultEmpty');
const resultLoading = document.getElementById('resultLoading');
const resultContent = document.getElementById('resultContent');
const resultError   = document.getElementById('resultError');
const loadingStep   = document.getElementById('loadingStep');
const retryBtn      = document.getElementById('retryBtn');

const MAX_SIZE_MB = 10;
let currentFile = null;
