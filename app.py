import threading
import uuid
import subprocess
import os
import queue
from flask import Flask, request, jsonify, render_template, abort, redirect, url_for

app = Flask(__name__)
download_queue = queue.Queue()
jobs = {}

# Allowed LAN prefixes
ALLOWED_PREFIXES = ("157.", "127.", "192.168.", "10.", "172.")

def is_local(addr):
    return any(addr.startswith(pref) for pref in ALLOWED_PREFIXES)

@app.before_request
def restrict_to_local():
    client = request.remote_addr or ""
    if not is_local(client):
        abort(403)

def worker():
    while True:
        job_id = download_queue.get()
        job = jobs[job_id]
        job['status'] = 'downloading'
        job['output'] = ''
        try:
            category = job.get('category') or ''
            category_folder = f"./downloads/{category}" if category else "./downloads"
            os.makedirs(category_folder, exist_ok=True)
            # Check if URL is a playlist
            if 'playlist?list=' in job['url']:
                cmd = ['yt-dlp', '--ffmpeg-location', '/usr/bin/ffmpeg', '-t', 'mp4', '-P', category_folder, '--embed-metadata',
                       '-o', '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s', job['url']]
            else:
                cmd = ['yt-dlp', '--ffmpeg-location', '/usr/bin/ffmpeg', '-t', 'mp4', '-P', category_folder, '--embed-metadata',
                       '-o', '%(title)s.%(ext)s', job['url']]
            # Use subprocess.Popen for live output
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output_lines = []
            for line in proc.stdout:
                output_lines.append(line)
                job['output'] = ''.join(output_lines)[-8000:]  # Keep last 8k chars
            proc.wait()
            if proc.returncode == 0:
                job['status'] = 'finished'
            else:
                job['status'] = 'error'
                job['error'] = job['output'][-1000:]  # Show last 1k chars as error
        except Exception as e:
            job['status'] = 'error'
            job['error'] = str(e)
        finally:
            download_queue.task_done()

# Start background thread
threading.Thread(target=worker, daemon=True).start()

@app.route('/download', methods=['POST'])
def enqueue_download():
    # Support both JSON and form submissions
    if request.is_json:
        data = request.get_json(force=True)
        urls_input = data.get('url') or data.get('urls')
        category = data.get('category', '').strip() if data.get('category') else ''
    else:
        urls_input = request.form.get('url') or request.form.get('urls')
        category = request.form.get('category', '').strip() if request.form.get('category') else ''
    if not urls_input:
        if request.is_json:
            return jsonify({'error': 'Missing url or urls'}), 400
        else:
            return render_template('index.html', error='Missing url or urls'), 400
    # Normalize to list
    if isinstance(urls_input, str):
        urls = [urls_input.strip()]
    elif isinstance(urls_input, list):
        urls = [url.strip() for url in urls_input if url.strip()]
    else:
        if request.is_json:
            return jsonify({'error': 'url must be a string or array of strings'}), 400
        else:
            return render_template('index.html', error='url must be a string or array of strings'), 400
    if not urls:
        if request.is_json:
            return jsonify({'error': 'No valid URLs provided'}), 400
        else:
            return render_template('index.html', error='No valid URLs provided'), 400
    job_ids = []
    for url in urls:
        job_id = str(uuid.uuid4())
        jobs[job_id] = {'url': url, 'status': 'queued', 'category': category}
        download_queue.put(job_id)
        job_ids.append(job_id)
    # Redirect to dashboard for form submissions
    if not request.is_json:
        return redirect(url_for('status'))
    # Return single job_id for backward compatibility, or array for multiple URLs
    if len(job_ids) == 1:
        return jsonify({'job_id': job_ids[0]}), 202
    else:
        return jsonify({'job_ids': job_ids}), 202

@app.route('/status', methods=['GET'])
def status():
    # Find the default job to show (active or most recent)
    default_job_id = None
    if jobs:
        # First try to find an active (downloading/queued) job
        for job_id, job in jobs.items():
            if job['status'] in ['downloading', 'queued']:
                default_job_id = job_id
                break
        
        # If no active job, get the most recent one (last added)
        if not default_job_id:
            default_job_id = list(jobs.keys())[-1]
    
    return render_template('dashboard.html', jobs=jobs, default_job_id=default_job_id)

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify(jobs)

@app.route('/job_output/<job_id>')
def job_output(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'output': job.get('output', '')})

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Listen on all interfaces but only serve local clients
    app.run(host='0.0.0.0', port=7434)