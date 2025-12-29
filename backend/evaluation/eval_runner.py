import os
import json
import time
import requests
import glob
from requests_toolbelt.multipart.encoder import MultipartEncoder

API_URL = "http://contract_api:8000" # Internal docker network URL or localhost if running locally? 
# If running locally, localhost:8000. If inside container, contract_api:8000.
# Let's assume this script runs LOCALLY, interacting with the running containers via localhost.
API_URL = "http://localhost:8000"

DATA_DIR = "backend/evaluation/data"
REPORT_PATH = "backend/evaluation/eval_report.json"

def load_ground_truth():
    with open(os.path.join(DATA_DIR, "ground_truth.json"), "r") as f:
        return json.load(f)

def upload_file(filepath):
    filename = os.path.basename(filepath)
    m = MultipartEncoder(fields={'file': (filename, open(filepath, 'rb'), 'application/pdf')})
    res = requests.post(f"{API_URL}/upload", data=m, headers={'Content-Type': m.content_type})
    if res.status_code != 200:
        print(f"Failed to upload {filename}: {res.text}")
        return None
    return res.json()["id"]

def wait_for_extraction(doc_id):
    for _ in range(20): # 20 attempts
        res = requests.get(f"{API_URL}/documents/{doc_id}/extraction")
        if res.status_code == 200:
            data = res.json()
            if data["status"] == "COMPLETED":
                return data["result"]
            if data["status"] == "FAILED":
                return None
        time.sleep(1)
    return None

def trigger_analysis(invoice_id):
    res = requests.post(f"{API_URL}/documents/{invoice_id}/analyze")
    return res.status_code == 200

def get_findings(invoice_id):
    res = requests.get(f"{API_URL}/documents/{invoice_id}/findings")
    if res.status_code == 200:
        return res.json()["findings"]
    return []

def run_eval():
    print("Starting Evaluation Run...")
    gt_data = load_ground_truth()
    
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_scenarios": len(gt_data),
        "metrics": {
            "extraction_f1": 0.0,
            "mismatch_accuracy": 0.0,
            "risk_recall": 0.0
        },
        "details": []
    }
    
    correct_mismatch = 0
    total_findings_checks = 0
    
    # Track mapping of scenario to uploaded IDs
    scenario_map = {}
    
    # 1. Upload All
    print("Uploading documents...")
    for item in gt_data:
        # Contract first to ensure it exists for analysis
        cont_path = os.path.join(DATA_DIR, item["contract_file"])
        cont_id = upload_file(cont_path)
        
        inv_path = os.path.join(DATA_DIR, item["invoice_file"])
        inv_id = upload_file(inv_path)
        
        scenario_map[item["scenario_id"]] = {"inv_id": inv_id, "cont_id": cont_id}
        
        # Wait for extraction (simple sequential)
        wait_for_extraction(cont_id)
        # We need contract processed before invoice analysis? 
        # Actually retrieval depends on Vector Store. 
        # Ingestion happens in worker. We should wait a bit.
    
    time.sleep(5) # Let ingestion settle
    
    # 2. Process Each Scenario
    print("Processing & Verifying...")
    for item in gt_data:
        s_id = item["scenario_id"]
        inv_id = scenario_map[s_id]["inv_id"]
        
        # Extraction Check (Invoice)
        inv_data = wait_for_extraction(inv_id)
        extraction_score = 0
        if inv_data:
            # Simple exact match on total (float)
            if abs(inv_data.get("total_amount", 0) - item["expected_invoice"]["total_amount"]) < 0.01:
                extraction_score = 1.0
            # Could check vendor name too
        
        # Analysis Check
        trigger_analysis(inv_id)
        time.sleep(2) # Wait for analysis to save findings
        findings = get_findings(inv_id)
        
        # Mismatch Logic Check
        # Expected mismatch?
        expect_mismatch = item["expected_findings"]["mismatch"]
        found_mismatch = any(f["finding_type"] == "term_mismatch" for f in findings)
        
        mismatch_correct = (expect_mismatch == found_mismatch)
        if mismatch_correct:
            correct_mismatch += 1
            
        results["details"].append({
            "scenario_id": s_id,
            "extraction_score": extraction_score,
            "mismatch_correct": mismatch_correct,
            "expected_mismatch": expect_mismatch,
            "found_mismatch": found_mismatch
        })
        
    # Compute aggregates
    results["metrics"]["extraction_f1"] = sum(d["extraction_score"] for d in results["details"]) / len(results["details"])
    results["metrics"]["mismatch_accuracy"] = correct_mismatch / len(results["details"])
    
    print(json.dumps(results, indent=2))
    
    with open(REPORT_PATH, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_eval()
