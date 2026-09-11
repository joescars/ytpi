(function () {
  const categorySelect = document.getElementById('category');
  const categoryWrap = document.getElementById('categoryWrap');
  const customWrap = document.getElementById('customCategoryWrap');
  const customInput = document.getElementById('customCategory');
  const form = document.getElementById('download-form');
  const submitBtn = document.getElementById('submit-btn');
  const audioOnlyCheckbox = document.getElementById('audioOnly');
  const audioFormatWrap = document.getElementById('audioFormatWrap');
  const qualitySelect = document.getElementById('quality');
  const qualityWrap = document.getElementById('qualityWrap');

  // Store previous values when audio-only is enabled
  let previousCategory = categorySelect.value;
  let previousQuality = qualitySelect.value;

  // URL detection
  const urlTextarea = document.getElementById('url');
  const urlDetectionDiv = document.createElement('div');
  urlDetectionDiv.className = 'url-detection';
  urlDetectionDiv.style.marginTop = '0.5rem';
  urlDetectionDiv.style.fontSize = '0.9em';
  urlDetectionDiv.style.color = 'var(--text-secondary)';
  urlTextarea.parentNode.appendChild(urlDetectionDiv);

  function updateUrlDetection() {
    const urls = urlTextarea.value.trim().split('\n').filter(url => url.trim());
    if (urls.length === 0) {
      urlDetectionDiv.textContent = '';
      urlDetectionDiv.hidden = true;
      return;
    }

    const detectionResults = [];
    urls.forEach(url => {
      if (url.includes('playlist?list=') || url.includes('/playlist/')) {
        detectionResults.push('playlist');
      } else if (url.includes('youtube.com/watch') || url.includes('youtu.be/')) {
        detectionResults.push('video');
      } else {
        detectionResults.push('unknown');
      }
    });

    const uniqueResults = [...new Set(detectionResults)];
    if (uniqueResults.length === 1) {
      if (uniqueResults[0] === 'playlist') {
        urlDetectionDiv.textContent = '✓ This appears to be a YouTube playlist';
        urlDetectionDiv.style.color = 'var(--success)';
      } else if (uniqueResults[0] === 'video') {
        urlDetectionDiv.textContent = '✓ This appears to be a YouTube video';
        urlDetectionDiv.style.color = 'var(--success)';
      } else {
        urlDetectionDiv.textContent = '';
        urlDetectionDiv.hidden = true;
      }
    } else if (detectionResults.includes('playlist') && detectionResults.includes('video')) {
      urlDetectionDiv.textContent = '✓ Mix of videos and playlists detected';
      urlDetectionDiv.style.color = 'var(--text-secondary)';
    } else {
      urlDetectionDiv.textContent = '';
      urlDetectionDiv.hidden = true;
    }
    urlDetectionDiv.hidden = false;
  }

  function syncCustomField() {
    const custom = categorySelect.value === '__custom__';
    customWrap.hidden = !custom;
    customInput.required = custom;
    if (!custom) {
      customInput.value = '';
    }
  }

  function syncAudioOnlyField() {
    const audioOnly = audioOnlyCheckbox.checked;
    audioFormatWrap.hidden = !audioOnly;
    qualitySelect.disabled = audioOnly;
    qualityWrap.hidden = audioOnly;
    categoryWrap.hidden = audioOnly;
    categorySelect.disabled = audioOnly;
    
    if (audioOnly) {
      // Store current values before hiding
      previousCategory = categorySelect.value;
      previousQuality = qualitySelect.value;
      customWrap.hidden = true;
      customInput.required = false;
      customInput.value = '';
    } else {
      // Restore previous values when audio-only is disabled
      if (previousCategory && previousCategory !== '__custom__') {
        categorySelect.value = previousCategory;
      }
      if (previousQuality) {
        qualitySelect.value = previousQuality;
      }
      syncCustomField();
    }
  }

  categorySelect.addEventListener('change', syncCustomField);
  audioOnlyCheckbox.addEventListener('change', syncAudioOnlyField);

  urlTextarea.addEventListener('input', updateUrlDetection);
  // Initial detection
  updateUrlDetection();

  form.addEventListener('submit', () => {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Queueing...';
  });

  syncCustomField();
  syncAudioOnlyField();

  // Focus on URL field if there's an error
  if (document.getElementById('form-error')) {
    const urlField = document.getElementById('url');
    if (urlField) {
      urlField.focus();
    }
  }
})();