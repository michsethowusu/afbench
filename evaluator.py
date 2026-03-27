import os
import requests
import json
import csv
import pandas as pd
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import base64
import PyPDF2
from docx import Document
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ---------- Configuration & API ----------
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-4-maverick-17b-128e-instruct"
KNOWLEDGE_DB_FILE = "./frameworks/knowledge_base.json"
METADATA_FILE = "./metadata.csv"

# ==========================================
# 🧠 DYNAMIC METADATA LOADER
# ==========================================
def load_framework_metadata():
    meta_dict = {}
    if not os.path.exists(METADATA_FILE):
        return meta_dict
        
    with open(METADATA_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row['FrameworkCode'].strip()
            meta_dict[code] = {
                "sector": row['Sector'].strip(),
                "subdomain": row['Subdomain'].strip(), # NEW: Reads the subdomain
                "title": row['Title'].strip(),
                "folder": row['Folder'].strip(),
                "criteria_file": row['CriteriaFile'].strip(),
                "color": row['Color'].strip()
            }
            os.makedirs(row['Folder'].strip(), exist_ok=True)
    return meta_dict

FRAMEWORK_META = load_framework_metadata()

def load_criteria_from_csv(filepath):
    criteria = {}
    if not os.path.exists(filepath): return criteria
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['CriterionID']
            criteria[cid] = {
                "short_label": row['ShortLabel'], "section": row['Section'],
                "levels": {0: row['Level0'], 1: row['Level1'], 2: row['Level2'], 3: row['Level3'], 4: row['Level4'], 5: row['Level5']}
            }
    return criteria

CRITERIA_CACHE = {}
for fw_code, meta in FRAMEWORK_META.items():
    CRITERIA_CACHE[fw_code] = load_criteria_from_csv(meta["criteria_file"])

# ---------- LLM LOGIC ----------
def extract_text_from_file(file_path):
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join(page.extract_text() for page in reader.pages)
            return re.sub(r'\s+', ' ', text)
    elif file_path.endswith('.docx'):
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()

def detect_country(document_text, sector, subdomain):
    if not NVIDIA_API_KEY: return "Unknown Country"
    
    # Reconstructs EXACT Gradio string using your metadata: "teacher education framework"
    prompt = f"""Identify which African country this {subdomain} framework document belongs to.
    Look for country names, national bodies (e.g., "Kenya National Qualifications Framework", "Ghana Education Service").
    Return ONLY the country name (e.g., "Kenya", "Ghana", "Nigeria"). If uncertain, return "Unknown".
    
    DOCUMENT TEXT (first 3000 characters):
    {document_text[:3000]}
    
    Country:"""
    
    try:
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 50}
        response = requests.post(NVIDIA_URL, headers=headers, json=payload)
        if response.status_code == 200:
            country = response.json()["choices"][0]["message"]["content"].strip()
            return country.replace("The ", "").replace("the ", "").replace(".", "").replace("\n", " ").strip() or "Unknown Country"
    except: pass
    return "Unknown Country"

def build_evaluation_prompt(document_text, criteria_dict, framework_name, subdomain):
    prompt_parts = []
    
    # EXACT Gradio strings restored:
    prompt_parts.append(f"You are evaluating a national {subdomain} framework against the {framework_name}. ")
    prompt_parts.append("For each criterion below, select the SINGLE best description (0-5) that matches the document content. ")
    prompt_parts.append("Return ONLY a JSON object where keys are criterion IDs (e.g., 'S1' or 'Q1') and values are integers 0-5. No explanations.\n")
    
    for cid, data in criteria_dict.items():
        prompt_parts.append(f"\n{cid} - {data['short_label']}:")
        for level, desc in data['levels'].items():
            prompt_parts.append(f"  [{level}] {desc}")
            
    prompt_parts.append(f"\n\nDOCUMENT TEXT:\n{document_text[:20000]}\n")
    
    # EXACT Gradio JSON hints restored:
    prompt_parts.append("\nRespond with valid JSON only: {\"S1\": 4, \"S2\": 3, ...} or {\"Q1\": 5, \"Q2\": 4, ...}")
    
    return "\n".join(prompt_parts)

