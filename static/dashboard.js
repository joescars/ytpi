(function () {
  const jobsBody = document.getElementById('jobs-body');
  const outputMeta = document.getElementById('output-meta');
  const outputPre = document.getElementById('job-output');
  const refreshBtn = document.getElementById('refresh-btn');
  const clearBtn = document.getElementById('clear-finished-btn');
  const activeJobSeed = document.body.dataset.defaultJobId || '';

  const kpiTotal = document.getElementById('kpi-total');
  const kpiActive = document.getElementById('kpi-active');
  const kpiErrors = document.getElementById('kpi-errors');
  const kpiDone = document.getElementById('kpi-done');

  let activeJobId = activeJobSeed || null;
  let outputTimer = null;
  let jobsFetchInFlight = false;
  let outputFetchInFlight = false;

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
    output: (jobId) => request(`/job_output/${jobId}`),
    cancel: (jobId) => request(`/jobs/${jobId}/cancel`, { method: 'POST' }),
    retry: (jobId) => request(`/jobs/${jobId}/retry`, { method: 'POST' }),
    clearFinished: () => request('/clear-finished', { method: 'POST' }),
  };

  async function fetchJobs() {
    if (jobsFetchInFlight || document.hidden) return;
    jobsFetchInFlight = true;
    try {
      const data = await api.jobs();
      const items = data.items || [];
      renderJobs(items);
    } catch (_e) {
      // Keep UI responsive even if poll occasionally fails.
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

    try {
      if (action === 'cancel') {
        await api.cancel(jobId);
      }
      if (action === 'retry') {
        await api.retry(jobId);
      }
      await fetchJobs();
      if (activeJobId === jobId) {
        await fetchOutput(jobId);
      }
    } catch (_e) {
      // keep controls non-blocking
    }
  });

  clearBtn.addEventListener('click', async () => {
    if (!window.confirm('Clear finished/error/cancelled jobs?')) return;
    try {
      const data = await api.clearFinished();
      outputMeta.textContent = data.message;
      await fetchJobs();
    } catch (_e) {
      outputMeta.textContent = 'Failed to clear finished jobs';
    }
  });

  refreshBtn.addEventListener('click', fetchJobs);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      fetchJobs();
      if (activeJobId) fetchOutput(activeJobId);
    }
  });

  window.addEventListener('load', async () => {
    await fetchJobs();
    if (activeJobId) openJob(activeJobId);
    setInterval(fetchJobs, 3000);
  });
})();
