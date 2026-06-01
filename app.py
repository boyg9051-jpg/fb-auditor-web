import sys
import re
import time
import os
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
    <title>Enterprise FB Auditor Tool v1.4</title>
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
                    <h2 class="text-center text-primary mb-2">📊 Enterprise FB Auditor v1.4 (Bypass Edition)</h2>
                    <p class="text-muted text-center mb-4">Direct Endpoint Security Bypass Core</p>
                    
                    <div class="mb-3">
                        <label class="form-label fw-bold">ফেসবুক সেশন কুকি (Facebook Cookie):</label>
                        <textarea id="fbCookie" class="form-control" rows="2" placeholder="c_user=xxxx; xs=xxxx; fr=xxxx..."></textarea>
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
            tbody.innerHTML = `<tr><td colspan="4" class="text-center py-4"><b>🤖 সিকিউরিটি বাইপাস মেকানিজমে স্ক্র্যাপিং চলছে... অনুগ্রহ করে অপেক্ষা করুন।</b></td></tr>`;

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
    # প্রোফাইল আইডি এক্সট্রাক্ট করা (id= এক্সপ্রেশন অথবা ইউজারনেম বের করার জন্য)
    profile_id = ""
    id_match = re.search(r'id=(\d+)', url)
    if id_match:
        profile_id = id_match.group(1)
    else:
        username_match = re.search(r'facebook\.com/([^/?]+)', url)
        if username_match:
            profile_id = username_match.group(1)

    if not profile_id:
        return {"status": "Dead / Invalid Link", "metrics": "N/A"}

    # ফেসবুকের ডাইরেক্ট গ্রাফিকাল মোবাইল এন্ডপয়েন্ট ব্যবহার করা যা রিডাইরেকশন বাইপাস করে
    target_url = f"https://mbasic.facebook.com/{profile_id}/friends" if id_match else f"https://mbasic.facebook.com/{profile_id}?v=info"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; Trident/7.0; rv:11.0) like Gecko',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    if cookie_str.strip():
        headers['Cookie'] = cookie_str.strip()

    try:
        async with session.get(target_url, headers=headers, timeout=15, allow_redirects=True) as response:
            final_url = str(response.url)
            if "login" in final_url or "checkpoint" in final_url:
                return {"status": "Dead / Disabled", "metrics": "N/A (Cookie Expired)"}

            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            page_text = soup.get_text()
            page_text_lower = page_text.lower()

            # একদম নিখুঁতভাবে ফ্রেন্ডলিস্টের ভেতরের টেক্সট ডাম্প অ্যানালাইসিস
            friends_count = "0"
            
            # মেথড ১: ফ্রেন্ডস ডিরেক্টরি সাব-লিংক থেকে সংখ্যা গোনা
            all_matches = re.findall(r'([\d.,\dKkMমববিি]+)\s*(friends|friend|mutual friends|বন্ধু)', page_text, re.IGNORECASE)
            if all_matches:
                # সবচেয়ে বড় বা প্রথম সংখ্যাটি নেওয়া
                friends_count = all_matches[0][0]
                return {"status": "✅ Live", "metrics": f"Friends: {friends_count}"}

            # মেথড ২: ফলোয়ার সংখ্যা ব্যাকআপ হিসেবে চেক
            followers_match = re.search(r'([\d.,\dKkMমববিি]+)\s*(followers|follower|ফলোয়ার)', page_text, re.IGNORECASE)
            if followers_match:
                return {"status": "✅ Live", "metrics": f"Followers: {followers_match.group(1)}"}

            # মেথড ৩: যদি কোনো সংখ্যা না পাওয়া যায় কিন্তু আইডি সচল থাকে
            if "content not found" in page_text_lower or "page isn't available" in page_text_lower:
                return {"status": "Dead / Disabled", "metrics": "N/A"}
            
            # যদি টাইটেলে নাম থাকে কিন্তু ফ্রেন্ডস সংখ্যা না দেখায়, তার মানে প্রাইভেসি লক করা
            title_text = soup.title.string if soup.title else ""
            if title_text and "facebook" not in title_text.lower():
                return {"status": "✅ Live", "metrics": "Profile Live (Friends List Hidden)"}

            return {"status": "✅ Live", "metrics": "0 Friends / Metric Hidden"}

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)