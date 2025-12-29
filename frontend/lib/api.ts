import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
    baseURL: API_URL,
});

export interface Document {
    id: number;
    filename: string;
    status: string;
    created_at: string;
    extraction_result?: any;
}

export interface Finding {
    id: number;
    document_id: number;
    finding_type: string;
    severity: string;
    description: string;
    evidence: any;
    status: string;
}

export const getDocuments = async () => {
    const res = await api.get('/search?q=&limit=100'); // Hacky: search all? Or specific endpoint?
    // Actually we don't have a "list all" endpoint. Let's add one or use search.
    // Search returns chunks. We need list of docs.
    // Let's implement /documents endpoint.
    return res.data;
};

export const getDocument = async (id: number) => {
    const res = await api.get(`/documents/${id}/extraction`);
    // This returns extraction, but we also want findings.
    return res.data;
};

export const getFindings = async (id: number) => {
    const res = await api.get(`/documents/${id}/findings`);
    return res.data.findings;
};

export const reviewFinding = async (id: number, decision: 'APPROVE' | 'OVERRIDE', comment?: string) => {
    await api.post(`/findings/${id}/review`, { decision, comment });
};

export const uploadDocument = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    await api.post('/upload', formData);
};
