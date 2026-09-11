(function () {
  console.log('dashboard.js starting');
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

  // Connection state tracking
  const connectionIndicator = document.getElementById('connection-indicator');
  const connectionStatusText = document.getElementById('connection-status-text');
  const lastUpdatedTime = document.getElementById('last-updated-time');
  const connectionWarning = document.getElementById('connection-warning');
  const connectionWarningText = document.getElementById('connection-warning-text');
  
  let lastSuccessfulUpdate = Date.now();
  let consecutiveFailures = 0;
  let maxBackoffInterval = 30000; // 30 seconds max
  let currentPollInterval = 3000; // Start with 3 seconds
  let jobsPollIntervalId = null;
  let playlistsPollIntervalId = null;
  let connectionWarningShown = false;

  let activeJobId = activeJobSeed || null;
  let outputTimer = null;
  let jobsFetchInFlight = false;
  let outputFetchInFlight = false;

  // Track pending actions to prevent duplicates
  const pendingActions = new Set();

  // API helpers
  const api = {
    jobs: () => request('/api/status?limit=200'),
    output: (jobId) => request(`/job_output/${jobId}`),
    cancel: (jobId) => request(`/jobs/${jobId}/cancel`, { method: 'POST' }),
    retry: (jobId) => request(`/jobs/${jobId}/retry`, { method: 'POST' }),
    clearFinished: () => request('/clear-finished', { method: 'POST' }),
    playlists: () => request('/api/playlists'),
    syncPlaylist: (playlistId) => request(`/api/playlists/${playlistId}/sync`, { method: 'POST' }),
  };

  async function request(path, options = {}) {
    const response = await fetch(path, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  function updateConnectionState(success) {
    if (success) {
      consecutiveFailures = 0;
      lastSuccessfulUpdate = Date.now();
      updateLastUpdatedTime();
      
      if (connectionWarningShown) {
        // Connection recovered
        connectionWarning.style.display = 'none';
        connectionWarningShown = false;
        connectionIndicator.style.backgroundColor = 'var(--success)';
        connectionStatusText.textContent = 'Connected';
        showNotification('Connection restored', 'success', 3000);
      }
    } else {
      consecutiveFailures++;
      
      // Show warning after 2 consecutive failures
      if (consecutiveFailures >= 2 && !connectionWarningShown) {
        connectionWarning.style.display = 'flex';
        connectionWarningShown = true;
        connectionIndicator.style.backgroundColor = 'var(--warning)';
        connectionStatusText.textContent = 'Connection issues';
        connectionWarningText.textContent = `Dashboard data may be stale (${consecutiveFailures} failures). Retrying...`;
        showNotification('Connection issue detected', 'warning', 5000);
      }
      
      // Update warning text for repeated failures
      if (connectionWarningShown) {
        connectionWarningText.textContent = `Dashboard data may be stale (${consecutiveFailures} failures). Retrying...`;
      }
      
      // Implement backoff: increase interval up to max
      currentPollInterval = Math.min(maxBackoffInterval, 3000 * Math.pow(1.5, consecutiveFailures - 1));
      
      // Restart polling with new interval
      restartPolling();
    }
  }

  function updateLastUpdatedTime() {
    const now = Date.now();
    const diff = Math.floor((now - lastSuccessfulUpdate) / 1000);
    
    if (diff < 10) {
      lastUpdatedTime.textContent = 'Last updated: just now';
    } else if (diff < 60) {
      lastUpdatedTime.textContent = `Last updated: ${diff} seconds ago`;
    } else if (diff < 3600) {
      const minutes = Math.floor(diff / 60);
      lastUpdatedTime.textContent = `Last updated: ${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else {
      const hours = Math.floor(diff / 3600);
      lastUpdatedTime.textContent = `Last updated: ${hours} hour${hours !== 1 ? 's' : ''} ago`;
    }
  }

  function restartPolling() {
    // Clear existing intervals
    if (jobsPollIntervalId) {
      clearInterval(jobsPollIntervalId);
      jobsPollIntervalId = null;
    }
    if (playlistsPollIntervalId) {
      clearInterval(playlistsPollIntervalId);
      playlistsPollIntervalId = null;
    }
    
    // Only restart if page is visible
    if (!document.hidden) {
      jobsPollIntervalId = setInterval(fetchJobs, currentPollInterval);
      // Playlists poll less frequently
      playlistsPollIntervalId = setInterval(fetchPlaylists, Math.max(currentPollInterval * 2, 10000));
    }
  }

  function setupConnectionWarningDismiss() {
    const dismissBtn = connectionWarning?.querySelector('.dismiss');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => {
        connectionWarning.style.display = 'none';
      });
    }
  }

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
    btn.textContent = label;
    btn.dataset.action = action;
    btn.dataset.jobid = jobId;
    return btn;
  }

  function renderJobs(jobs) {
    if (!jobs.length) {
      jobsBody.innerHTML = '<tr><td colspan="8" class="empty">No jobs in history</td></tr>';
      updateKpis({ total: 0, active: 0, errors: 0, done: 0 });
      return;
    }

    const fragment = document.createDocumentFragment();
    let total = 0, active = 0, errors = 0, done = 0;

    jobs.forEach(job => {
      total++;
      if (job.status === 'queued' || job.status === 'downloading') active++;
      else if (job.status === 'error') errors++;
      else if (job.status === 'finished') done++;

      const tr = document.createElement('tr');
      tr.dataset.jobid = job.id;
      tr.dataset.status = job.status;

      // ID column with clickable button
      const idTd = document.createElement('td');
      const idButton = document.createElement('button');
      idButton.type = 'button';
      idButton.className = 'id-btn';
      if (job.id === activeJobId) idButton.classList.add('active');
      idButton.dataset.jobid = job.id;
      idButton.textContent = job.id.slice(0, 8);
      idButton.title = `Select job ${job.id}`;
      idTd.appendChild(idButton);

      // Status column
      const statusTd = document.createElement('td');
      statusTd.className = `status ${statusClass(job.status)}`;
      statusTd.textContent = job.status;

      // Progress column with accessible progress bar
      const progressTd = document.createElement('td');
      const progressWrap = document.createElement('div');
      progressWrap.className = 'progress';
      progressWrap.setAttribute('role', 'progressbar');
      progressWrap.setAttribute('aria-valuemin', '0');
      progressWrap.setAttribute('aria-valuemax', '100');
      progressWrap.setAttribute('aria-valuenow', String(pctNumber(job.progress)));
      progressWrap.setAttribute('aria-label', `Progress for job ${job.id}`);
      
      const progressFill = document.createElement('span');
      const percent = pctNumber(job.progress);
      progressFill.style.width = `${percent}%`;
      progressWrap.appendChild(progressFill);
      
      const pctText = document.createElement('span');
      pctText.className = 'pct-text';
      pctText.textContent = `${percent.toFixed(1)}%`;
      if (job.progress_stage && job.progress_stage !== 'Preparing') {
        pctText.title = job.progress_stage;
      }
      
      progressTd.appendChild(progressWrap);
      progressTd.appendChild(pctText);

      // ETA column
      const etaTd = document.createElement('td');
      etaTd.textContent = job.eta || '-';

      // Speed column
      const speedTd = document.createElement('td');
      speedTd.textContent = job.speed || '-';

      // URL column with title
      const urlTd = document.createElement('td');
      const urlLink = document.createElement('a');
      urlLink.href = job.url;
      urlLink.target = '_blank';
      urlLink.rel = 'noopener noreferrer';
      urlLink.textContent = new URL(job.url).hostname;
      urlLink.title = job.url;
      urlTd.appendChild(urlLink);

      // Error column (empty unless error status)
      const errorTd = document.createElement('td');
      if (job.error) {
        errorTd.textContent = job.error;
        errorTd.title = job.error;
      }

      // Action column
      const actionsTd = document.createElement('td');
      const actionButton = buildActionButton(job);
      if (actionButton) actionsTd.appendChild(actionButton);

      tr.append(idTd, statusTd, progressTd, etaTd, speedTd, urlTd, errorTd, actionsTd);
      fragment.appendChild(tr);
    });

    jobsBody.innerHTML = '';
    jobsBody.appendChild(fragment);
    updateKpis({ total, active, errors, done });
  }

  function updateKpis({ total, active, errors, done }) {
    kpiTotal.textContent = String(total);
    kpiActive.textContent = String(active);
    kpiErrors.textContent = String(errors);
    kpiDone.textContent = String(done);
  }

  async function fetchJobs() {
    if (jobsFetchInFlight || document.hidden) return;
    jobsFetchInFlight = true;
    try {
      const data = await api.jobs();
      const items = data.items || [];
      renderJobs(items);
      updateConnectionState(true); // Mark as successful
    } catch (error) {
      updateConnectionState(false); // Mark as failed
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
      let metaText = `Job ${jobId} | ${data.status || 'unknown'} | ${pct}%`;
      if (data.eta) metaText += ` | ETA ${data.eta}`;
      if (data.speed) metaText += ` | ${data.speed}`;
      if (data.progress_stage && data.progress_stage !== 'Preparing') {
        metaText += ` | ${data.progress_stage}`;
      }
      outputMeta.textContent = metaText;
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
      } else if (action === 'retry') {
        data = await api.retry(jobId);
        showSuccess(data.message || 'Job re-queued successfully');
      }
      await fetchJobs();
    } catch (error) {
      console.error(`Job ${action} failed:`, error);
      showError(`Failed to ${action} job: ${error.message || 'Unknown error'}`);
    } finally {
      actionButton.disabled = false;
      actionButton.textContent = originalText;
      pendingActions.delete(actionKey);
    }
  });

  // Clear finished jobs
  clearBtn.addEventListener('click', async () => {
    if (!window.confirm('Clear completed history? This will remove finished, error, and cancelled job records but will NOT delete downloaded files.')) return;
    
    // Set button to pending state
    clearBtn.disabled = true;
    const originalText = clearBtn.textContent;
    clearBtn.textContent = 'Clearing...';
    
    try {
      const data = await api.clearFinished();
      showSuccess(data.message || 'Cleared completed history');
      outputMeta.textContent = data.message;
      await fetchJobs();
    } catch (error) {
      console.error('Clear failed:', error);
      showError(`Failed to clear history: ${error.message || 'Unknown error'}`);
      outputMeta.textContent = 'Failed to clear history';
    } finally {
      clearBtn.disabled = false;
      clearBtn.textContent = originalText;
    }
  });

  // Refresh button
  refreshBtn.addEventListener('click', async () => {
    // Set button to pending state
    refreshBtn.disabled = true;
    const originalText = refreshBtn.textContent;
    refreshBtn.textContent = 'Refreshing...';
    
    try {
      await Promise.all([fetchJobs(), fetchPlaylists()]);
      showSuccess('Dashboard refreshed');
    } catch (error) {
      console.error('Refresh failed:', error);
      showError('Failed to refresh dashboard');
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.textContent = originalText;
    }
  });

  // Playlist functions (simplified for this example)
  async function fetchPlaylists() {
    try {
      const data = await api.playlists();
      const items = data.items || [];
      // Simple render for playlists
      if (items.length === 0) {
        playlistsList.innerHTML = '<p class="empty">No saved playlists</p>';
      } else {
        playlistsList.innerHTML = items.map(playlist => `
          <div class="playlist-card surface">
            <div class="playlist-details">
              <h3>${playlist.name}</h3>
              <p>Category: ${playlist.category} | Quality: ${playlist.quality}</p>
              <button class="btn btn-primary sync-btn" data-playlist-id="${playlist.id}">Sync Now</button>
            </div>
          </div>
        `).join('');
        
        // Add sync button handlers
        document.querySelectorAll('.sync-btn').forEach(btn => {
          btn.addEventListener('click', async (e) => {
            const playlistId = btn.dataset.playlistId;
            btn.disabled = true;
            btn.textContent = 'Syncing...';
            try {
              const data = await api.syncPlaylist(playlistId);
              showSuccess(`Playlist sync started: job ${data.job_id}`);
              await fetchJobs();
            } catch (error) {
              console.error('Sync failed:', error);
              showError(`Sync failed: ${error.message || 'Unknown error'}`);
            } finally {
              btn.disabled = false;
              btn.textContent = 'Sync Now';
            }
          });
        });
      }
    } catch (error) {
      console.error('Failed to fetch playlists:', error);
      // Don't show error for playlist fetch failures
    }
  }

  // Visibility change handling
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      restartPolling();
    }
  });

  // Setup and initialization
  (async () => {
    setupConnectionWarningDismiss();
    updateLastUpdatedTime(); // Initial update
    
    await fetchJobs();
    await fetchPlaylists();
    if (activeJobId) openJob(activeJobId);
    restartPolling();
  })();
})();