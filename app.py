import threading
import uuid
import subprocess
import os
import queue
from flask import Flask, request, jsonify, render_template, abort

app = Flask(__name__)
download_queue = queue.Queue()
jobs = {}

# Allowed LAN prefixes
ALLOWED_PREFIXES = ("127.", "192.168.", "10.", "172.")

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
        try:
            category = job.get('category') or ''
            category_folder = f"./downloads/{category}" if category else "./downloads"
            os.makedirs(category_folder, exist_ok=True)
            # Check if URL is a playlist
            if 'playlist?list=' in job['url']:
                # Playlist command - download all videos in playlist with organized output
                cmd = ['yt-dlp', '--ffmpeg-location', '/usr/bin/ffmpeg', '-t', 'mp4', '-P', category_folder, '--embed-metadata',
                       '-o', '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s', job['url']]
            else:
                # Single video command
                cmd = ['yt-dlp', '--ffmpeg-location', '/usr/bin/ffmpeg', '-t', 'mp4', '-P', category_folder, '--embed-metadata',
                       '-o', '%(title)s.%(ext)s', job['url']]
            
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0:
                job['status'] = 'finished'
            else:
                job['status'] = 'error'
                job['error'] = proc.stderr
        except Exception as e:
            job['status'] = 'error'
            job['error'] = str(e)
        finally:
            download_queue.task_done()

# Start background thread
threading.Thread(target=worker, daemon=True).start()

@app.route('/download', methods=['POST'])
def enqueue_download():
    data = request.get_json(force=True)
    
    # Support both single URL and array of URLs
    urls_input = data.get('url') or data.get('urls')
    category = data.get('category', '').strip() if data.get('category') else ''
    if not urls_input:
        return jsonify({'error': 'Missing url or urls'}), 400
    
    # Normalize to list
    if isinstance(urls_input, str):
        urls = [urls_input.strip()]
    elif isinstance(urls_input, list):
        urls = [url.strip() for url in urls_input if url.strip()]
    else:
        return jsonify({'error': 'url must be a string or array of strings'}), 400
    
    if not urls:
        return jsonify({'error': 'No valid URLs provided'}), 400
    
    job_ids = []
    for url in urls:
        job_id = str(uuid.uuid4())
        jobs[job_id] = {'url': url, 'status': 'queued', 'category': category}
        download_queue.put(job_id)
        job_ids.append(job_id)
    
    # Return single job_id for backward compatibility, or array for multiple URLs
    if len(job_ids) == 1:
        return jsonify({'job_id': job_ids[0]}), 202
    else:
        return jsonify({'job_ids': job_ids}), 202

@app.route('/status', methods=['GET'])
def status():
    return render_template('dashboard.html', jobs=jobs)

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify(jobs)

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # Listen on all interfaces but only serve local clients
    app.run(host='0.0.0.0', port=7434)