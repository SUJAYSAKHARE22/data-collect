import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import { 
  Globe, 
  FileArchive, 
  FolderOpen, 
  Search, 
  ArrowUpDown, 
  Download, 
  FileCode, 
  Folder, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Loader2, 
  Database,
  History,
  Info,
  Calendar,
  FileText,
  Sparkles,
  FileDown,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  BarChart3
} from 'lucide-react';

const Github = ({ size = 20, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

function App() {
  const [activeTab, setActiveTab] = useState('github');
  
  // Form states
  const [githubUrl, setGithubUrl] = useState('');
  const [githubBranch, setGithubBranch] = useState('');
  const [githubToken, setGithubToken] = useState('');
  
  const [webUrl, setWebUrl] = useState('');
  const [webMaxPages, setWebMaxPages] = useState(50);
  const [webMaxDepth, setWebMaxDepth] = useState(2);
  
  const [zipFile, setZipFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  
  const [localPath, setLocalPath] = useState('');

  // App orchestration states
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // { status, input_type, source, error }
  const [jobMetadata, setJobMetadata] = useState(null);
  const [jobTree, setJobTree] = useState(null);
  const [jobFiles, setJobFiles] = useState([]);
  
  const [history, setHistory] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState(null);
  
  // Tree component UI states
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  
  // Files table UI states
  const [filesSearch, setFilesSearch] = useState('');
  const [filesSort, setFilesSort] = useState('path-asc');

  // Explorer and Code Viewer states
  const [explorerTab, setExplorerTab] = useState('tree');
  const [selectedFilePath, setSelectedFilePath] = useState(null);
  const [selectedFileDetails, setSelectedFileDetails] = useState(null);
  const [selectedFileContent, setSelectedFileContent] = useState(null);
  const [loadingFileContent, setLoadingFileContent] = useState(false);
  const [copied, setCopied] = useState(false);

  // AI Analysis Agent states
  const [analysisId, setAnalysisId] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState(null); // { status, error, confidence }
  const [analysisPolling, setAnalysisPolling] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [analysisReport, setAnalysisReport] = useState(null); // parsed report_data JSON
  const [analysisStarting, setAnalysisStarting] = useState(false);
  const [expandedFindingGroups, setExpandedFindingGroups] = useState(new Set());

  // Load history from localStorage on mount
  useEffect(() => {
    try {
      const storedHistory = localStorage.getItem('collector_history');
      if (storedHistory) {
        setHistory(JSON.parse(storedHistory));
      }
    } catch (e) {
      console.error('Failed to load history', e);
    }
  }, []);

  // Save history to localStorage
  const saveToHistory = (id, type, source) => {
    const item = { id, type, source, timestamp: new Date().toISOString() };
    const updated = [item, ...history.filter(h => h.id !== id)].slice(0, 10);
    setHistory(updated);
    localStorage.setItem('collector_history', JSON.stringify(updated));
  };

  // Poll status when jobId changes
  useEffect(() => {
    if (!jobId) return;

    let intervalId;
    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/status/${jobId}`);
        if (!response.ok) {
          throw new Error(`Error fetching status: ${response.statusText}`);
        }
        const data = await response.json();
        setJobStatus(data);

        if (data.status === 'completed') {
          setPolling(false);
          clearInterval(intervalId);
          fetchResults(jobId);
        } else if (data.status === 'failed') {
          setPolling(false);
          clearInterval(intervalId);
          setError(data.error || 'Job failed on the server.');
        }
      } catch (err) {
        console.error(err);
        setError(`Failed to retrieve status: ${err.message}`);
        setPolling(false);
        clearInterval(intervalId);
      }
    };

    setPolling(true);
    setError(null);
    checkStatus(); // Immediate check
    intervalId = setInterval(checkStatus, 2000);

    return () => clearInterval(intervalId);
  }, [jobId]);

  // Poll AI analysis status when analysisId changes
  useEffect(() => {
    if (!analysisId) return;

    let intervalId;
    const checkAnalysisStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/analyze/status/${analysisId}`);
        if (!response.ok) {
          throw new Error(`Error fetching analysis status: ${response.statusText}`);
        }
        const data = await response.json();
        setAnalysisStatus(data);

        if (data.status === 'completed') {
          setAnalysisPolling(false);
          clearInterval(intervalId);
          fetchAnalysisReport(analysisId);
        } else if (data.status === 'failed') {
          setAnalysisPolling(false);
          clearInterval(intervalId);
          setAnalysisError(data.error || 'AI analysis failed on the server.');
        }
      } catch (err) {
        console.error(err);
        setAnalysisError(`Failed to retrieve analysis status: ${err.message}`);
        setAnalysisPolling(false);
        clearInterval(intervalId);
      }
    };

    setAnalysisPolling(true);
    setAnalysisError(null);
    checkAnalysisStatus();
    intervalId = setInterval(checkAnalysisStatus, 2500);

    return () => clearInterval(intervalId);
  }, [analysisId]);

  // Fetch the structured report data once analysis completes
  const fetchAnalysisReport = async (id) => {
    try {
      const response = await fetch(`${API_BASE}/analyze/${id}/report?format=json`);
      if (!response.ok) {
        throw new Error('Failed to fetch analysis report');
      }
      const data = await response.json();
      setAnalysisReport(data);
      setExpandedFindingGroups(new Set((data.developer?.groups || []).slice(0, 1).map(g => g.id)));
    } catch (err) {
      console.error(err);
      setAnalysisError(`Failed to fetch analysis report: ${err.message}`);
    }
  };

  // Kick off a new AI analysis run for the current job
  const handleStartAnalysis = async () => {
    if (!jobId) return;
    setAnalysisStarting(true);
    setAnalysisError(null);
    setAnalysisReport(null);
    setAnalysisStatus(null);

    try {
      const response = await fetch(`${API_BASE}/analyze/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        const errorDetail = await response.json().catch(() => ({}));
        throw new Error(errorDetail.detail || 'Failed to start AI analysis');
      }

      const data = await response.json();
      setAnalysisId(data.analysis_id);
    } catch (err) {
      setAnalysisError(err.message);
    } finally {
      setAnalysisStarting(false);
    }
  };

  const toggleFindingGroup = (groupId) => {
    const next = new Set(expandedFindingGroups);
    if (next.has(groupId)) next.delete(groupId);
    else next.add(groupId);
    setExpandedFindingGroups(next);
  };

  const downloadAnalysisAsset = async (format) => {
    if (!analysisId) return;
    const url = format === 'pdf'
      ? `${API_BASE}/analyze/${analysisId}/report.pdf`
      : `${API_BASE}/analyze/${analysisId}/report?format=${format}`;

    if (format === 'pdf') {
      window.open(url, '_blank', 'noopener,noreferrer');
      return;
    }

    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const ext = format === 'markdown' ? 'md' : format;
      const objectUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `${(analysisReport?.projectName || 'report').toLowerCase().replace(/[^a-z0-9]+/g, '-')}-report.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error(err);
      setAnalysisError(`Failed to download ${format} report: ${err.message}`);
    }
  };

  // Fetch metadata, tree, files once completed
  const fetchResults = async (id) => {
    try {
      setError(null);
      // Fetch in parallel
      const [metaRes, treeRes, filesRes] = await Promise.all([
        fetch(`${API_BASE}/metadata/${id}`),
        fetch(`${API_BASE}/tree/${id}`),
        fetch(`${API_BASE}/files/${id}`)
      ]);

      if (!metaRes.ok || !treeRes.ok || !filesRes.ok) {
        throw new Error('Some job outputs are not available.');
      }

      const metaData = await metaRes.json();
      const treeData = await treeRes.json();
      const filesData = await filesRes.json();

      setJobMetadata(metaData.metadata);
      setJobTree(treeData.tree);
      setJobFiles(filesData.files);

      // Auto-expand root folder
      if (treeData.tree && treeData.tree.name) {
        setExpandedNodes(new Set([treeData.tree.name]));
      }
    } catch (err) {
      console.error(err);
      setError(`Failed to fetch job results: ${err.message}`);
    }
  };

  // Submit GitHub Repository
  const handleGithubSubmit = async (e) => {
    e.preventDefault();
    if (!githubUrl) return;

    setSubmitting(true);
    setError(null);
    clearResults();

    try {
      const response = await fetch(`${API_BASE}/github`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_url: githubUrl,
          branch: githubBranch || null,
          access_token: githubToken || null
        })
      });

      if (!response.ok) {
        const errorDetail = await response.json();
        throw new Error(errorDetail.detail?.[0]?.msg || errorDetail.detail || 'Submission failed');
      }

      const data = await response.json();
      setJobId(data.job_id);
      saveToHistory(data.job_id, 'github', githubUrl);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Submit Website Crawler
  const handleWebsiteSubmit = async (e) => {
    e.preventDefault();
    if (!webUrl) return;

    setSubmitting(true);
    setError(null);
    clearResults();

    try {
      const response = await fetch(`${API_BASE}/website`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: webUrl,
          max_pages: parseInt(webMaxPages) || null,
          max_depth: parseInt(webMaxDepth) !== undefined ? parseInt(webMaxDepth) : null
        })
      });

      if (!response.ok) {
        const errorDetail = await response.json();
        throw new Error(errorDetail.detail?.[0]?.msg || errorDetail.detail || 'Submission failed');
      }

      const data = await response.json();
      setJobId(data.job_id);
      saveToHistory(data.job_id, 'website', webUrl);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Submit ZIP upload
  const handleZipSubmit = async (e) => {
    e.preventDefault();
    if (!zipFile) return;

    setSubmitting(true);
    setError(null);
    clearResults();

    try {
      const formData = new FormData();
      formData.append('file', zipFile);

      const response = await fetch(`${API_BASE}/zip`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorDetail = await response.json();
        throw new Error(errorDetail.detail || 'ZIP upload failed');
      }

      const data = await response.json();
      setJobId(data.job_id);
      saveToHistory(data.job_id, 'zip', zipFile.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // Submit Local path
  const handleLocalSubmit = async (e) => {
    e.preventDefault();
    if (!localPath) return;

    setSubmitting(true);
    setError(null);
    clearResults();

    try {
      const response = await fetch(`${API_BASE}/local`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: localPath })
      });

      if (!response.ok) {
        const errorDetail = await response.json();
        throw new Error(errorDetail.detail?.[0]?.msg || errorDetail.detail || 'Submission failed');
      }

      const data = await response.json();
      setJobId(data.job_id);
      saveToHistory(data.job_id, 'local', localPath);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const clearResults = () => {
    setJobMetadata(null);
    setJobTree(null);
    setJobFiles([]);
    setJobStatus(null);
    setExpandedNodes(new Set());
    setSelectedFilePath(null);
    setSelectedFileDetails(null);
    setSelectedFileContent(null);
    setLoadingFileContent(false);
    setCopied(false);
    setAnalysisId(null);
    setAnalysisStatus(null);
    setAnalysisError(null);
    setAnalysisReport(null);
    setAnalysisPolling(false);
    setExpandedFindingGroups(new Set());
  };

  const handleFileClick = async (path) => {
    setSelectedFilePath(path);
    setLoadingFileContent(true);
    setSelectedFileContent('');
    setCopied(false);

    // Find the file details from jobFiles
    const details = jobFiles.find(f => f.path === path);
    setSelectedFileDetails(details);

    try {
      const response = await fetch(`${API_BASE}/files/${jobId}/${path}`);
      if (!response.ok) {
        throw new Error(`Failed to load file content: ${response.statusText}`);
      }
      const data = await response.json();
      setSelectedFileContent(data.content);
    } catch (err) {
      console.error(err);
      setSelectedFileContent(`[Error loading file content: ${err.message}]`);
    } finally {
      setLoadingFileContent(false);
    }
  };

  const handleCopyCode = () => {
    if (selectedFileContent) {
      navigator.clipboard.writeText(selectedFileContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleHistoryItemClick = (histItem) => {
    clearResults();
    setError(null);
    setJobId(histItem.id);
  };

  // Drag and drop events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setZipFile(file);
      } else {
        setError('Only .zip files are supported for upload.');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setZipFile(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

  // Directory Tree toggle
  const toggleNode = (nodePath) => {
    const next = new Set(expandedNodes);
    if (next.has(nodePath)) {
      next.delete(nodePath);
    } else {
      next.add(nodePath);
    }
    setExpandedNodes(next);
  };

  // File size formatter
  const formatSize = (bytes) => {
    if (bytes === undefined || bytes === null) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    const kb = bytes / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    return `${mb.toFixed(1)} MB`;
  };

  // Helper: recursively render the directory tree nodes
  const renderTreeNode = (node, path = '') => {
    if (!node) return null;
    const currentPath = path ? `${path}/${node.name}` : node.name;
    const isDir = node.type === 'directory';
    const isOpen = expandedNodes.has(currentPath);

    if (isDir) {
      return (
        <div key={currentPath} className="tree-node">
          <div 
            className="tree-node-content folder"
            onClick={() => toggleNode(currentPath)}
          >
            {isOpen ? <FolderOpen className="tree-icon folder" /> : <Folder className="tree-icon folder" />}
            <span>{node.name}</span>
          </div>
          {isOpen && node.children && (
            <div className="tree-node-children">
              {node.children.map(child => renderTreeNode(child, currentPath))}
            </div>
          )}
        </div>
      );
    } else {
      // File
      return (
        <div key={currentPath} className="tree-node">
          <div 
            className={`tree-node-content file clickable ${selectedFilePath === node.path ? 'selected' : ''}`}
            onClick={() => handleFileClick(node.path)}
            style={{ cursor: 'pointer' }}
          >
            <FileCode className="tree-icon file" />
            <span>{node.name}</span>
          </div>
        </div>
      );
    }
  };

  // Filter and sort files list
  const getProcessedFiles = () => {
    let result = [...jobFiles];

    if (filesSearch) {
      const query = filesSearch.toLowerCase();
      result = result.filter(f => 
        f.name.toLowerCase().includes(query) || 
        f.path.toLowerCase().includes(query) ||
        (f.language && f.language.toLowerCase().includes(query))
      );
    }

    result.sort((a, b) => {
      let valA, valB;
      const [field, order] = filesSort.split('-');

      if (field === 'path') {
        valA = a.path;
        valB = b.path;
      } else if (field === 'size') {
        valA = a.size_bytes || 0;
        valB = b.size_bytes || 0;
      } else if (field === 'language') {
        valA = a.language || '';
        valB = b.language || '';
      }

      if (valA < valB) return order === 'asc' ? -1 : 1;
      if (valA > valB) return order === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  };

  const processedFiles = getProcessedFiles();

  return (
    <div className="app-container">
      {/* Premium Glass Header */}
      <header>
        <div className="logo-section">
          <Database className="logo-icon" size={32} />
          <div>
            <h1>Project Data Collector</h1>
            <div className="system-status">
              <span className="status-indicator"></span>
              <span>Layered Intake Service</span>
            </div>
          </div>
        </div>
        <div className="system-status">
          <span className="badge completed">API OK</span>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="dashboard-grid">
        {/* Left Control Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Main Submission Card */}
          <div className="glass-card">
            <h2 className="card-title">Intake Console</h2>
            
            {/* Input Selection Tab */}
            <div className="tab-headers">
              <button 
                className={`tab-btn ${activeTab === 'github' ? 'active' : ''}`}
                onClick={() => { setActiveTab('github'); setError(null); }}
              >
                <Github size={16} />
                <span>GitHub</span>
              </button>
              <button 
                className={`tab-btn ${activeTab === 'website' ? 'active' : ''}`}
                onClick={() => { setActiveTab('website'); setError(null); }}
              >
                <Globe size={16} />
                <span>Website</span>
              </button>
              <button 
                className={`tab-btn ${activeTab === 'zip' ? 'active' : ''}`}
                onClick={() => { setActiveTab('zip'); setError(null); }}
              >
                <FileArchive size={16} />
                <span>ZIP Upload</span>
              </button>
              <button 
                className={`tab-btn ${activeTab === 'local' ? 'active' : ''}`}
                onClick={() => { setActiveTab('local'); setError(null); }}
              >
                <FolderOpen size={16} />
                <span>Local</span>
              </button>
            </div>

            {/* Tab Forms */}
            {activeTab === 'github' && (
              <form onSubmit={handleGithubSubmit}>
                <div className="form-group">
                  <label htmlFor="githubUrl">Repository URL *</label>
                  <div className="input-container">
                    <Github className="input-icon" size={18} />
                    <input 
                      id="githubUrl"
                      type="url" 
                      placeholder="https://github.com/owner/repo" 
                      value={githubUrl}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label htmlFor="githubBranch">Target Branch (Optional)</label>
                  <div className="input-container">
                    <FolderOpen className="input-icon" size={18} />
                    <input 
                      id="githubBranch"
                      type="text" 
                      placeholder="e.g. main, dev (defaults to repo primary)" 
                      value={githubBranch}
                      onChange={(e) => setGithubBranch(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label htmlFor="githubToken">Personal Access Token (Private Repos Only)</label>
                  <div className="input-container">
                    <FileText className="input-icon" size={18} />
                    <input 
                      id="githubToken"
                      type="password" 
                      placeholder="ghp_xxxxxxxxxxxxxxxxxxxxx" 
                      value={githubToken}
                      onChange={(e) => setGithubToken(e.target.value)}
                    />
                  </div>
                </div>
                <button type="submit" className="submit-btn" disabled={submitting || polling}>
                  {submitting ? <Loader2 className="loader-spinner" /> : <Github size={18} />}
                  <span>Clone & Collect</span>
                </button>
              </form>
            )}

            {activeTab === 'website' && (
              <form onSubmit={handleWebsiteSubmit}>
                <div className="form-group">
                  <label htmlFor="webUrl">Website URL *</label>
                  <div className="input-container">
                    <Globe className="input-icon" size={18} />
                    <input 
                      id="webUrl"
                      type="url" 
                      placeholder="https://example.com" 
                      value={webUrl}
                      onChange={(e) => setWebUrl(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <div className="form-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label htmlFor="webMaxPages">Max Pages</label>
                    <input 
                      id="webMaxPages"
                      type="number" 
                      min="1" 
                      max="500"
                      value={webMaxPages}
                      onChange={(e) => setWebMaxPages(e.target.value)}
                      style={{ paddingLeft: '0.75rem' }}
                    />
                  </div>
                  <div>
                    <label htmlFor="webMaxDepth">Max Depth</label>
                    <input 
                      id="webMaxDepth"
                      type="number" 
                      min="0" 
                      max="10"
                      value={webMaxDepth}
                      onChange={(e) => setWebMaxDepth(e.target.value)}
                      style={{ paddingLeft: '0.75rem' }}
                    />
                  </div>
                </div>
                <button type="submit" className="submit-btn" disabled={submitting || polling}>
                  {submitting ? <Loader2 className="loader-spinner" /> : <Globe size={18} />}
                  <span>Crawl & Collect</span>
                </button>
              </form>
            )}

            {activeTab === 'zip' && (
              <form onSubmit={handleZipSubmit}>
                <div className="form-group">
                  <label>Upload ZIP Archive *</label>
                  <div 
                    className={`zip-dropzone ${dragActive ? 'dragover' : ''}`}
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={triggerFileInput}
                  >
                    <FileArchive className="zip-icon" size={40} />
                    <span className="zip-text">Drag & drop your .zip here, or click to browse</span>
                    <input 
                      ref={fileInputRef}
                      type="file" 
                      accept=".zip"
                      onChange={handleFileChange}
                      style={{ display: 'none' }}
                      required
                    />
                  </div>
                  {zipFile && (
                    <div className="zip-selected-file">
                      <FileArchive size={16} />
                      <span>{zipFile.name} ({formatSize(zipFile.size)})</span>
                    </div>
                  )}
                </div>
                <button type="submit" className="submit-btn" disabled={!zipFile || submitting || polling}>
                  {submitting ? <Loader2 className="loader-spinner" /> : <FileArchive size={18} />}
                  <span>Upload & Process</span>
                </button>
              </form>
            )}

            {activeTab === 'local' && (
              <form onSubmit={handleLocalSubmit}>
                <div className="form-group">
                  <label htmlFor="localPath">Absolute Directory Path *</label>
                  <div className="input-container">
                    <FolderOpen className="input-icon" size={18} />
                    <input 
                      id="localPath"
                      type="text" 
                      placeholder="e.g. C:\Projects\MyRepo or /var/www" 
                      value={localPath}
                      onChange={(e) => setLocalPath(e.target.value)}
                      required
                    />
                  </div>
                </div>
                <button type="submit" className="submit-btn" disabled={submitting || polling}>
                  {submitting ? <Loader2 className="loader-spinner" /> : <FolderOpen size={18} />}
                  <span>Index Local Path</span>
                </button>
              </form>
            )}
          </div>

          {/* Job History Card */}
          <div className="glass-card">
            <h2 className="card-title">
              <History size={18} style={{ color: 'var(--primary)' }} />
              <span>Recent Collections</span>
            </h2>
            {history.length === 0 ? (
              <p style={{ color: 'var(--text-dark)', fontSize: '0.875rem' }}>No recent collection jobs run.</p>
            ) : (
              <div className="history-list">
                {history.map((h) => (
                  <div 
                    key={h.id} 
                    className={`history-item ${jobId === h.id ? 'active' : ''}`}
                    onClick={() => handleHistoryItemClick(h)}
                  >
                    <div className="history-info">
                      <span className="history-id">{h.id.substring(0, 12)}...</span>
                      <span className="history-source">{h.source}</span>
                    </div>
                    <span className="badge completed" style={{ fontSize: '0.65rem' }}>
                      {h.type}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Details Panel */}
        <div className="main-display">
          {!jobId && (
            <div className="glass-card welcome-screen" style={{ height: '100%' }}>
              <Database className="welcome-icon" size={64} />
              <h2>No Job Selected</h2>
              <p style={{ marginTop: '0.5rem', maxWidth: '400px' }}>
                Submit a URL, crawl target, or ZIP file in the intake console to begin structuring your project files.
              </p>
            </div>
          )}

          {jobId && (
            <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Tracker / Active Job Header */}
              <div className="tracker-status-box">
                <div className="tracker-title-section">
                  <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                    Job ID: <span style={{ fontFamily: 'monospace', color: 'var(--primary)' }}>{jobId}</span>
                  </h3>
                  {jobStatus && (
                    <span className="tracker-source">
                      Source: <strong>{jobStatus.source}</strong> ({jobStatus.input_type})
                    </span>
                  )}
                </div>
                {jobStatus && (
                  <span className={`badge ${jobStatus.status}`}>
                    {jobStatus.status === 'pending' && <Clock size={12} />}
                    {jobStatus.status === 'running' && <Loader2 size={12} className="loader-spinner" style={{ animationDuration: '2s', width: 12, height: 12, borderWidth: '2px' }} />}
                    {jobStatus.status === 'completed' && <CheckCircle size={12} />}
                    {jobStatus.status === 'failed' && <AlertTriangle size={12} />}
                    {jobStatus.status}
                  </span>
                )}
              </div>

              {/* Error Box */}
              {error && (
                <div className="error-message">
                  <AlertTriangle size={20} style={{ flexShrink: 0 }} />
                  <div>
                    <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Job Execution Failed</strong>
                    <span>{error}</span>
                  </div>
                </div>
              )}

              {/* Polling/Running Spinner */}
              {polling && (
                <div className="tracker-loader-container">
                  <div className="pulse-ring">
                    <Database size={30} style={{ color: 'var(--primary)' }} />
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ fontWeight: '500' }}>Running Collector Pipeline...</p>
                    <p style={{ color: 'var(--text-dark)', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                      Cloning, crawling, and organizing file graphs.
                    </p>
                  </div>
                </div>
              )}

              {/* Results View */}
              {jobStatus?.status === 'completed' && jobMetadata && (
                <div>
                  {/* Results Sub-grid */}
                  <div className="results-grid">
                    {/* Column 1: Metadata Overview */}
                    <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(0,0,0,0.1)' }}>
                      <h4 className="card-title" style={{ fontSize: '1rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
                        <Info size={16} />
                        <span>Project Overview</span>
                      </h4>
                      <div className="meta-grid">
                        <div className="meta-box">
                          <div className="meta-label">Project Name</div>
                          <div className="meta-value">{jobMetadata.project_name}</div>
                        </div>
                        <div className="meta-box">
                          <div className="meta-label">Total Files</div>
                          <div className="meta-value">{jobMetadata.files?.length || 0}</div>
                        </div>
                        <div className="meta-box">
                          <div className="meta-label">Primary Language</div>
                          <div className="meta-value">{jobMetadata.language || 'Unknown'}</div>
                        </div>
                        <div className="meta-box">
                          <div className="meta-label">Folders Indexed</div>
                          <div className="meta-value">{jobMetadata.folders?.length || 0}</div>
                        </div>
                      </div>

                      {/* Entry Files & Dependency Files list */}
                      {jobMetadata.entry_files && jobMetadata.entry_files.length > 0 && (
                        <div style={{ marginTop: '1.25rem' }}>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-dark)', display: 'block', marginBottom: '0.5rem' }}>Entry Files:</span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {jobMetadata.entry_files.map(f => (
                              <span key={f} className="lang-pill" style={{ background: 'rgba(6, 182, 212, 0.08)', color: 'var(--primary)', borderColor: 'rgba(6, 182, 212, 0.15)' }}>
                                {f}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {jobMetadata.dependencies && jobMetadata.dependencies.length > 0 && (
                        <div style={{ marginTop: '1.25rem' }}>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-dark)', display: 'block', marginBottom: '0.5rem' }}>Dependency Files:</span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {jobMetadata.dependencies.map(f => (
                              <span key={f} className="lang-pill" style={{ background: 'rgba(139, 92, 246, 0.08)', color: 'var(--secondary)', borderColor: 'rgba(139, 92, 246, 0.15)' }}>
                                {f}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {jobMetadata.extra && (
                        <div style={{ marginTop: '1.25rem' }}>
                          {jobMetadata.extra.description && (
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem', borderLeft: '3px solid var(--primary)', paddingLeft: '0.5rem' }}>
                              {jobMetadata.extra.description}
                            </p>
                          )}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.8rem' }}>
                            {jobMetadata.extra.branch && (
                              <div>
                                <span style={{ color: 'var(--text-dark)' }}>Branch:</span> {jobMetadata.extra.branch}
                              </div>
                            )}
                            {jobMetadata.extra.license && (
                              <div>
                                <span style={{ color: 'var(--text-dark)' }}>License:</span> {jobMetadata.extra.license}
                              </div>
                            )}
                            {jobMetadata.extra.stars !== undefined && (
                              <div>
                                <span style={{ color: 'var(--text-dark)' }}>GitHub Stars:</span> {jobMetadata.extra.stars}
                              </div>
                            )}
                            {jobMetadata.extra.commit_hash && (
                              <div style={{ gridColumn: 'span 2' }}>
                                <span style={{ color: 'var(--text-dark)' }}>Commit:</span> <span style={{ fontFamily: 'monospace' }}>{jobMetadata.extra.commit_hash.substring(0, 10)}</span>
                              </div>
                            )}
                          </div>

                          {jobMetadata.extra.languages && Object.keys(jobMetadata.extra.languages).length > 0 && (
                            <div style={{ marginTop: '1rem' }}>
                              <span style={{ fontSize: '0.8rem', color: 'var(--text-dark)' }}>Languages composition:</span>
                              <div className="languages-pill-container">
                                {Object.keys(jobMetadata.extra.languages).map(lang => (
                                  <span key={lang} className="lang-pill">{lang}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ marginTop: '1.5rem' }}>
                        <a 
                          href={`${API_BASE}/download/${jobId}`} 
                          className="submit-btn" 
                          style={{ textDecoration: 'none' }}
                          target="_blank" 
                          rel="noreferrer"
                        >
                          <Download size={16} />
                          <span>Download Archive (.zip)</span>
                        </a>
                      </div>
                    </div>
                  </div>

                  {/* AI Analysis Agent Section */}
                  {jobStatus?.status === 'completed' && (
                    <div className="ai-analysis-card">
                      <div className="ai-analysis-header">
                        <div className="ai-analysis-title">
                          <Sparkles size={18} />
                          <span>AI Analysis Agent</span>
                        </div>
                        {!analysisId && (
                          <button
                            className="ai-run-btn"
                            onClick={handleStartAnalysis}
                            disabled={analysisStarting}
                          >
                            {analysisStarting ? <Loader2 size={16} className="loader-spinner" style={{ width: 16, height: 16, borderWidth: '2px' }} /> : <Sparkles size={16} />}
                            <span>{analysisStarting ? 'Starting...' : 'Run AI Analysis'}</span>
                          </button>
                        )}
                        {analysisId && analysisStatus?.status === 'completed' && (
                          <button
                            className="ai-run-btn"
                            onClick={() => { setAnalysisId(null); setAnalysisReport(null); setAnalysisStatus(null); }}
                          >
                            <Sparkles size={16} />
                            <span>Re-run Analysis</span>
                          </button>
                        )}
                      </div>

                      {!analysisId && !analysisError && (
                        <p className="ai-analysis-intro">
                          Runs an AI code-analysis agent (Kimi K2) over the collected project to produce a
                          confidence-scored report covering architecture, code quality, security, dependencies,
                          and a phased action plan — downloadable as Markdown, HTML, JSON, or PDF.
                        </p>
                      )}

                      {analysisError && (
                        <div className="ai-error-box">
                          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
                          <span>{analysisError}</span>
                        </div>
                      )}

                      {analysisPolling && !analysisReport && (
                        <div className="ai-analysis-loading">
                          <Loader2 size={20} className="loader-spinner" style={{ width: 20, height: 20, borderWidth: '2px' }} />
                          <span>
                            {analysisStatus?.status === 'running' || !analysisStatus
                              ? 'Analyzing project with Kimi K2 — this can take up to a minute...'
                              : `Status: ${analysisStatus?.status}...`}
                          </span>
                        </div>
                      )}

                      {analysisReport && (
                        <>
                          <div className={`confidence-badge ${analysisReport.overallConfidence.score >= 0.8 ? '' : analysisReport.overallConfidence.score >= 0.5 ? 'medium' : 'low'}`}>
                            <ShieldCheck size={16} />
                            <span className="cb-score">{Math.round(analysisReport.overallConfidence.score * 100)}% confidence</span>
                            <span className="cb-rationale">{analysisReport.overallConfidence.rationale}</span>
                          </div>

                          <p className="ai-analysis-intro" style={{ color: 'var(--text-main)' }}>
                            {analysisReport.executive.overview}
                          </p>

                          <div className="ai-stats-row">
                            <div className="ai-stat">
                              <span className="ai-stat-value">{analysisReport.executive.overallRisk}</span>
                              <span className="ai-stat-label">Overall Risk</span>
                            </div>
                            <div className="ai-stat">
                              <span className="ai-stat-value">{analysisReport.executive.totalFindings}</span>
                              <span className="ai-stat-label">Total Findings</span>
                            </div>
                            <div className="ai-stat">
                              <span className="ai-stat-value">{analysisReport.executive.estimatedTimeline}</span>
                              <span className="ai-stat-label">Est. Timeline</span>
                            </div>
                            <div className="ai-stat">
                              <span className="ai-stat-value">${analysisReport.business.estimatedCost.toLocaleString()}</span>
                              <span className="ai-stat-label">Est. Cost</span>
                            </div>
                          </div>

                          <div style={{ marginBottom: '0.75rem' }}>
                            {Object.entries(analysisReport.executive.bySeverity).filter(([, c]) => c > 0).map(([sev, count]) => (
                              <span key={sev} className={`severity-pill ${sev}`} style={{ marginRight: '0.4rem' }}>
                                {sev}: {count}
                              </span>
                            ))}
                          </div>

                          <div className="ai-download-row">
                            <button className="ai-download-btn pdf" onClick={() => downloadAnalysisAsset('pdf')}>
                              <FileDown size={15} />
                              <span>Download PDF Report</span>
                            </button>
                            <button className="ai-download-btn" onClick={() => downloadAnalysisAsset('markdown')}>
                              <FileText size={15} />
                              <span>Markdown</span>
                            </button>
                            <button className="ai-download-btn" onClick={() => downloadAnalysisAsset('html')}>
                              <FileCode size={15} />
                              <span>HTML</span>
                            </button>
                            <button className="ai-download-btn" onClick={() => downloadAnalysisAsset('json')}>
                              <Database size={15} />
                              <span>JSON</span>
                            </button>
                          </div>

                          <h4 style={{ fontSize: '0.9rem', margin: '1rem 0 0.5rem', color: 'var(--text-main)' }}>
                            <BarChart3 size={15} style={{ verticalAlign: 'middle', marginRight: '0.35rem' }} />
                            Findings by Category
                          </h4>
                          {analysisReport.developer.groups.map(group => (
                            <div key={group.id} className="finding-group-card">
                              <div className="finding-group-header" onClick={() => toggleFindingGroup(group.id)}>
                                <span className="finding-group-name">
                                  <span className={`severity-pill ${group.maxSeverity}`}>{group.maxSeverity}</span>
                                  {group.name}
                                  <span className="finding-group-count">({group.count} findings)</span>
                                </span>
                                {expandedFindingGroups.has(group.id) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </div>
                              {expandedFindingGroups.has(group.id) && (
                                <div className="finding-group-body">
                                  {group.findings.map(f => (
                                    <div key={f.id} className="finding-row">
                                      <div className="finding-row-title">
                                        <span className={`severity-pill ${f.severity}`}>{f.severity}</span>
                                        <span>{f.title}</span>
                                        {f.file && <span className="finding-row-file">{f.file}</span>}
                                      </div>
                                      <div className="finding-row-desc">{f.description}</div>
                                      <div className="finding-row-rec">→ {f.recommendation}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}

                          <h4 style={{ fontSize: '0.9rem', margin: '1.25rem 0 0.5rem', color: 'var(--text-main)' }}>
                            Implementation Roadmap
                          </h4>
                          {analysisReport.roadmap.phases.map((phase, idx) => (
                            <div key={idx} className="ai-roadmap-phase">
                              <h5>{phase.name} · {phase.totalHours}h</h5>
                              <p style={{ fontSize: '0.78rem', color: 'var(--text-dark)', marginBottom: '0.4rem' }}>{phase.description}</p>
                              {phase.items.map((item, i) => (
                                <div key={i} className="ai-roadmap-item">
                                  • <strong style={{ color: 'var(--text-main)' }}>{item.title}</strong> ({item.effort}, {item.effortHours}h): {item.action}
                                </div>
                              ))}
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  )}

                  {/* Explorer Section (Tree + Flat list on left, Code Viewer on right) */}
                  <div className="explorer-section">
                    {/* Left Column: File Navigation */}
                    <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                      <div className="tab-headers" style={{ marginBottom: 0 }}>
                        <button 
                          className={`tab-btn ${explorerTab === 'tree' ? 'active' : ''}`}
                          onClick={() => setExplorerTab('tree')}
                          type="button"
                        >
                          <FolderOpen size={16} />
                          <span>Tree</span>
                        </button>
                        <button 
                          className={`tab-btn ${explorerTab === 'list' ? 'active' : ''}`}
                          onClick={() => setExplorerTab('list')}
                          type="button"
                        >
                          <FileText size={16} />
                          <span>Flat List</span>
                        </button>
                      </div>

                      {explorerTab === 'tree' && (
                        <div className="tree-container">
                          {jobTree ? renderTreeNode(jobTree) : <p style={{ color: 'var(--text-dark)' }}>No tree layout generated.</p>}
                        </div>
                      )}

                      {explorerTab === 'list' && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                          <div className="files-control-bar">
                            <div className="search-input-wrapper">
                              <Search className="search-icon" size={16} />
                              <input 
                                type="text" 
                                placeholder="Search files..." 
                                value={filesSearch}
                                onChange={(e) => setFilesSearch(e.target.value)}
                              />
                            </div>
                            <div className="sort-select">
                              <select 
                                value={filesSort}
                                onChange={(e) => setFilesSort(e.target.value)}
                              >
                                <option value="path-asc">Path (A-Z)</option>
                                <option value="path-desc">Path (Z-A)</option>
                                <option value="size-desc">Size (Large-Small)</option>
                                <option value="size-asc">Size (Small-Large)</option>
                                <option value="language-asc">Language (A-Z)</option>
                              </select>
                            </div>
                          </div>

                          <div className="files-list-container">
                            {processedFiles.length === 0 ? (
                              <p style={{ color: 'var(--text-dark)', padding: '2rem', textAlign: 'center' }}>
                                No files found.
                              </p>
                            ) : (
                              processedFiles.map((file, idx) => (
                                <div 
                                  key={idx} 
                                  className={`file-row-item clickable ${selectedFilePath === file.path ? 'selected' : ''}`}
                                  onClick={() => handleFileClick(file.path)}
                                  style={{ cursor: 'pointer' }}
                                >
                                  <div className="file-row-header">
                                    <span>{file.path}</span>
                                  </div>
                                  <div className="file-row-meta">
                                    <span>Size: <strong>{formatSize(file.size_bytes)}</strong></span>
                                    {file.language && (
                                      <span className="lang-pill" style={{ margin: 0, padding: '0.1rem 0.4rem', fontSize: '0.7rem' }}>
                                        {file.language}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Right Column: Code Viewer */}
                    <div className="glass-card" style={{ padding: '1.25rem', background: 'rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', minHeight: '500px' }}>
                      {selectedFilePath === null ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, color: 'var(--text-muted)', textAlign: 'center', padding: '3rem 1rem' }}>
                          <FileCode size={48} style={{ color: 'var(--text-dark)', marginBottom: '1rem' }} />
                          <p style={{ fontWeight: '500' }}>No File Selected</p>
                          <p style={{ fontSize: '0.875rem', color: 'var(--text-dark)', marginTop: '0.25rem' }}>
                            Select a file from the Tree or Flat List to view its content.
                          </p>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, gap: '0.75rem', minWidth: 0 }}>
                          <div className="code-viewer-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.75rem', gap: '1rem' }}>
                            <div style={{ minWidth: 0 }}>
                              <h4 style={{ fontSize: '0.95rem', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0 }}>
                                {selectedFilePath}
                              </h4>
                              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                                Size: {formatSize(selectedFileDetails?.size_bytes)} | Language: {selectedFileDetails?.language || 'Plain Text'}
                              </p>
                            </div>
                            <button 
                              className="tab-btn" 
                              style={{ padding: '0.4rem 0.75rem', background: 'rgba(255,255,255,0.05)', borderRadius: 'var(--radius-sm)', cursor: 'pointer', flexShrink: 0 }}
                              onClick={handleCopyCode}
                              type="button"
                            >
                              {copied ? 'Copied!' : 'Copy Code'}
                            </button>
                          </div>

                          <div className="code-viewer-body" style={{ flex: 1, position: 'relative', background: '#030712', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-glass)', overflow: 'hidden', minHeight: '350px', display: 'flex' }}>
                            {loadingFileContent ? (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', height: '100%', minHeight: '350px' }}>
                                <Loader2 className="loader-spinner" />
                              </div>
                            ) : (
                              <div style={{ display: 'flex', width: '100%', overflow: 'auto', padding: '1rem', fontFamily: 'monospace', fontSize: '0.85rem', lineHeight: '1.5' }}>
                                <div style={{ color: 'var(--text-dark)', textAlign: 'right', userSelect: 'none', paddingRight: '1rem', borderRight: '1px solid rgba(255,255,255,0.05)', marginRight: '1rem', minWidth: '2.5rem' }}>
                                  {selectedFileContent ? selectedFileContent.split('\n').map((_, i) => (
                                    <div key={i}>{i + 1}</div>
                                  )) : <div>1</div>}
                                </div>
                                <pre style={{ margin: 0, color: '#f3f4f6', flex: 1, whiteSpace: 'pre', overflow: 'visible' }}>
                                  <code>{selectedFileContent || ''}</code>
                                </pre>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
