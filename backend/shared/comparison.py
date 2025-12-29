from typing import Dict, Any, TypedDict, Optional, List
import logging
import json
import os
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from shared.models import Document, Finding as DBFinding
from shared.schemas import Finding, FindingType, FindingSeverity, InvoiceSchema, ContractSchema

logger = logging.getLogger(__name__)

class ComparisonState(TypedDict):
    invoice_id: int
    invoice_data: Dict[str, Any]
    contract_id: Optional[int]
    contract_data: Optional[Dict[str, Any]]
    findings: List[Finding]

class ComparisonGraph:
    def __init__(self, db: Session):
        self.db = db
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mistral_key = os.getenv("MISTRAL_API_KEY")
        
        if self.mistral_key:
            self.llm = ChatMistralAI(model="mistral-small-latest", temperature=0)
        elif self.openai_key:
            self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            self.llm = None

    def retrieve_contract(self, state: ComparisonState):
        logger.info("Node: Retrieve Contract")
        invoice_data = state["invoice_data"]
        vendor_name = invoice_data.get("vendor_name", {}).get("value")
        
        if not vendor_name:
            logger.warning("No vendor name in invoice data")
            return {"contract_id": None}

        # Naive Search: Find any contract where party_b (Vendor) roughly matches vendor_name
        # In prod, use Vector Search or specific metadata columns
        # Fetch all contracts
        contracts = self.db.query(Document).filter(
            Document.extraction_result.isnot(None)
            # In a real system we would filter by doc_type inside JSON, but specific SQL required for that
        ).all()
        
        best_match = None
        for doc in contracts:
            if not doc.extraction_result or doc.extraction_result.get("doc_type") != "contract":
                continue
            
            data = doc.extraction_result.get("data", {})
            party_a = data.get("party_a", {}).get("value", "")
            party_b = data.get("party_b", {}).get("value", "")
            
            if (vendor_name.lower() in party_a.lower()) or (vendor_name.lower() in party_b.lower()):
                best_match = doc
                break
        
        if best_match:
            logger.info(f"Found related contract: {best_match.id}")
            return {
                "contract_id": best_match.id,
                "contract_data": best_match.extraction_result.get("data")
            }
        
        return {"contract_id": None}

    def compare_terms(self, state: ComparisonState):
        logger.info("Node: Compare Terms")
        findings = []
        
        if not state["contract_id"]:
            findings.append(Finding(
                finding_type=FindingType.MISSING_PO, # abusing enum slightly to mean Missing Contract
                severity=FindingSeverity.HIGH,
                description="No matching contract found for this vendor.",
                recommendation="Upload a contract for this vendor."
            ))
            return {"findings": findings}

        inv_terms_node = state["invoice_data"].get("payment_terms") # Invoice extraction might not have this schema yet
        # InvoiceSchema usually has date/total. Let's assume user asked for custom fields or we check total/date.
        
        # Payment Terms from Contract
        cont_terms_node = state["contract_data"].get("payment_terms", {})
        count_terms_val = cont_terms_node.get("value")
        
        # Invoices usually imply terms via Due Date vs Invoice Date.
        # But if Invoice has explicit "Payment Terms" text extracted (e.g. "Net 15"), we compare.
        # IF InvoiceSchema DOES NOT have 'payment_terms', we should extract it ad-hoc or Check Invoice Date vs Due Date.
        # For this MVP, let's assume we extract "payment_terms" or generic "terms" from invoice text if possible.
        # BUT our InvoiceSchema (pydantic) currently is: vendor, date, number, total, items.
        # So we can't easily compare "Payment Terms" string unless we add it to InvoiceSchema.
        
        # Let's check Total Amount logic instead for a sure win, 
        # OR assume we updated InvoiceSchema.
        # **Decision**: Update InvoiceSchema to include `payment_terms`. 
        # FOR NOW: I will check Invoice Total vs Contract "Liability Cap" if available? No that's for total spend.
        
        # Let's stick to the plan: "Verify Mismatch Detection on Bad Invoice" with "Net 15".
        # I need to update InvoiceSchema to capture `payment_terms`.
        # I will do that as a prerequisite step.
        pass # Handle in next logic block
        
        # Use LLM to compare if we have data
        inv_terms_val = state["invoice_data"].get("payment_terms", {}).get("value")
        
        if inv_terms_val and count_terms_val and self.llm:
            prompt = ChatPromptTemplate.from_template(
                """Compare the following payment terms. Are they consistent?
                If no, explain why briefly.
                
                Invoice Terms: {inv_terms}
                Contract Terms: {cont_terms}
                
                Return JSON: {{"consistent": bool, "explanation": str}}"""
            )
            chain = prompt | self.llm
            res = chain.invoke({"inv_terms": inv_terms_val, "cont_terms": count_terms_val})
            try:
                # Naive parse
                content = res.content.replace("```json", "").replace("```", "")
                parsed = json.loads(content)
                if not parsed["consistent"]:
                    findings.append(Finding(
                        finding_type=FindingType.TERM_MISMATCH,
                        severity=FindingSeverity.HIGH,
                        description=f"Invoice terms '{inv_terms_val}' conflict with Contract '{count_terms_val}'. {parsed['explanation']}",
                        evidence={
                            "invoice_evidence": state["invoice_data"].get("payment_terms"),
                            "contract_evidence": cont_terms_node
                        }
                    ))
            except Exception as e:
                logger.error(f"Comparison LLM failed: {e}")

        elif not self.llm and inv_terms_val and count_terms_val:
            # Fallback for Mock Mode / No-LLM
            # Simple string equality or containment check
            # Normalize strings roughly
            norm_inv = str(inv_terms_val).lower().strip()
            norm_cont = str(count_terms_val).lower().strip()
            
            if norm_inv != norm_cont:
                 findings.append(Finding(
                    finding_type=FindingType.TERM_MISMATCH,
                    severity=FindingSeverity.HIGH,
                    description=f"Invoice terms '{inv_terms_val}' do not match Contract '{count_terms_val}'. (Mock Comparison)",
                    evidence={
                        "invoice_evidence": state["invoice_data"].get("payment_terms"),
                        "contract_evidence": cont_terms_node
                    }
                ))

        return {"findings": findings}

    def build_graph(self):
        workflow = StateGraph(ComparisonState)
        workflow.add_node("retrieve", self.retrieve_contract)
        workflow.add_node("compare", self.compare_terms)
        
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "compare")
        workflow.add_edge("compare", END)
        
        return workflow.compile()

    def run(self, invoice_id: int):
        # Fetch Invoice Data
        doc = self.db.query(Document).filter(Document.id == invoice_id).first()
        if not doc or not doc.extraction_result:
            raise ValueError("Invoice not found or not extracted")
            
        initial_state = {
            "invoice_id": invoice_id,
            "invoice_data": doc.extraction_result.get("data", {}),
            "contract_id": None,
            "contract_data": None,
            "findings": []
        }
        
        app = self.build_graph()
        result = app.invoke(initial_state)
        return result["findings"]
