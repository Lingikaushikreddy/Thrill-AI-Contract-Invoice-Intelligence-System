import os
import json
import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime, timedelta

DATA_DIR = "backend/evaluation/data"
os.makedirs(DATA_DIR, exist_ok=True)

SCENARIOS = [
    {"id": 1, "type": "match", "vendor": "Vendor A", "inv_total": 1000, "inv_terms": "Net 30", "cont_terms": "Net 30", "risk": "Low"},
    {"id": 2, "type": "term_mismatch", "vendor": "Vendor B", "inv_total": 2000, "inv_terms": "Net 15", "cont_terms": "Net 30", "risk": "Low"},
    {"id": 3, "type": "risk_liability", "vendor": "Vendor C", "inv_total": 5000, "inv_terms": "Net 30", "cont_terms": "Net 30", "risk": "High", "clause": "Unlimited Liability"},
    {"id": 4, "type": "match", "vendor": "Vendor D", "inv_total": 1500, "inv_terms": "Net 45", "cont_terms": "Net 45", "risk": "Low"},
    {"id": 5, "type": "term_mismatch", "vendor": "Vendor E", "inv_total": 3000, "inv_terms": "Immediate", "cont_terms": "Net 60", "risk": "Low"},
]

ground_truth = []

def generate_invoice(path, scenario):
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"INVOICE - {scenario['vendor']}")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, 700, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    c.drawString(50, 680, f"Payment Terms: {scenario['inv_terms']}")
    
    c.drawString(50, 650, "Line Items:")
    c.drawString(50, 630, f"Service Fee ...... ${scenario['inv_total']:.2f}")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 600, f"Total: ${scenario['inv_total']:.2f}")
    c.save()

def generate_contract(path, scenario):
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"MASTER SERVICE AGREEMENT")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 730, f"Between Customer and {scenario['vendor']}")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 700, "1. Payment Terms")
    c.setFont("Helvetica", 12)
    c.drawString(50, 685, f"Customer shall pay undisputed invoices within {scenario['cont_terms']} days.")
    # Hack: normalize 'Net 30' to '30' or just keep text consistent? 
    # Let's make the text explicitly say the term.
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 650, "2. Liability")
    c.setFont("Helvetica", 12)
    if scenario.get("clause") == "Unlimited Liability":
        c.drawString(50, 635, "The Vendor's liability shall be unlimited.")
    else:
        c.drawString(50, 635, "The Vendor's liability shall be limited to 1x Fees.")
        
    c.save()

def main():
    print("Generating Gold Dataset...")
    for s in SCENARIOS:
        inv_name = f"invoice_{s['id']}_{s['vendor'].replace(' ', '')}.pdf"
        cont_name = f"contract_{s['id']}_{s['vendor'].replace(' ', '')}.pdf"
        
        generate_invoice(os.path.join(DATA_DIR, inv_name), s)
        generate_contract(os.path.join(DATA_DIR, cont_name), s)
        
        # Ground Truth Entry
        ground_truth.append({
            "scenario_id": s["id"],
            "invoice_file": inv_name,
            "contract_file": cont_name,
            "type": s["type"],
            "expected_invoice": {
                "vendor_name": s["vendor"],
                "total_amount": float(s["inv_total"]),
                "payment_terms": s["inv_terms"]
            },
            "expected_findings": {
                "mismatch": s["type"] == "term_mismatch",
                "risk_high": s.get("risk") == "High"
            }
        })
    
    with open(os.path.join(DATA_DIR, "ground_truth.json"), "w") as f:
        json.dump(ground_truth, f, indent=2)
    
    print(f"Generated {len(SCENARIOS)} pairs in {DATA_DIR}")

if __name__ == "__main__":
    main()
