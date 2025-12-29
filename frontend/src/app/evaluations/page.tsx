"use client";

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
// We need an endpoint to serve the report, or just import json if we can.
// Since it's generated on backend, let's add an API endpoint: GET /evaluation/report
// For now, let's mock the report fetch or add the endpoint.
// Adding endpoint is cleaner.

export default function EvaluationDashboard() {
    const [report, setReport] = useState<any>(null);

    useEffect(() => {
        // In a real app we'd fetch from API
        // fetch('/api/evaluation/report')
        // For this demo, let's use a hardcoded sample if API missing, 
        // or better, implement the API endpoint quickly.
        // Let's implement GET /evaluation/report in backend.

        api.get('/evaluation/report').then(res => setReport(res.data)).catch(e => console.error(e));
    }, []);

    if (!report) return <div className="p-8">Loading Evaluation Data... (Run eval_runner.py first)</div>;

    const { metrics, details, timestamp } = report;

    return (
        <div className="min-h-screen bg-slate-50 p-8 font-sans">
            <h1 className="text-3xl font-bold text-slate-900 mb-2">Evaluation Dashboard</h1>
            <p className="text-slate-500 mb-8">Run ID: {timestamp}</p>

            {/* Scorecards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <ScoreCard label="Extraction F1" value={metrics.extraction_f1.toFixed(2)} target={0.9} />
                <ScoreCard label="Mismatch Accuracy" value={metrics.mismatch_accuracy.toFixed(2)} target={0.8} />
                <ScoreCard label="Risk Recall" value={metrics.risk_recall.toFixed(2)} target={0.95} />
            </div>

            {/* Details Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-slate-100 text-slate-600 font-semibold text-sm">
                        <tr>
                            <th className="p-4">Scenario ID</th>
                            <th className="p-4">Extraction Score</th>
                            <th className="p-4">Mismatch Detected?</th>
                            <th className="p-4">Expected Mismatch?</th>
                            <th className="p-4">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {details.map((d: any) => (
                            <tr key={d.scenario_id} className="hover:bg-slate-50">
                                <td className="p-4">Scenario {d.scenario_id}</td>
                                <td className="p-4">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${d.extraction_score >= 0.9 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                        {d.extraction_score.toFixed(2)}
                                    </span>
                                </td>
                                <td className="p-4">{d.found_mismatch ? 'Yes' : 'No'}</td>
                                <td className="p-4">{d.expected_mismatch ? 'Yes' : 'No'}</td>
                                <td className="p-4">
                                    {d.mismatch_correct ? (
                                        <span className="text-green-600 font-bold">PASS</span>
                                    ) : (
                                        <span className="text-red-600 font-bold">FAIL</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function ScoreCard({ label, value, target }: { label: string, value: string, target: number }) {
    const isGood = parseFloat(value) >= target;
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <h3 className="text-slate-500 text-sm font-medium uppercase tracking-wide mb-2">{label}</h3>
            <div className="flex items-end gap-2">
                <span className={`text-4xl font-bold ${isGood ? 'text-green-600' : 'text-red-600'}`}>{value}</span>
                <span className="text-slate-400 text-sm mb-1">Target: {target}</span>
            </div>
        </div>
    );
}
