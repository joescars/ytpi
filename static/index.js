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
    categoryWrap.hidden = audioOnly;
    categorySelect.disabled = audioOnly;
    if (audioOnly) {
      customWrap.hidden = true;
      customInput.required = false;
      customInput.value = '';
    } else {
      syncCustomField();
    }
  }

  categorySelect.addEventListener('change', syncCustomField);
  audioOnlyCheckbox.addEventListener('change', syncAudioOnlyField);

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