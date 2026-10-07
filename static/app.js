(() => {
  'use strict';
  const list = document.querySelector('#job-list');
  const form = document.querySelector('#download-form');
  const toastRegion = document.querySelector('#toast-region');
  const dialog = document.querySelector('#details-dialog');
  const emptyState = document.querySelector('#empty-state');
  const state = { filter: 'all', search: '', offset: 0, total: 0, jobs: [], busy: false, timer: 0, playlistTimer: 0, delay: 5000, stopped: false };
  const $ = (selector, root = document) => root.querySelector(selector);
  const text = (node, value) => { node.textContent = value == null ? '' : String(value); return node; };
  const element = (tag, className, value) => { const node = document.createElement(tag); if (className) node.className = className; if (value !== undefined) text(node, value); return node; };
  const labels = { queued: 'In queue', downloading: 'Downloading', finished: 'Finished', error: 'Needs attention', cancelled: 'Cancelled' };
  const escapeText = (value) => String(value || '').trim();

  function toast(message, kind = '') {
    const item = element('div', `toast ${kind}`, message);
    toastRegion.append(item);
    window.setTimeout(() => item.remove(), 4500);
  }

  function selectedTheme() {
    const saved = localStorage.getItem('ytpi-theme');
    return saved === 'dark' || saved === 'light' ? saved : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function setTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('ytpi-theme', theme);
    document.querySelectorAll('.theme-toggle').forEach((button) => button.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`));
  }
  setTheme(selectedTheme());
  document.querySelectorAll('.theme-toggle').forEach((button) => button.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark')));

  const audioToggle = $('#audio-only');
  const qualityField = $('#quality-field');
  const audioField = $('#audio-field');
  const hint = $('#audio-hint');
  audioToggle.addEventListener('change', () => {
    qualityField.hidden = audioToggle.checked;
    $('#category').disabled = audioToggle.checked;
    audioField.hidden = !audioToggle.checked;
    hint.hidden = !audioToggle.checked;
  });
  $('#category').addEventListener('change', (event) => { $('#custom-field').hidden = event.target.value !== '__custom__'; });

  function humanTitle(job) {
    const title = escapeText(job.title);
    if (title) return title;
    try { return `${new URL(job.url).hostname.replace(/^www\./, '')} video`; }
    catch { return 'Untitled download'; }
  }
  function meta(job) {
    const mode = job.audio_only ? `Audio · ${(job.audio_format || 'mp3').toUpperCase()}` : (job.quality === 'max' ? 'Best quality' : `${job.quality}p`);
    return `${job.category || 'Main library'} · ${mode}`;
  }
  function createJobCard(job) {
    const card = element('article', 'job-card'); card.dataset.jobid = job.id; card.dataset.status = job.status;
    const leading = element('div', 'job-leading'); leading.append(element('span', 'job-type-icon', job.audio_only ? '♫' : '▶'));
    const main = element('div', 'job-main');
    const titleRow = element('div', 'job-title-row');
    const title = element('h3', 'job-title', humanTitle(job)); title.title = humanTitle(job);
    titleRow.append(title, element('span', `status-chip status-${job.status}`, labels[job.status] || job.status));
    main.append(titleRow, element('div', 'job-meta', meta(job)));
    const progressLine = element('div', 'progress-line');
    const progress = element('div', 'progress-track'); progress.setAttribute('role', 'progressbar'); progress.setAttribute('aria-label', `Progress for ${humanTitle(job)}`); progress.setAttribute('aria-valuemin', '0'); progress.setAttribute('aria-valuemax', '100');
    const percent = Math.max(0, Math.min(100, Number(job.progress) || 0)); progress.setAttribute('aria-valuenow', String(percent));
    const fill = element('span'); fill.style.width = `${percent}%`; progress.append(fill);
    progressLine.append(progress, element('span', 'progress-label', `${Math.round(percent)}%`)); main.append(progressLine);
    if (job.error) main.append(element('p', 'job-error', job.error));
    const actions = element('div', 'job-actions');
    const details = element('button', 'text-button details-button', 'Details'); details.type = 'button'; details.dataset.id = job.id; details.setAttribute('aria-label', `Details for ${humanTitle(job)}`); actions.append(details);
    if (job.status === 'queued' || job.status === 'downloading') addAction(actions, 'cancel', job.id, 'Cancel');
    else if (job.status === 'error' || job.status === 'cancelled') addAction(actions, 'retry', job.id, 'Retry');
    card.append(leading, main, actions);
    return card;
  }
  function addAction(parent, action, id, label) {
    const button = element('button', action === 'retry' ? 'button button-outlined action-button' : 'icon-button action-button', action === 'cancel' ? '×' : label);
    button.type = 'button'; button.dataset.action = action; button.dataset.id = id;
    if (action === 'cancel') button.setAttribute('aria-label', 'Cancel download');
    parent.append(button);
  }
  function render(jobs, append = false) {
    const focused = document.activeElement;
    const focusId = focused?.dataset?.id;
    const focusAction = focused?.dataset?.action || (focused?.classList?.contains('details-button') ? 'details' : '');
    if (!append) list.replaceChildren();
    if (!append && state.total === 0) list.append(emptyState);
    for (const job of jobs) list.append(createJobCard(job));
    emptyState.hidden = state.total > 0;
    const counts = state.counts || {};
    const current = state.jobs;
    const totalAll = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0);
    $('#stat-total').textContent = String(totalAll);
    $('#stat-active').textContent = String((counts.queued || 0) + (counts.downloading || 0));
    $('#stat-finished').textContent = String(counts.finished || 0);
    $('#stat-errors').textContent = String(counts.error || 0);
    $('#nav-count').textContent = String(totalAll);
    $('#results-label').textContent = state.total ? `Showing ${current.length} of ${state.total} downloads` : 'No downloads yet';
    $('#clear-button').hidden = !((counts.finished || 0) + (counts.error || 0) + (counts.cancelled || 0));
    const more = $('#load-more');
    if (more) more.remove();
    if (current.length < state.total) {
      const button = element('button', 'button button-tonal load-more', 'Load more downloads'); button.id = 'load-more'; button.type = 'button'; button.addEventListener('click', () => loadJobs(true)); list.append(button);
    }
    if (focusId && focusAction) {
      const match = [...list.querySelectorAll('[data-id]')].find((node) => node.dataset.id === focusId && (node.dataset.action === focusAction || (focusAction === 'details' && node.classList.contains('details-button'))));
      match?.focus({ preventScroll: true });
    }
    $('#job-list').setAttribute('aria-busy', 'false');
  }
  function api(path, options = {}) {
    return fetch(path, { ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) } }).then(async (response) => {
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
      return body;
    });
  }
  async function loadJobs(append = false) {
    if (state.busy || document.hidden) return;
    state.busy = true;
    const offset = append ? state.jobs.length : 0;
    const params = new URLSearchParams({ limit: '40', offset: String(offset) });
    if (state.filter !== 'all') params.set('status', state.filter === 'error' ? 'error' : state.filter);
    if (state.search) params.set('search', state.search);
    try {
      const data = await api(`/api/jobs?${params}`);
      state.total = data.total;
      state.jobs = append ? [...state.jobs, ...data.items] : data.items;
      state.counts = data.status_counts || {};
      render(data.items, append);
      state.delay = 5000;
      $('#connection-label').textContent = 'All systems ready';
    } catch (error) {
      $('#connection-label').textContent = 'Connection issue · retrying';
      state.delay = Math.min(30000, state.delay * 1.6);
      if (!state.jobs.length) toast(error.message, 'error');
    } finally {
      state.busy = false;
      schedulePoll();
    }
  }
  function schedulePoll() {
    clearTimeout(state.timer);
    clearTimeout(state.playlistTimer);
    if (!state.stopped && !document.hidden) {
      state.timer = setTimeout(() => loadJobs(false), state.delay);
      state.playlistTimer = setTimeout(loadPlaylists, Math.min(state.delay, 10000));
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { loadJobs(false); loadPlaylists(); }
    else { clearTimeout(state.timer); clearTimeout(state.playlistTimer); }
  });
  $('#refresh-button').addEventListener('click', () => { loadJobs(false); loadPlaylists(); });

  $('#download-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = $('#queue-button'); button.disabled = true; button.textContent = 'Adding to queue…';
    const custom = $('#category').value === '__custom__';
    const urls = $('#urls').value.split(/[\n,]+/).map((url) => url.trim()).filter(Boolean);
    try {
      const data = await api('/api/jobs', { method: 'POST', body: JSON.stringify({ urls, category: custom ? '' : $('#category').value, custom_category: custom ? $('#custom-category').value : '', quality: $('#quality').value, audio_only: audioToggle.checked, audio_format: $('#audio-format').value }) });
      toast(`${data.total} download${data.total === 1 ? '' : 's'} added to your queue`);
      $('#urls').value = '';
      if (custom) { $('#category').value = ''; $('#custom-field').hidden = true; }
      await loadJobs(false);
      $('#downloads').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
    } catch (error) {
      toast(error.message, 'error');
      $('#urls').focus();
    } finally {
      button.disabled = false; button.innerHTML = '<span aria-hidden="true">↓</span> Queue download';
    }
  });

  document.querySelectorAll('.filter-tab').forEach((button) => button.addEventListener('click', () => {
    document.querySelectorAll('.filter-tab').forEach((tab) => { tab.classList.toggle('active', tab === button); tab.setAttribute('aria-pressed', String(tab === button)); });
    state.filter = button.dataset.filter; state.jobs = []; loadJobs(false);
  }));
  let searchTimer;
  $('#search').addEventListener('input', (event) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.search = event.target.value.trim(); state.jobs = []; loadJobs(false); }, 250); });

  list.addEventListener('click', async (event) => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.classList.contains('load-more')) return;
    const id = button.dataset.id; if (!id) return;
    if (button.classList.contains('details-button')) return showDetails(id);
    const action = button.dataset.action; if (!action) return;
    button.disabled = true;
    try {
      await api(`/api/jobs/${encodeURIComponent(id)}/${action}`, { method: 'POST' });
      toast(action === 'cancel' ? 'Download cancelled' : 'Download added back to the queue');
      await loadJobs(false);
    } catch (error) { toast(error.message, 'error'); button.disabled = false; }
  });
  async function showDetails(id) {
    try {
      const job = await api(`/api/jobs/${encodeURIComponent(id)}`);
      const content = $('#details-content'); content.replaceChildren();
      content.append(element('div', 'eyebrow', 'DOWNLOAD DETAILS'), element('h2', '', humanTitle(job)), element('p', 'detail-subtitle', labels[job.status] || job.status));
      const grid = element('div', 'detail-grid');
      for (const [label, value] of [['Saved to', job.category || 'Main library'], ['Format', meta(job).split(' · ').slice(-1)[0]], ['Progress', `${Math.round(Number(job.progress) || 0)}%`], ['Added', new Date(job.created_at).toLocaleString()], ['File', job.filename || 'Not available yet']]) {
        const cell = element('div', 'detail-cell'); cell.append(element('span', '', label), element('strong', '', value)); grid.append(cell);
      }
      const link = element('a', 'text-button', 'Open original link ↗'); link.href = job.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; content.append(grid, link);
      if (job.status === 'finished' && job.filename) {
        const confirmation = element('p', 'detail-file-path', `Saved file: ${job.filename}`);
        content.append(confirmation);
      }
      if (job.error) content.append(element('h3', '', 'What happened'), element('p', 'job-error', job.error));
      content.append(element('h3', '', 'Technical details'));
      const output = element('pre', 'technical-output', job.output || 'No technical output yet.'); content.append(output);
      dialog.showModal();
    } catch (error) { toast(error.message, 'error'); }
  }
  $('#clear-button').addEventListener('click', async () => {
    if (!window.confirm('Remove finished, failed, and cancelled history records? Downloaded media files will not be deleted.')) return;
    try { const data = await api('/api/jobs/completed', { method: 'DELETE' }); toast(`${data.removed} history record${data.removed === 1 ? '' : 's'} removed`); await loadJobs(false); }
    catch (error) { toast(error.message, 'error'); }
  });
  document.querySelectorAll('.mobile-nav-item').forEach((item) => item.addEventListener('click', () => {
    document.querySelectorAll('.mobile-nav-item').forEach((nav) => nav.classList.toggle('selected', nav === item));
  }));
  let editingPlaylistId = null;
  let playlistBusy = false;
  function labeledField(labelText, control) {
    const wrapper = element('label', 'playlist-field');
    wrapper.append(element('span', '', labelText), control);
    return wrapper;
  }
  async function loadPlaylists() {
    if (playlistBusy || document.hidden || $('.playlist-form:focus-within')) return;
    playlistBusy = true;
    try {
      const data = await api('/api/playlists');
      const container = $('#playlists-list');
      container.replaceChildren();
      if (!data.items.length) {
        const empty = element('div', 'playlist-placeholder');
        empty.append(element('span', '', '▧'), element('span', '', 'Queue a YouTube playlist to save it here.'));
        container.append(empty);
        return;
      }
      for (const playlist of data.items) {
        const card = element('article', 'playlist-card');
        const header = element('div', 'playlist-header');
        const title = element('a', 'playlist-name', playlist.name || 'YouTube playlist');
        title.href = playlist.url; title.target = '_blank'; title.rel = 'noopener noreferrer';
        const status = element('span', `status-chip status-${playlist.sync_status === 'successful' ? 'finished' : playlist.sync_status === 'failed' ? 'error' : playlist.sync_status === 'syncing' ? 'downloading' : 'queued'}`, playlist.sync_status || 'Saved');
        header.append(title, status);
        const summary = element('p', 'playlist-summary', `${playlist.category || 'Main library'} · ${playlist.audio_only ? `Audio · ${(playlist.audio_format || 'mp3').toUpperCase()}` : playlist.quality === 'max' ? 'Best quality' : `${playlist.quality}p`}`);
        const metadata = element('p', 'playlist-last-sync', playlist.last_successful_sync_at ? `Last successful sync · ${new Date(playlist.last_successful_sync_at).toLocaleString()}` : 'Not synced yet');
        const controls = element('div', 'playlist-actions');
        const edit = element('button', 'button button-outlined', 'Edit settings'); edit.type = 'button'; edit.dataset.playlistAction = 'edit'; edit.dataset.playlistId = playlist.id;
        const sync = element('button', 'button button-tonal', playlist.sync_status === 'syncing' || playlist.sync_status === 'requested' ? 'Sync queued…' : 'Sync now'); sync.type = 'button'; sync.dataset.playlistAction = 'sync'; sync.dataset.playlistId = playlist.id;
        sync.disabled = ['syncing','requested'].includes(playlist.sync_status);
        controls.append(edit, sync);
        card.append(header, summary, metadata);
        if (playlist.discovered_count || playlist.downloaded_count || playlist.already_present_count || playlist.failed_count) {
          const counts = element('p', 'playlist-counts', `${playlist.downloaded_count || 0} new · ${playlist.already_present_count || 0} already saved · ${playlist.failed_count || 0} failed`);
          card.append(counts);
        }
        card.append(controls);
        if (editingPlaylistId === playlist.id) {
          const editForm = element('form', 'playlist-form'); editForm.dataset.playlistId = playlist.id;
          const category = element('input'); category.name = 'category'; category.value = playlist.category || ''; category.maxLength = 80; category.placeholder = 'Main library';
          const quality = element('select'); quality.name = 'quality';
          for (const [value, label] of [['max','Best available'],['2160','2160p'],['1440','1440p'],['1080','1080p'],['720','720p'],['480','480p']]) { const option = element('option','',label); option.value = value; option.selected = value === playlist.quality; quality.append(option); }
          const audioLabel = element('label','playlist-audio-toggle'); const audio = element('input'); audio.type = 'checkbox'; audio.name = 'audio_only'; audio.checked = Boolean(playlist.audio_only); audioLabel.append(audio, document.createTextNode(' Audio only'));
          const format = element('select'); format.name = 'audio_format';
          for (const value of ['mp3','wav']) { const option = element('option','',value.toUpperCase()); option.value = value; option.selected = value === (playlist.audio_format || 'mp3'); format.append(option); }
          const actions = element('div','playlist-actions'); const save = element('button','button button-filled','Save settings'); save.type='submit'; const cancelEdit = element('button','text-button','Cancel'); cancelEdit.type='button'; cancelEdit.dataset.playlistAction='close-edit'; actions.append(save,cancelEdit);
          editForm.append(labeledField('Save to folder',category),labeledField('Video quality',quality),audioLabel,labeledField('Audio format',format),actions);
          editForm.addEventListener('submit', async (event) => {
            event.preventDefault(); const submit = editForm.querySelector('[type=submit]'); submit.disabled = true;
            try {
              await api(`/api/playlists/${playlist.id}`, { method: 'PUT', body: JSON.stringify({ category: category.value, quality: quality.value, audio_only: audio.checked, audio_format: format.value }) });
              editingPlaylistId = null; toast('Playlist settings saved'); await loadPlaylists();
            } catch (error) { toast(error.message, 'error'); submit.disabled = false; }
          });
          card.append(editForm);
        }
        container.append(card);
      }
    } catch (error) { toast(error.message, 'error'); }
    finally { playlistBusy = false; }
  }
  $('#playlists-list').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-playlist-action]'); if (!button) return;
    const playlistId = Number(button.dataset.playlistId);
    if (button.dataset.playlistAction === 'close-edit') { editingPlaylistId = null; await loadPlaylists(); return; }
    if (button.dataset.playlistAction === 'edit') { editingPlaylistId = playlistId; await loadPlaylists(); $('.playlist-form input')?.focus(); return; }
    if (button.dataset.playlistAction === 'sync') {
      button.disabled = true;
      try { await api(`/api/playlists/${playlistId}/sync`, { method: 'POST' }); toast('Playlist sync added to the queue'); await Promise.all([loadJobs(false),loadPlaylists()]); }
      catch (error) { toast(error.message, 'error'); button.disabled = false; }
    }
  });
  loadJobs(false);
  loadPlaylists();
})();