def call_nvidia_llm(prompt):
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 2000}
    response = requests.post(NVIDIA_URL, headers=headers, json=payload)
    if response.status_code != 200: raise Exception(f"API error: {response.text}")
    
    content = response.json()["choices"][0]["message"]["content"].strip()
    
    # Safely parsing the JSON block
    json_marker = "```json"
    code_marker = "```"
    
    if json_marker in content: 
        content = content.split(json_marker)[1].split(code_marker)[0]
    elif code_marker in content: 
        content = content.split(code_marker)[1].split(code_marker)[0]
    
    try: return json.loads(content.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match: return json.loads(match.group())
        raise Exception("Could not parse JSON.")

# ---------- CHARTS ENGINE ----------
def generate_charts(df, country, framework_name):
    labels = df["Label"].tolist()
    scores = df["Score"].tolist()
    values = np.array(scores)

    plt.figure(figsize=(14, 9))
    colors = ['#b71c1c' if v == 0 else '#d32f2f' if v == 1 else '#f57c00' if v == 2 else '#fbc02d' if v == 3 else '#689f38' if v == 4 else '#2e7d32' for v in values]
    bars = plt.barh(labels, values, color=colors, edgecolor='black', linewidth=0.5)
    plt.xlim(0, 5)
    plt.xlabel("Score (0-5)", fontsize=12, fontweight='bold')
    plt.title(f"{country}\n{framework_name} Alignment", fontsize=16, fontweight='bold', pad=20)
    plt.axvline(x=3, color='gray', linestyle='--', alpha=0.5)
    for i, (bar, score) in enumerate(zip(bars, values)):
        plt.text(score + 0.1, bar.get_y() + bar.get_height()/2, f"{score}", va='center', fontweight='bold', fontsize=11)
    plt.tight_layout()
    bar_buf = BytesIO()
    plt.savefig(bar_buf, format='png', dpi=150, bbox_inches='tight')
    bar_img = base64.b64encode(bar_buf.getvalue()).decode()
    plt.close()

    N = len(labels)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    values_radar = list(values) + [values[0]]
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    ax.plot(angles, values_radar, 'o-', linewidth=2.5, color='#1565c0')
    ax.fill(angles, values_radar, alpha=0.25, color='#1565c0')
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=10)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(['1', '2', '3', '4', '5'], color="grey", size=8)
    ax.set_title("Alignment Profile", size=16, fontweight='bold', pad=20)
    radar_buf = BytesIO()
    plt.savefig(radar_buf, format='png', dpi=150, bbox_inches='tight')
    radar_img = base64.b64encode(radar_buf.getvalue()).decode()
    plt.close()

    total_score = sum(values)
    max_score = len(values) * 5
    percent = (total_score / max_score) * 100 if max_score > 0 else 0
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.barh([0], [100], color='#e0e0e0', height=0.5, edgecolor='black')
    color = '#2e7d32' if percent >= 90 else '#689f38' if percent >= 75 else '#fbc02d' if percent >= 60 else '#f57c00' if percent >= 40 else '#d32f2f'
    ax.barh([0], [percent], color=color, height=0.5, edgecolor='black')
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(['0%', '25%', '50%', '75%', '100%'], fontsize=11)
    ax.set_yticks([])
    ax.set_title(f"{percent:.1f}% Alignment", fontsize=18, fontweight='bold', pad=15)
    gauge_buf = BytesIO()
    plt.savefig(gauge_buf, format='png', dpi=150, bbox_inches='tight')
    gauge_img = base64.b64encode(gauge_buf.getvalue()).decode()
    plt.close()

    return bar_img, radar_img, gauge_img, percent

# ---------- KNOWLEDGE BASE MANAGER ----------
def load_knowledge_base():
    if os.path.exists(KNOWLEDGE_DB_FILE):
        try:
            with open(KNOWLEDGE_DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"countries": {}, "processed_docs": {}}

def save_knowledge_base(kb):
    os.makedirs(os.path.dirname(KNOWLEDGE_DB_FILE), exist_ok=True)
    with open(KNOWLEDGE_DB_FILE, 'w', encoding='utf-8') as f: json.dump(kb, f, indent=2)

