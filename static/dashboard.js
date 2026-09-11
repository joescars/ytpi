(function () {
  const jobsBody = document.getElementById('jobs-body');
  const outputMeta = document.getElementById('output-meta');
  const outputPre = document.getElementById('job-output');
  const refreshBtn = document.getElementById('refresh-btn');
  const clearBtn = document.getElementById('clear-finished-btn');
  const playlistsList = document.getElementById('playlists-list');
  const activeJobSeed = document.body.dataset.defaultJobId || '';
  const notificationRegion = document.getElementById('notification-region');

  const kpiTotal = document.getElementById('kpi-total');
  const kpiActive = document.getElementById('kpi-active');
  const kpiErrors = document.getElementById('kpi-errors');
  const kpiDone = document.getElementById('kpi-done');

  let activeJobId = activeJobSeed || null;
  let outputTimer = null;
  let jobsFetchInFlight = false;
  let outputFetchInFlight = false;

  // Track pending actions to prevent duplicates
  const pendingActions = new Set();

  function showNotification(message, type = 'info', autoDismiss = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.setAttribute('role', 'alert');
    
    const content = document.createElement('div');
    content.className = 'content';
    content.textContent = message;
    
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'dismiss';
    dismiss.setAttribute('aria-label', 'Dismiss notification');
    dismiss.textContent = '×';
    dismiss.addEventListener('click', () => {
      removeNotification(notification);
    });
    
    notification.appendChild(content);
    notification.appendChild(dismiss);
    notificationRegion.appendChild(notification);
    
    if (autoDismiss > 0) {
      setTimeout(() => {
        removeNotification(notification);
      }, autoDismiss);
    }
    
    return notification;
  }

  function removeNotification(notification) {
    if (!notification.parentNode) return;
    notification.classList.add('exiting');
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }

  function showSuccess(message) {
    return showNotification(message, 'success', 5000);
  }

  function showError(message) {
    return showNotification(message, 'error', 8000);
  }

  function showWarning(message) {
    return showNotification(message, 'warning', 7000);
  }

  function pctNumber(value) {
    const num = Number(value ?? 0);
    if (Number.isNaN(num)) return 0;
    return Math.max(0, Math.min(100, num));
  }

  function statusClass(status) {
    return String(status || 'queued').toLowerCase();
  }

  function buildActionButton(job) {
    if (job.status === 'queued' || job.status === 'downloading') {
      return button('Cancel', 'btn btn-muted', 'cancel', job.id);
    }
    if (job.status === 'error' || job.status === 'cancelled') {
      return button('Retry', 'btn btn-primary', 'retry', job.id);
    }
    return null;
  }

  function button(label, className, action, jobId) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.dataset.action = action;
    btn.dataset.jobid = jobId;
    btn.textContent = label;
    return btn;
  }

  function createRow(job) {
    const tr = document.createElement('tr');

    const idTd = document.createElement('td');
    const idBtn = document.createElement('button');
    idBtn.type = 'button';
    idBtn.className = 'id-btn' + (activeJobId === job.id ? ' active' : '');
    idBtn.dataset.jobid = job.id;
    idBtn.textContent = String(job.id || '').slice(0, 8);
    idTd.appendChild(idBtn);

    const statusTd = document.createElement('td');
    const status = document.createElement('span');
    status.className = `state ${statusClass(job.status)}`;
    status.textContent = job.status || 'queued';
    statusTd.appendChild(status);

    const progressTd = document.createElement('td');
    const progressWrap = document.createElement('div');
    progressWrap.className = 'progress';
    progressWrap.setAttribute('role', 'progressbar');
    progressWrap.setAttribute('aria-valuemin', '0');
    progressWrap.setAttribute('aria-valuemax', '100');
    const progressFill = document.createElement('span');
    const percent = pctNumber(job.progress);
    progressWrap.setAttribute('aria-valuenow', String(percent));
    progressFill.style.width = `${percent}%`;
    progressWrap.appendChild(progressFill);
    const pctText = document.createElement('div');
    pctText.className = 'mono';
    pctText.style.fontSize = '0.72rem';
    pctText.textContent = `${percent.toFixed(1)}%`;
    progressTd.appendChild(progressWrap);
    progressTd.appendChild(pctText);

    const etaTd = document.createElement('td');
    etaTd.textContent = job.eta || '-';

    const speedTd = document.createElement('td');
    speedTd.textContent = job.speed || '-';

    const urlTd = document.createElement('td');
    urlTd.className = 'url-cell';
    const link = document.createElement('a');
    link.href = job.url || '#';
    link.rel = 'noopener';
    link.target = '_blank';
    link.textContent = job.url || '';
    urlTd.appendChild(link);

    const errorTd = document.createElement('td');
    errorTd.className = 'error-cell';
    errorTd.textContent = job.error || '';

    const actionsTd = document.createElement('td');
    const actionBtn = buildActionButton(job);
    if (actionBtn) {
      actionsTd.appendChild(actionBtn);
    }

    tr.append(idTd, statusTd, progressTd, etaTd, speedTd, urlTd, errorTd, actionsTd);
    return tr;
  }

  function renderJobs(items) {
    jobsBody.innerHTML = '';
    if (!items.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 8;
      td.className = 'empty';
      td.textContent = 'No jobs yet. Queue one from the home page.';
      tr.appendChild(td);
      jobsBody.appendChild(tr);
      updateKpis(items);
      return;
    }

    const fragment = document.createDocumentFragment();
    items.forEach(job => fragment.appendChild(createRow(job)));
    jobsBody.appendChild(fragment);
    updateKpis(items);

    if (!activeJobId && items.length) {
      openJob(items[0].id);
    }
  }

  function updateKpis(items) {
    const active = items.filter(j => j.status === 'queued' || j.status === 'downloading').length;
    const done = items.filter(j => j.status === 'finished').length;
    const errors = items.filter(j => j.status === 'error').length;
    kpiTotal.textContent = String(items.length);
    kpiActive.textContent = String(active);
    kpiDone.textContent = String(done);
    kpiErrors.textContent = String(errors);
  }

  async function request(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  }

  const api = {
    jobs: () => request('/api/status?limit=200'),
    playlists: () => request('/api/playlists'),
    output: (jobId) => request(`/job_output/${jobId}`),
    cancel: (jobId) => request(`/jobs/${jobId}/cancel`, { method: 'POST' }),
    retry: (jobId) => request(`/jobs/${jobId}/retry`, { method: 'POST' }),
    clearFinished: () => request('/clear-finished', { method: 'POST' }),
  };

  async function fetchPlaylists() {
    try {
      const data = await api.playlists();
      playlistsList.innerHTML = '';
      if (!data.items.length) {
        playlistsList.innerHTML = '<p class="empty">No playlists saved yet.</p>';
        return;
      }
      data.items.forEach(playlist => {
        const card = document.createElement('div');
        card.className = 'playlist-card surface';
        card.dataset.playlistId = playlist.id;
        
        // Format last synced time
        let lastSyncedText = 'Never';
        if (playlist.last_synced_at) {
          const syncedDate = new Date(playlist.last_synced_at);
          lastSyncedText = syncedDate.toLocaleDateString() + ' ' + syncedDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        }
        
        // Determine mode (audio/video)
        const mode = playlist.audio_only ? 'Audio' : 'Video';
        const format = playlist.audio_only ? playlist.audio_format : playlist.quality;
        
        // Create card content
        card.innerHTML = `
          <div class="playlist-header">
            <div class="playlist-title">
              <a href="${playlist.url}" target="_blank" rel="noopener" title="${playlist.url}" class="playlist-name">${playlist.name || 'Untitled playlist'}</a>
              <button class="btn btn-small btn-muted edit-btn" data-playlist-id="${playlist.id}">Edit</button>
            </div>
            <div class="playlist-mode">${mode} • ${format}</div>
          </div>
          <div class="playlist-details">
            <div class="playlist-detail"><span class="detail-label">Category:</span> <span class="detail-value">${playlist.category || 'default'}</span></div>
            <div class="playlist-detail"><span class="detail-label">Last synced:</span> <span class="detail-value">${lastSyncedText}</span></div>
          </div>
          <div class="playlist-actions">
            <button class="btn btn-primary sync-btn" data-playlist-id="${playlist.id}">Sync Now</button>
          </div>
          <div class="playlist-edit-form" style="display: none;">
            <form class="edit-form" data-playlist-id="${playlist.id}">
              <div class="form-group">
                <label for="category-${playlist.id}">Category:</label>
                <input type="text" id="category-${playlist.id}" name="category" value="${playlist.category || ''}" placeholder="Category name">
              </div>
              <div class="form-group">
                <label for="quality-${playlist.id}">${playlist.audio_only ? 'Audio Format:' : 'Quality:'}</label>
                <select id="quality-${playlist.id}" name="${playlist.audio_only ? 'audio_format' : 'quality'}">
                  ${playlist.audio_only ? 
                    '<option value="mp3"' + (playlist.audio_format === 'mp3' ? ' selected' : '') + '>MP3</option>' +
                    '<option value="wav"' + (playlist.audio_format === 'wav' ? ' selected' : '') + '>WAV</option>' :
                    '<option value="max"' + (playlist.quality === 'max' ? ' selected' : '') + '>Max</option>' +
                    '<option value="2160"' + (playlist.quality === '2160' ? ' selected' : '') + '>2160p</option>' +
                    '<option value="1440"' + (playlist.quality === '1440' ? ' selected' : '') + '>1440p</option>' +
                    '<option value="1080"' + (playlist.quality === '1080' ? ' selected' : '') + '>1080p</option>' +
                    '<option value="720"' + (playlist.quality === '720' ? ' selected' : '') + '>720p</option>' +
                    '<option value="480"' + (playlist.quality === '480' ? ' selected' : '') + '>480p</option>'
                  }
                </select>
              </div>
              <div class="form-group">
                <label for="audio-only-${playlist.id}">Audio Only:</label>
                <input type="checkbox" id="audio-only-${playlist.id}" name="audio_only" ${playlist.audio_only ? 'checked' : ''}>
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-muted cancel-edit-btn">Cancel</button>
                <button type="submit" class="btn btn-primary save-btn">Save</button>
              </div>
            </form>
          </div>
        `;
        
        playlistsList.appendChild(card);
      });
      
      // Add event listeners for edit/sync buttons
      setupPlaylistEventListeners();
    } catch (_e) {
      playlistsList.innerHTML = '<p class="empty">Playlists unavailable.</p>';
    }
  }
  
  function setupPlaylistEventListeners() {
    // Sync buttons
    document.querySelectorAll('.sync-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const button = e.target;
        const playlistId = button.dataset.playlistId;
        button.disabled = true;
        button.textContent = 'Syncing...';
        
        try { 
          const data = await request(`/api/playlists/${playlistId}/sync`, { method: 'POST' });
          showSuccess(`Playlist sync started. Job ID: ${data.job_id}`);
          await fetchJobs();
          await fetchPlaylists();
          // Try to focus on the new job
          if (data.job_id) {
            setTimeout(() => {
              openJob(data.job_id);
              // Also scroll to it if possible
              const jobButton = document.querySelector(`.id-btn[data-jobid="${data.job_id}"]`);
              if (jobButton) {
                jobButton.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              }
            }, 500);
          }
        } catch (error) {
          console.error('Playlist sync failed:', error);
          if (error.message.includes('429') || error.message.includes('queue')) {
            showError('Queue is full. Please wait for current jobs to finish.');
          } else {
            showError(`Failed to sync playlist: ${error.message || 'Unknown error'}`);
          }
          button.disabled = false;
          button.textContent = 'Sync Now';
        }
      });
    });
    
    // Edit buttons
    document.querySelectorAll('.edit-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const playlistId = btn.dataset.playlistId;
        const card = btn.closest('.playlist-card');
        const editForm = card.querySelector('.playlist-edit-form');
        const details = card.querySelector('.playlist-details');
        const actions = card.querySelector('.playlist-actions');
        
        // Show edit form, hide details and actions
        editForm.style.display = 'block';
        details.style.display = 'none';
        actions.style.display = 'none';
        btn.style.display = 'none';
      });
    });
    
    // Cancel edit buttons
    document.querySelectorAll('.cancel-edit-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const form = btn.closest('.edit-form');
        const card = form.closest('.playlist-card');
        const editForm = card.querySelector('.playlist-edit-form');
        const details = card.querySelector('.playlist-details');
        const actions = card.querySelector('.playlist-actions');
        const editBtn = card.querySelector('.edit-btn');
        
        // Hide edit form, show details and actions
        editForm.style.display = 'none';
        details.style.display = 'block';
        actions.style.display = 'block';
        editBtn.style.display = 'inline-block';
      });
    });
    
    // Save/edit form submissions
    document.querySelectorAll('.edit-form').forEach(form => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const playlistId = form.dataset.playlistId;
        const saveBtn = form.querySelector('.save-btn');
        const card = form.closest('.playlist-card');
        
        const formData = new FormData(form);
        const data = {
          category: formData.get('category') || '',
          audio_only: formData.get('audio_only') === 'on',
        };
        
        // Get quality or audio_format based on checkbox state
        if (data.audio_only) {
          data.audio_format = formData.get('audio_format') || 'mp3';
        } else {
          data.quality = formData.get('quality') || 'max';
        }
        
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
        
        try {
          const response = await request(`/api/playlists/${playlistId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
          
          showSuccess('Playlist settings updated');
          await fetchPlaylists(); // Refresh to show updated values
        } catch (error) {
          console.error('Failed to update playlist:', error);
          showError(`Failed to update: ${error.message || 'Unknown error'}`);
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save';
        }
      });
    });
  }

  async function fetchJobs() {
    if (jobsFetchInFlight || document.hidden) return;
    jobsFetchInFlight = true;
    try {
      const data = await api.jobs();
      const items = data.items || [];
      renderJobs(items);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      // Don't show notification for every polling failure, only log it
      // We'll show a persistent warning if multiple consecutive failures occur
      if (jobsBody.querySelector('.empty')) {
        // Only show if we have no jobs displayed
        jobsBody.innerHTML = '<tr><td colspan="8" class="empty">Failed to load jobs. Connection issue?</td></tr>';
      }
    } finally {
      jobsFetchInFlight = false;
    }
  }

  async function fetchOutput(jobId) {
    if (!jobId || outputFetchInFlight || document.hidden) return;
    outputFetchInFlight = true;
    try {
      const data = await api.output(jobId);
      const pct = pctNumber(data.progress).toFixed(1);
      outputMeta.textContent = `Job ${jobId} | ${data.status || 'unknown'} | ${pct}% | ETA ${data.eta || '-'} | ${data.speed || '-'}`;
      outputPre.textContent = data.output || '(No output yet)';
      outputPre.scrollTop = outputPre.scrollHeight;
    } catch (_e) {
      outputMeta.textContent = `Job ${jobId} | output unavailable`;
    } finally {
      outputFetchInFlight = false;
    }
  }

  function openJob(jobId) {
    activeJobId = jobId;
    document.querySelectorAll('.id-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.jobid === jobId);
    });
    fetchOutput(jobId);
    if (outputTimer) clearInterval(outputTimer);
    outputTimer = setInterval(() => fetchOutput(jobId), 2000);
  }

  jobsBody.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const idButton = target.closest('.id-btn');
    if (idButton) {
      openJob(idButton.dataset.jobid || '');
      return;
    }

    const actionButton = target.closest('button[data-action]');
    if (!actionButton) return;

    const action = actionButton.dataset.action;
    const jobId = actionButton.dataset.jobid;
    if (!jobId) return;

    // Prevent duplicate actions
    const actionKey = `${action}:${jobId}`;
    if (pendingActions.has(actionKey)) return;
    
    // Set button to pending state
    actionButton.disabled = true;
    const originalText = actionButton.textContent;
    actionButton.textContent = action === 'cancel' ? 'Cancelling...' : 'Retrying...';
    pendingActions.add(actionKey);

    try {
      let data;
      if (action === 'cancel') {
        data = await api.cancel(jobId);
        showSuccess(data.message || 'Job cancelled successfully');
      }
      if (action === 'retry') {
        data = await api.retry(jobId);
        showSuccess(data.message || 'Job re-queued successfully');
      }
      await fetchJobs();
      if (activeJobId === jobId) {
        await fetchOutput(jobId);
      }
    } catch (error) {
      console.error('Action failed:', error);
      showError(`Failed to ${action} job: ${error.message || 'Unknown error'}`);
      // Restore button after error
      actionButton.disabled = false;
      actionButton.textContent = originalText;
      pendingActions.delete(actionKey);
      return;
    } finally {
      // Button will be recreated by fetchJobs, so no need to restore here
      pendingActions.delete(actionKey);
    }
  });

  clearBtn.addEventListener('click', async () => {
    if (!window.confirm('Clear finished/error/cancelled jobs?')) return;
    
    // Set button to pending state
    clearBtn.disabled = true;
    const originalText = clearBtn.textContent;
    clearBtn.textContent = 'Clearing...';
    
    try {
      const data = await api.clearFinished();
      showSuccess(data.message || 'Cleared finished jobs');
      outputMeta.textContent = data.message;
      await fetchJobs();
    } catch (error) {
      console.error('Clear failed:', error);
      showError(`Failed to clear finished jobs: ${error.message || 'Unknown error'}`);
      outputMeta.textContent = 'Failed to clear finished jobs';
    } finally {
      clearBtn.disabled = false;
      clearBtn.textContent = originalText;
    }
  });

  refreshBtn.addEventListener('click', async () => {
    // Set button to pending state
    refreshBtn.disabled = true;
    const originalText = refreshBtn.textContent;
    refreshBtn.textContent = 'Refreshing...';
    
    try {
      await fetchJobs();
      showSuccess('Dashboard refreshed');
    } catch (error) {
      console.error('Refresh failed:', error);
      showError('Failed to refresh dashboard');
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = originalText;
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      fetchJobs();
      if (activeJobId) fetchOutput(activeJobId);
    }
  });

  window.addEventListener('load', async () => {
    await fetchJobs();
    await fetchPlaylists();
    if (activeJobId) openJob(activeJobId);
    setInterval(fetchJobs, 3000);
  });
})();
