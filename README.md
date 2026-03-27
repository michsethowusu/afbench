# AfBench

AfBench (African Benchmarking) is an open-source policy analytics and benchmarking platform. It uses Large Language Models (LLMs) to automatically evaluate national policy documents against continental standards (such as the African Union's AFSCTP and ATQF frameworks) and generates interactive, visual alignment dashboards.

## Features

* **AI-Powered Evaluation:** Automatically grades uploaded PDFs and DOCX files against multi-level rubrics using the NVIDIA API (Llama-4-Maverick).
* **Dynamic Metadata Registry:** Easily add new sectors or frameworks by updating a single `metadata.csv` file—no code changes required.
* **Instant Dashboards:** Generates responsive bar charts, radar charts, and gauge visualizations for instant alignment feedback.
* **Persistent Knowledge Base:** Evaluated documents are saved to a local JSON database to build a permanent repository of national frameworks.

## Project Structure

* `app.py`: The Flask web server and application routes.
* `evaluator.py`: The core AI, document parsing, and visualization engine.
* `metadata.csv`: The master registry controlling the active framework modules.
* `criteria/`: Contains the CSV rubrics used by the AI for scoring.
* `frameworks/`: The dynamic local database where uploaded PDFs and `knowledge_base.json` are stored.

## Local Setup

**1. Clone the repository**
> git clone https://github.com/yourusername/afbench.git
> cd afbench

**2. Set up a virtual environment (Recommended)**
> python3 -m venv venv
> source venv/bin/activate  # On Windows use: venv\Scripts\activate

**3. Install dependencies**
> pip install -r requirements.txt

**4. Add your API Key**
Create a file named `.env` in the root directory and add your NVIDIA API key:
> NVIDIA_API_KEY="your_api_key_here"

**5. Run the application**
> python app.py

The application will be available at `http://127.0.0.1:5000`.

## Adding a New Framework

AfBench is designed to be a "no-code" engine for policy experts. To add a new framework (e.g., Healthcare Standards):
1. Create a new criteria rubric CSV and place it in the `criteria/` folder.
2. Add a new row to `metadata.csv` defining the Sector, Subdomain, Title, and file paths.
3. Restart the application. AfBench will automatically create the necessary folders and update the UI.

## License

This project is dual-licensed to protect the public-interest nature of the tool:

**1. Software & Code (Apache 2.0 + Commons Clause)**
The source code of AfBench is licensed under the Apache License 2.0, with the addition of the Commons Clause. 
* **You can:** Download, modify, distribute, and use this code for research, government, NGO, or personal public-good projects.
* **You cannot:** Sell this software, offer it as a paid commercial Software-as-a-Service (SaaS), or charge consulting fees exclusively for its use. 

**2. Data, Metadata & Rubrics (CC BY-NC-SA 4.0)**
The criteria CSV files, metadata registries, and the resulting `knowledge_base.json` databases are licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
* If you use or adapt our benchmarking rubrics for your own reports or tools, you must provide attribution, you may not use them for commercial purposes, and you must share your adaptations under the same terms.