# ---------- EVALUATION WRAPPERS ----------
def evaluate_framework(file_path, fw_code, save_to_db=False, filename=None):
    if not NVIDIA_API_KEY: 
        return pd.DataFrame(), "❌ NVIDIA_API_KEY not set.", "", "", "", 0, "Error", "Unknown Country"
    
    meta = FRAMEWORK_META.get(fw_code)
    if not meta: return pd.DataFrame(), "Invalid framework type.", "", "", "", 0, "Error", "Unknown Country"
    
    criteria_dict = CRITERIA_CACHE[fw_code]
    framework_name = meta["title"]
    sector = meta["sector"]
    subdomain = meta["subdomain"]
    
    try: text = extract_text_from_file(file_path)
    except Exception as e: return pd.DataFrame(), f"Error: {e}", "", "", "", 0, "Error", "Unknown Country"

    # Pass BOTH sector and subdomain dynamically
    country = detect_country(text, sector, subdomain)
    try:
        prompt = build_evaluation_prompt(text, criteria_dict, framework_name, subdomain)
        results = call_nvidia_llm(prompt)
    except Exception as e: return pd.DataFrame(), f"AI error: {e}", "", "", "", 0, "Error", country

    rows = []
    for cid, data in criteria_dict.items():
        score = int(results.get(cid, 0))
        rows.append({"ID": cid, "Label": data['short_label'], "Section": data['section'], "Score": score, "Level": data['levels'][score]})
    df = pd.DataFrame(rows)
    
    bar_img, radar_img, gauge_img, percent = generate_charts(df, country, framework_name)
    strong = df[df['Score'] >= 4]['Label'].tolist()
    weak = df[df['Score'] <= 2]['Label'].tolist()
    
    if save_to_db and filename and country != "Unknown Country":
        kb = load_knowledge_base()
        if country not in kb["countries"]: 
            kb["countries"][country] = {}
        kb["countries"][country][fw_code] = {
            "filename": filename,
            "overall_score": percent,
            "scores": results, 
        }
        if "processed_docs" not in kb: 
            kb["processed_docs"] = {}
        kb["processed_docs"][f"{fw_code}_{filename}"] = {"mtime": os.path.getmtime(file_path)}
        save_knowledge_base(kb)
    
    summary_md = f"""
### **{country} - {framework_name} Evaluation Report**

**Overall Alignment: {percent:.1f}%**

**Scale:** 0 = Non-existent | 1 = Weak | 2 = Developing | 3 = Moderate | 4 = Strong | 5 = Excellent

**🟢 Strengths ({len(strong)}):** {', '.join(strong) if strong else 'None identified'}

**🔴 Priority Areas ({len(weak)}):** {', '.join(weak) if weak else 'None - all criteria adequate'}
    """
    
    return df, summary_md, f'<img src="data:image/png;base64,{bar_img}" style="width:100%; max-width:900px;">', \
           f'<img src="data:image/png;base64,{radar_img}" style="width:100%; max-width:600px;">', \
           f'<img src="data:image/png;base64,{gauge_img}" style="width:100%; max-width:800px;">', \
           percent, "Success", country

def scan_folders_for_documents():
    docs = []
    for fw_code, meta in FRAMEWORK_META.items():
        folder = meta["folder"]
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.lower().endswith('.pdf'):
                    docs.append({"filename": f, "fw": fw_code, "path": os.path.join(folder, f)})
    return docs

def build_knowledge_base_from_documents():
    kb = load_knowledge_base()
    docs = scan_folders_for_documents()
    if not NVIDIA_API_KEY: return kb
    
    for doc in docs:
        doc_id = f"{doc['fw']}_{doc['filename']}"
        if doc_id in kb.get("processed_docs", {}) and kb["processed_docs"][doc_id].get("mtime", 0) == os.path.getmtime(doc["path"]):
            continue 
            
        try:
            print(f"Scanning: {doc['filename']} for {doc['fw']}...")
            text = extract_text_from_file(doc["path"])
            
            c_dict = CRITERIA_CACHE.get(doc["fw"])
            if not c_dict: continue
            
            meta = FRAMEWORK_META[doc["fw"]]
            sector = meta["sector"]
            subdomain = meta["subdomain"]
            fw_title = meta["title"]
            
            country = detect_country(text, sector, subdomain)
            prompt = build_evaluation_prompt(text, c_dict, fw_title, subdomain)
            results = call_nvidia_llm(prompt)
            scores = [int(results.get(cid, 0)) for cid in c_dict.keys()]
            
            if country not in kb["countries"]: kb["countries"][country] = {}
            kb["countries"][country][doc["fw"]] = {
                "filename": doc["filename"],
                "overall_score": round((sum(scores) / (len(c_dict) * 5)) * 100, 1) if c_dict else 0,
                "scores": results, 
            }
            if "processed_docs" not in kb: kb["processed_docs"] = {}
            kb["processed_docs"][doc_id] = {"mtime": os.path.getmtime(doc["path"])}
        except Exception as e: print(f"Error on {doc['filename']}: {e}")
            
    save_knowledge_base(kb)
    return kb

def get_dynamic_country_results(country):
    kb = load_knowledge_base()
    if country not in kb["countries"]: return None
    
    results = {}
    for fw_code, fw_data in kb["countries"][country].items():
        if fw_code not in FRAMEWORK_META: continue
        saved_scores = fw_data.get("scores")
        if not saved_scores: continue
            
        meta = FRAMEWORK_META[fw_code]
        c_dict = CRITERIA_CACHE[fw_code]
        
        rows = []
        for cid, data in c_dict.items():
            score = int(saved_scores.get(cid, 0))
            rows.append({"ID": cid, "Label": data['short_label'], "Section": data['section'], "Score": score, "Level": data['levels'][score]})
        
        df = pd.DataFrame(rows)
        bar_img, radar_img, gauge_img, percent = generate_charts(df, country, meta["title"])
        
        results[fw_code] = {
            "meta": meta,
            "bar": f'<img src="data:image/png;base64,{bar_img}" class="img-fluid">',
            "radar": f'<img src="data:image/png;base64,{radar_img}" class="img-fluid">',
            "gauge": f'<img src="data:image/png;base64,{gauge_img}" class="img-fluid">',
            "table": df.to_html(classes="table table-striped table-bordered small", index=False)
        }
    if not results: return None
    return {"name": country, "frameworks": results}
