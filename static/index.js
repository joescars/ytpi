(function () {
  const categorySelect = document.getElementById('category');
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
  }

  categorySelect.addEventListener('change', syncCustomField);
  audioOnlyCheckbox.addEventListener('change', syncAudioOnlyField);

  form.addEventListener('submit', () => {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Queueing...';
  });

  syncCustomField();
  syncAudioOnlyField();
})();
