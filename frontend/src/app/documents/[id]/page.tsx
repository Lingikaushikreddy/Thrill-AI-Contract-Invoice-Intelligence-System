"use client";

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getDocument, getFindings, reviewFinding, Document, Finding } from '@/lib/api';
import { AlertCircle, Check, X, ShieldAlert, FileText, ChevronRight } from 'lucide-react';
import axios from 'axios';

export default function DocumentDetails() {
    const { id } = useParams();
    const docId = parseInt(id as string);

    const [doc, setDoc] = useState<Document | null>(null);
    const [findings, setFindings] = useState<Finding[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'mismatch' | 'risk'>('mismatch');
    const [risks, setRisks] = useState<any[]>([]); // Using any for simplicity for now

    useEffect(() => {
        if (!docId) return;
        loadData();
    }, [docId]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [docData, findingsData] = await Promise.all([
                getDocument(docId),
                getFindings(docId)
            ]);
            setDoc(docData.result ? { ...docData, extraction_result: docData.result } : docData); // Normalize API response structure
            setFindings(findingsData);

            // Also fetch risks if it's a contract
            // Note: This endpoint triggers analysis if not done, or we should have a 'get risks' endpoint.
            // Since `assess_risk` is POST, let's just trigger it or assume it's done? 
            // For UX, let's try to fetch active risks if they exist in findings, 
            // OR let the user click "Run Risk Analysis".

        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const runRiskAnalysis = async () => {
        try {
            const res = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/contracts/${docId}/risk_assessment`);
            if (res.data.status === 'success') {
                setRisks(res.data.risks);
                setActiveTab('risk');
                // Ideally we reload findings if risks are stored as findings (Wait, are they?)
                // The current implementation returns risks in the response but doesn't strictly adhere to storing them 
                // in the `findings` table in the same format as mismatch. 
                // Actually, `RiskAssessmentGraph` does NOT save to DB in the current implementation! 
                // It returns them. I should fix that in backend or just show them here.
                // For Proof of Concept, displaying them from response is fine.
            }
        } catch (e) {
            alert("Analysis failed");
        }
    };

    const handleReview = async (findingId: number, decision: 'APPROVE' | 'OVERRIDE') => {
        try {
            await reviewFinding(findingId, decision);
            // Update local state
            setFindings(prev => prev.map(f => f.id === findingId ? { ...f, status: decision === 'APPROVE' ? 'reviewed' : 'overridden' } : f));
        } catch (e) {
            alert("Action failed");
        }
    };

    if (loading) return <div className="p-8">Loading...</div>;
    if (!doc) return <div className="p-8">Document not found</div>;

    return (
        <div className="h-screen flex flex-col bg-slate-50 font-sans">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
                <div className="flex items-center gap-4">
                    <Link href="/" className="p-2 hover:bg-slate-100 rounded-full">‹</Link>
                    <div>
                        <h1 className="text-xl font-bold text-slate-900">{doc.filename}</h1>
                        <span className="text-xs text-slate-500 uppercase tracking-wide">{doc.status} • ID: {doc.id}</span>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={runRiskAnalysis} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
                        Run Risk Analysis
                    </button>
                </div>
            </header>

            <div className="flex-1 flex overflow-hidden">
                {/* PDF View (Left) */}
                <div className="w-1/2 bg-slate-200 flex items-center justify-center border-r border-slate-300 relative">
                    <p className="text-slate-500">PDF Viewer Placeholder</p>
                    {/* In a real app, use <iframe src={pdfUrl} /> or react-pdf */}
                </div>

                {/* Findings Panel (Right) */}
                <div className="w-1/2 bg-white flex flex-col">
                    {/* Tabs */}
                    <div className="flex border-b border-slate-200">
                        <button
                            onClick={() => setActiveTab('mismatch')}
                            className={`flex-1 py-3 text-sm font-medium border-b-2 ${activeTab === 'mismatch' ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500'}`}
                        >
                            Mismatches ({findings.length})
                        </button>
                        <button
                            onClick={() => setActiveTab('risk')}
                            className={`flex-1 py-3 text-sm font-medium border-b-2 ${activeTab === 'risk' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500'}`}
                        >
                            Risk Assessment ({risks.length})
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                        {activeTab === 'mismatch' ? (
                            findings.length === 0 ? <p className="text-slate-400 text-center py-10">No mismatches detected.</p> :
                                findings.map(f => (
                                    <div key={f.id} className={`border rounded-xl p-4 ${f.status === 'open' ? 'bg-white border-slate-200' : 'bg-slate-50 border-transparent'}`}>
                                        <div className="flex justify-between items-start mb-2">
                                            <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${f.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                                                }`}>
                                                {f.severity}
                                            </span>
                                            <span className="text-xs text-slate-400 capitalize">{f.status}</span>
                                        </div>
                                        <h3 className="font-semibold text-slate-900 mb-1">{f.finding_type.replace('_', ' ')}</h3>
                                        <p className="text-sm text-slate-600 mb-4">{f.description}</p>

                                        {f.status === 'open' && (
                                            <div className="flex gap-2 mt-4 pt-4 border-t border-slate-100">
                                                <button onClick={() => handleReview(f.id, 'APPROVE')} className="flex-1 px-3 py-2 bg-slate-900 text-white text-xs rounded-lg hover:bg-slate-800">
                                                    Confirm Issue
                                                </button>
                                                <button onClick={() => handleReview(f.id, 'OVERRIDE')} className="flex-1 px-3 py-2 border border-slate-200 text-slate-700 text-xs rounded-lg hover:bg-slate-50">
                                                    Mark as Safe (Override)
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))
                        ) : (
                            risks.length === 0 ? <p className="text-slate-400 text-center py-10">Run analysis to see risks.</p> :
                                risks.map((r, i) => (
                                    <div key={i} className="border border-indigo-100 bg-indigo-50/30 rounded-xl p-4">
                                        <div className="flex justify-between mb-2">
                                            <span className="font-semibold text-indigo-900">{r.clause_type}</span>
                                            <span className="bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded text-xs font-bold">Score: {r.risk_score}/10</span>
                                        </div>
                                        <p className="text-sm text-slate-700 mb-3">{r.explanation}</p>

                                        <div className="bg-white p-3 rounded border border-indigo-100 text-xs text-slate-500 mb-2">
                                            <span className="block font-medium text-xs mb-1 uppercase tracking-wide">Original:</span>
                                            {r.original_text}
                                        </div>
                                        <div className="bg-green-50 p-3 rounded border border-green-100 text-xs text-green-700">
                                            <span className="block font-medium text-xs mb-1 uppercase tracking-wide">Suggested Redline:</span>
                                            {r.redline_text}
                                        </div>
                                    </div>
                                ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

import Link from 'next/link';
