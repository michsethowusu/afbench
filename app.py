from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
import markdown
import evaluator

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

for fw_code, meta in evaluator.FRAMEWORK_META.items():
    os.makedirs(meta["folder"], exist_ok=True)

def get_nav_data():
    """Helper to build the sidebar and home page data structure"""
    kb = evaluator.load_knowledge_base()
    nav_sectors = {}
    for fw_code, meta in evaluator.FRAMEWORK_META.items():
        sec = meta['sector']
        if sec not in nav_sectors:
            nav_sectors[sec] = []
        # Count how many countries have been evaluated for this framework
        count = sum(1 for c, data in kb.get("countries", {}).items() if fw_code in data)
        nav_sectors[sec].append({
            "code": fw_code,
            "title": meta['title'],
            "color": meta.get('color', 'dark'),
            "count": count
        })
    return nav_sectors

@app.route('/')
def dashboard():
    return render_template('index.html', view_mode='home', nav_sectors=get_nav_data())

@app.route('/framework/<fw_code>')
def framework_view(fw_code):
    ranking_data = evaluator.get_framework_ranking(fw_code)
    return render_template('index.html', view_mode='framework', nav_sectors=get_nav_data(), ranking_data=ranking_data)

@app.route('/report/<fw_code>/<country>')
def report_view(fw_code, country):
    report_data = evaluator.get_single_report(fw_code, country)
    return render_template('index.html', view_mode='report', nav_sectors=get_nav_data(), report_data=report_data)

@app.route('/evaluate', methods=['GET'])
def evaluate_page():
    return render_template('evaluate.html', meta=evaluator.FRAMEWORK_META)

@app.route('/api/evaluate', methods=['POST'])
def run_evaluation():
    fw_code = request.form.get('framework_type') 
    
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({"status": "Error", "message": "No file uploaded."}), 400
        
    file = request.files['file']
    filename = secure_filename(file.filename)
    
    meta = evaluator.FRAMEWORK_META.get(fw_code)
    sector_folder = meta['sector'].lower().replace(' ', '_') if meta else 'general'
    
    upload_dir = os.path.join("new_uploads", sector_folder)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    df, summary, bar_html, radar_html, gauge_html, percent, status, country = evaluator.evaluate_framework(
        file_path, fw_code, filename=filename
    )

    if status != "Success":
        return jsonify({"status": "Error", "message": summary}), 500

    return jsonify({
        "status": "Success",
        "country": country,
        "summary": summary,
        "percent": percent,
        "table": df.to_html(classes="table table-striped table-bordered small", index=False),
        "charts": {"bar": bar_html, "radar": radar_html, "gauge": gauge_html}
    })

@app.route('/api/refresh_kb', methods=['POST'])
def refresh_knowledge_base():
    try:
        evaluator.build_knowledge_base_from_documents() 
        return jsonify({"status": "Success"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
