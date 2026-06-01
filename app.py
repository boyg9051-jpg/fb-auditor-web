import sys
import re
import time
import asyncio
import aiohttp
from flask import Flask, render_template_string, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

HTML_DESIGN = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise FB Auditor Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
        .btn-success { background-color: #42b72a; border: none; font-weight: 600; }
        .badge-live { background-color: #d1e7dd; color: #0f5132; }
        .badge-dead { background-color: #f8d7da; color: #842029; }
        textarea { resize: none; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <div class="card p-4 mb-4">
                    <h2 class="text-center text-primary mb-2">📊 Enterprise FB Auditor v1.0</h2>
                    <p class="text-muted text-center mb-4">Bulk Facebook Profile Status & Metric Identifier</p>
                    
                    <div class="mb-3">
                        <label class="form-label fw-bold">ফ্রি সেশন কুকি (Facebook Cookie - ঐচ্ছিক):</label>
                        <input type="text" id="fbCookie" class="form-control" placeholder="c_user=xxxx; xs=xxxx; fr=xxxx...">
                    </div>

                    <div class="mb-3">
                        <label class="form-label fw-bold">ফেসবুক প্রোফাইল লিংকসমূহ (প্রতি লাইনে একটি):</label>
                        <textarea id="linksInput" class="form-control" rows="6" placeholder="https://www.facebook.com/username"></textarea>
                    </div>
                    
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <span class="fw-bold text-secondary" id="linkCount">মোট লিংক: 0</span>
                        <button id="startBtn" class="btn btn-success px-4 py-2" onclick="processBulkCheck()">🚀 অডিট শুরু করুন</button>
                    </div>
                </div>

                <div class="card p-4 d-none" id="resultCard">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h4>🔍 লাইভ অডিট রিপোর্ট</h4>
                        <button class="btn btn-outline-primary btn-sm" onclick="exportToCSV()">📥 Export to CSV</button>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover align-middle">
                            <thead class="table-light">
                                <tr>
                                    <th>#</th>
                                    <th>প্রোফাইল লিংক</th>
                                    <th>স্ট্যাটাস</th>
                                    <th>মেট্রিকস (ফ্রেন্ডস/ফলোয়ার)</th>
                                </tr>
                            </thead>
                            <tbody id="resultsTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const input = document.getElementById('linksInput');
        const countLabel = document.getElementById('linkCount');
        let currentResults = [];
        
        input.addEventListener('input', () => {
            const links = input.value.split('\\n').filter(line => line.trim() !== '');
            countLabel.innerText = `মোট লিংক: ${links.length}`;
        });

        async function processBulkCheck() {
            const links = input.value.split('\\n').filter(line => line.trim() !== '');
            if(links.length === 0) { alert('দয়া করে অন্তত একটি লিংক দিন!'); return; }

            const btn = document.getElementById('startBtn');
            const cookie = document.getElementById('fbCookie').value;
            const resultCard = document.getElementById('resultCard');
            const tbody = document.getElementById('resultsTableBody');
            
            btn.disabled = true;
            resultCard.classList.remove('d-none');
            tbody.innerHTML = `<tr><td colspan="4" class="text-center py-4"><b>🤖 হাই-স্পিড অডিট চলছে... অনুগ্রহ করে অপেক্ষা করুন।</b></td></tr>`;

            try {
                const response = await fetch('/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ links: links, cookie: cookie })
                });
                currentResults = await response.json();
                
                tbody.innerHTML = '';
                currentResults.forEach((item, index) => {
                    const badgeClass = item.status.includes('Live') ? 'badge-live' : 'badge-dead';
                    tbody.innerHTML += `
                        <tr>
                            <td>${index + 1}</td>
                            <td><a href="${item.url}" target="_blank">${item.url}</a></td>
                            <td><span class="badge ${badgeClass} p-2">${item.status}</span></td>
                            <td class="fw-bold">${item.metrics}</td>
                        </tr>
                    `;
                });
            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger py-4"><b>❌ সার্ভার ত্রুটি!</b></td></tr>`;
            }
            btn.disabled = false;
        }

        function exportToCSV() {
            let csv = 'No,URL,Status,Metrics\\n';
            currentResults.forEach((item, index) => {
                csv += `"${index+1}","${item.url}","${item.status}","${item.metrics}"\\n`;
            });
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.setAttribute("download", "fb_audit_report.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    </script>
</body>
</html>
"""

async def async_check_profile(session, url, cookie_str):
    if "www.facebook.com" in url:
        url = url.replace("www.facebook.com", "mbasic.facebook.com")
    elif "m.facebook.com" in url:
        url = url.replace("m.facebook.com", "mbasic.facebook.com")
    elif "mbasic.facebook.com" not in url and url.strip():
        if not url.startswith("http"):
            url = "https://mbasic.facebook.com/" + url

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    if cookie_str.strip():
        headers['Cookie'] = cookie_str.strip()

    try:
        async with session.get(url, headers=headers, timeout=12) as response:
            if response.status == 404:
                return {"status": "Dead / Disabled", "metrics": "N/A"}
            
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            page_text = soup.get_text()
            page_text_lower = page_text.lower()
            page_title = soup.title.string.lower() if soup.title else ""

            error_keywords = ["page isn't available", "content not found", "not found", "লিংকটি হয়তো ভেঙে গেছে", "এই পৃষ্ঠাটি উপলভ্য নয়"]
            if any(kw in page_text_lower or kw in page_title for kw in error_keywords):
                return {"status": "Dead / Disabled", "metrics": "N/A"}

            friends_match = re.search(r'([\d.,\dKkMমববিি]+)\s*(friends|friend|mutual friends|বন্ধু|পারস্পরিক বন্ধু)', page_text, re.IGNORECASE)
            followers_match = re.search(r'([\d.,\dKkMমববিি]+)\s*(followers|follower|ফলোয়ার)', page_text, re.IGNORECASE)

            if friends_match:
                return {"status": "✅ Live", "metrics": f"Friends: {friends_match.group(1)}"}
            elif followers_match:
                return {"status": "✅ Live", "metrics": f"Followers: {followers_match.group(1)}"}
            else:
                return {"status": "✅ Live", "metrics": "0 Friends / Profile Locked"}
    except Exception:
        return {"status": "Rate Limited / Error", "metrics": "Retry"}

@app.route('/')
def index():
    return render_template_string(HTML_DESIGN)

@app.route('/audit', methods=['POST'])
def audit_links():
    data = request.get_json()
    links = data.get('links', [])
    cookie = data.get('cookie', '')
    
    async def run_bulk():
        async with aiohttp.ClientSession() as session:
            tasks = [async_check_profile(session, url, cookie) for url in links if url.strip()]
            return await asyncio.gather(*tasks)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async_results = loop.run_until_complete(run_bulk())
    loop.close()

    final_results = []
    idx = 0
    for url in links:
        if url.strip():
            final_results.append({
                "url": url,
                "status": async_results[idx]["status"],
                "metrics": async_results[idx]["metrics"]
            })
            idx += 1
    return jsonify(final_results)

if __name__ == '__main__':
    # রেন্ডার সার্ভারের জন্য লোকাল অ্যাপ রান কনফিগারেশন
    app.run()