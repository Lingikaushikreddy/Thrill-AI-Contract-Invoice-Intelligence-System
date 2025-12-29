"use client";

import { useEffect, useState } from 'react';
import { getDocuments, uploadDocument, Document } from '../lib/api';
import Link from 'next/link';
import { Upload, FileText, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';

export default function Dashboard() {
    const [docs, setDocs] = useState<Document[]>([]);
    const [uploading, setUploading] = useState(false);

    useEffect(() => {
        fetchDocs();
    }, []);

    const fetchDocs = async () => {
        try {
            const data = await getDocuments();
            setDocs(data.documents);
        } catch (e) {
            console.error(e);
        }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0]) return;
        setUploading(true);
        try {
            await uploadDocument(e.target.files[0]);
            await fetchDocs(); // Refresh
            // Simulating polling for updates would be better
        } catch (err) {
            alert("Upload failed");
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 p-8 font-sans">
            <header className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Contract Intelligence</h1>
                    <p className="text-slate-500">AI-Powered Risk & Mismatch Detection</p>
                </div>
                <div className="relative">
                    <input
                        type="file"
                        onChange={handleUpload}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                        accept=".pdf"
                    />
                    <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition">
                        {uploading ? <Loader2 className="animate-spin h-5 w-5" /> : <Upload className="h-5 w-5" />}
                        Upload Document
                    </button>
                </div>
            </header>

            <div className="grid gap-4">
                {docs.map((doc) => (
                    <div key={doc.id} className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 flex items-center justify-between hover:shadow-md transition">
                        <div className="flex items-center gap-4">
                            <div className="bg-blue-50 p-2 rounded-lg">
                                <FileText className="h-6 w-6 text-blue-600" />
                            </div>
                            <div>
                                <Link href={`/documents/${doc.id}`} className="text-lg font-semibold text-slate-900 hover:text-blue-600">
                                    {doc.filename}
                                </Link>
                                <div className="text-sm text-slate-500 flex items-center gap-2">
                                    <span>ID: {doc.id}</span>
                                    <span>•</span>
                                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-4">
                            {/* Status Badge */}
                            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${doc.status === 'COMPLETED' ? 'bg-green-50 text-green-700 border-green-200' :
                                    doc.status === 'FAILED' ? 'bg-red-50 text-red-700 border-red-200' :
                                        'bg-yellow-50 text-yellow-700 border-yellow-200'
                                }`}>
                                {doc.status}
                            </span>

                            <Link href={`/documents/${doc.id}`} className="text-sm font-medium text-slate-600 hover:text-slate-900">
                                View Analysis &rarr;
                            </Link>
                        </div>
                    </div>
                ))}

                {docs.length === 0 && (
                    <div className="text-center py-20 text-slate-400">
                        <p>No documents found. Upload a contract or invoice to get started.</p>
                    </div>
                )}
            </div>
        </div>
    );
}
