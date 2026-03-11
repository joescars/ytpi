(function () {
  const categorySelect = document.getElementById('category');
  const customWrap = document.getElementById('customCategoryWrap');
  const customInput = document.getElementById('customCategory');
  const form = document.getElementById('download-form');
  const submitBtn = document.getElementById('submit-btn');

  function syncCustomField() {
    const custom = categorySelect.value === '__custom__';
    customWrap.hidden = !custom;
    customInput.required = custom;
    if (!custom) {
      customInput.value = '';
    }
  }

  categorySelect.addEventListener('change', syncCustomField);

  form.addEventListener('submit', () => {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Queueing...';
  });

  syncCustomField();
})();
