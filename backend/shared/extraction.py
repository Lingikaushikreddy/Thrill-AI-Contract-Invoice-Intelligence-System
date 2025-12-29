from typing import Dict, Any, TypedDict, Optional
from enum import Enum
import os
import logging
import json

from langchain_openai import ChatOpenAI
from langchain_mistralai import ChatMistralAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, END
from shared.schemas import InvoiceSchema, ContractSchema, DocumentExtraction, ExtractedField
from shared.ingestion import VectorService

logger = logging.getLogger(__name__)

class DocumentType(str, Enum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    OTHER = "other"

class GraphState(TypedDict):
    doc_id: int
    doc_text: str
    doc_type: Optional[str]
    extracted_data: Optional[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]

class ExtractionGraph:
    def __init__(self):
        self.vector_service = VectorService()
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.mistral_key = os.getenv("MISTRAL_API_KEY")
        
        if self.mistral_key:
            logger.info("Using Mistral AI")
            self.llm = ChatMistralAI(model="mistral-small-latest", temperature=0)
        elif self.openai_key:
            logger.info("Using OpenAI")
            self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        else:
            logger.warning("No API Key found. Using Mock Mode.")
            self.llm = None # Mock mode

    def classify_document(self, state: GraphState):
        logger.info("Node: Classify Document")
        text = state["doc_text"][:2000] # Use first 2k chars
        
        if not self.llm:
            # Mock logic
            # Mock logic
            if "scope of work" in text.lower() or "agreement" in text.lower():
                return {"doc_type": "contract"}
            if "invoice" in text.lower():
                return {"doc_type": "invoice"}
            return {"doc_type": "other"}

        # Real LLM logic
        prompt = ChatPromptTemplate.from_template(
            """Classify the following document as 'invoice', 'contract', or 'other'. Only return the classification.
            
            Definitions:
            - 'invoice': Contains list of items, quantities, prices, total amount, invoice number.
            - 'contract': Contains agreement terms, scope of work, signatures, parties (e.g. 'Party A' and 'Party B'), liability caps.
            
            Document:
            {text}"""
        )
        chain = prompt | self.llm
        result = chain.invoke({"text": text})
        doc_type = result.content.strip().lower()
        if "invoice" in doc_type: 
            # Heuristic Correction: If it has "Scope of Work" and NO "Invoice #", it's a contract
            if "scope of work" in text.lower() and "invoice #" not in text.lower():
                return {"doc_type": "contract"}
            return {"doc_type": "invoice"}
        
        if "contract" in doc_type: return {"doc_type": "contract"}
        return {"doc_type": "other"}

    def extract_data(self, state: GraphState):
        logger.info(f"Node: Extract Data ({state['doc_type']})")
        doc_type = state["doc_type"]
        text = state["doc_text"][:5000] 

        if not self.llm:
            # Mock Extraction
            data = {}
            if doc_type == "invoice":
                inv_terms = "Net 10" if "Net 10" in text else "Net 30"
                data = {
                    "vendor_name": "Mock Vendor",
                    "total_amount": 1000.0,
                    "invoice_date": "2024-01-01",
                    "payment_terms": inv_terms
                }
            elif doc_type == "contract":
                data = {
                    "payment_terms": "Net 30",
                    "party_a": "Mock Party A", 
                    "party_b": "Mock Vendor"
                }
            return {"extracted_data": data}

        # Real LLM Extraction using Pydantic
        schema = InvoiceSchema if doc_type == "invoice" else ContractSchema
        parser = PydanticOutputParser(pydantic_object=schema)
        
        prompt = ChatPromptTemplate.from_template(
            "Extract the following information from the document.\n{format_instructions}\n\nDocument:\n{text}"
        )
        
        chain = prompt | self.llm | parser
        try:
            result = chain.invoke({"text": text, "format_instructions": parser.get_format_instructions()})
            return {"extracted_data": result.dict()}
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"extracted_data": {}}

    def link_evidence(self, state: GraphState):
        logger.info("Node: Link Evidence")
        data = state["extracted_data"]
        doc_id = state["doc_id"]
        
        final_output = {}
        
        for key, value in data.items():
            # Skip empty or complex types for now simple linking
            if not value or isinstance(value, (list, dict)):
                final_output[key] = {"value": value, "evidence": None}
                continue
                
            # Search for value in chunks to find evidence
            # This is a heuristic: query the vector DB with the value? 
            # Or better: search for the key+value context.
            # Simplified: Exact string match check in top chunks for the value
            
            # Use vector search to find context of this field
            search_query = f"{key}: {value}"
            results = self.vector_service.search(query=search_query, doc_id=doc_id, limit=1)
            
            evidence = None
            if results:
                top_hit = results[0]
                evidence = {
                    "chunk_id": top_hit.id,
                    "text": top_hit.payload.get("text"),
                    "page_number": top_hit.payload.get("page_number"),
                    "score": top_hit.score
                }
            
            final_output[key] = {
                "value": value,
                "evidence": evidence
            }
            
        return {"final_output": final_output}

    def build_graph(self):
        workflow = StateGraph(GraphState)
        
        workflow.add_node("classify", self.classify_document)
        workflow.add_node("extract", self.extract_data)
        workflow.add_node("link_evidence", self.link_evidence)
        
        workflow.set_entry_point("classify")
        
        workflow.add_conditional_edges(
            "classify",
            lambda x: "extract" if x["doc_type"] in ["invoice", "contract"] else END
        )
        
        workflow.add_edge("extract", "link_evidence")
        workflow.add_edge("link_evidence", END)
        
        return workflow.compile()

    def run(self, doc_id: int, text: str):
        app = self.build_graph()
        result = app.invoke({"doc_id": doc_id, "doc_text": text, "doc_type": None, "extracted_data": None, "final_output": None})
        return {
            "doc_type": result.get("doc_type"),
            "data": result.get("final_output") or result.get("extracted_data")
        }
