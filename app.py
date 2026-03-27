from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
import markdown
import evaluator

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Dynamically ensure all official folders defined in metadata exist
for fw_code, meta in evaluator.FRAMEWORK_META.items():
    os.makedirs(meta["folder"], exist_ok=True)

@app.route('/')
@app.route('/country/<country_name>')
def dashboard(country_name=None):
    kb = evaluator.load_knowledge_base()
    countries = sorted(kb["countries"].keys())
    
    country_data = None
    if country_name:
        country_data = evaluator.get_dynamic_country_results(country_name)

    return render_template('index.html', 
                           countries=countries, 
                           kb=kb, 
                           selected_country=country_data,
                           meta=evaluator.FRAMEWORK_META)

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
    
    # NEW: Dynamically determine the sector folder for new uploads
    meta = evaluator.FRAMEWORK_META.get(fw_code)
    sector_folder = meta['sector'].lower().replace(' ', '_') if meta else 'general'
    
    upload_dir = os.path.join("new_uploads", sector_folder)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    # Run the evaluation
    df, summary, bar_html, radar_html, gauge_html, percent, status, country = evaluator.evaluate_framework(
        file_path, fw_code, filename=filename
    )

    if status != "Success":
        return jsonify({"status": "Error", "message": summary}), 500

    return jsonify({
        "status": "Success",
        "country": country,
        "summary": summary, # HTML is now pre-formatted in evaluator
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
