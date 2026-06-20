import { useRef, useState } from 'react';
import {
  Check,
  BookOpen,
  ChevronDown,
  FileText,
  Loader2,
  Scale,
  ShieldCheck,
  Trash2,
  Upload,
} from 'lucide-react';
import { api } from '../api';

const MODES = {
  analyze_contract: {
    label: 'Review a contract',
    description: 'Find important clauses, risks, and practical next steps.',
    icon: ShieldCheck,
    cta: 'Review document',
  },
  summarize_case: {
    label: 'Summarize a document',
    description: 'Turn a long legal document into a clear, readable summary.',
    icon: FileText,
    cta: 'Create summary',
  },
};

const UploadForm = ({ onUploadStart, onUploadComplete, onError }) => {
  const [file, setFile] = useState(null);
  const [taskType, setTaskType] = useState('analyze_contract');
  const [dragActive, setDragActive] = useState(false);
  const [retainInLibrary, setRetainInLibrary] = useState(false);
  const [jurisdiction, setJurisdiction] = useState('');
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryStatus, setLibraryStatus] = useState(null);
  const inputRef = useRef(null);

  const selectFile = (selectedFile) => {
    if (!selectedFile) return;
    const extension = selectedFile.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(extension)) {
      onError('Please choose a PDF, DOCX, or TXT file.');
      return;
    }
    setFile(selectedFile);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) return;

    onUploadStart();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('task_type', taskType);
    
    // Explicitly casting to lower-case string values matching backend parser
    formData.append('retain_in_library', String(retainInLibrary && taskType === 'analyze_contract'));
    if (jurisdiction.trim()) formData.append('jurisdiction', jurisdiction.trim());

    try {
      const response = await api.post('/api/upload', formData);
      const content = response.data?.results;

      if (taskType === 'analyze_contract' && !Array.isArray(content?.contract_analysis?.analyzed_clauses)) {
        throw new Error(content?.error || 'The contract review did not return usable results.');
      }
      if (taskType === 'summarize_case' && !content?.summary_data?.final_summary) {
        throw new Error(content?.error || 'The document summary could not be created.');
      }

      onUploadComplete({
        type: taskType === 'summarize_case' ? 'summary' : 'contract',
        filename: file.name,
        content,
        libraryIndexing: response.data?.library_indexing,
      });
    } catch (error) {
      onError(
        error.response?.data?.detail ||
        error.message ||
        'We could not process this document. Please try again.'
      );
    }
  };

  const activeMode = MODES[taskType];

  const loadLibrary = async () => {
    const nextOpen = !libraryOpen;
    setLibraryOpen(nextOpen);
    if (!nextOpen || libraryStatus) return;
    setLibraryLoading(true);
    try {
      const response = await api.get('/api/clause-library/status');
      setLibraryStatus(response.data);
    } catch {
      setLibraryStatus({
        status: 'error',
        document_count: 0,
        clause_count: 0,
        documents: [],
        message: 'The clause library is unavailable.',
      });
    } finally {
      setLibraryLoading(false);
    }
  };

  const deleteLibraryDocument = async (documentHash) => {
    setLibraryLoading(true);
    try {
      await api.delete(`/api/clause-library/documents/${documentHash}`);
      const response = await api.get('/api/clause-library/status');
      setLibraryStatus(response.data);
    } catch {
      onError('The document could not be removed from the private library.');
    } finally {
      setLibraryLoading(false);
    }
  };

  return (
    <section className="upload-layout">
      <div className="landing-copy">
        <div className="brand-mark"><Scale size={20} /></div>
        <span className="eyebrow">Legal document review</span>
        <h2>Understand the document before you act on it.</h2>
        <p>
          Upload a legal document and get a focused review in plain language.
          Your original file stays on your device unless you submit it for analysis.
        </p>
        <div className="trust-line">
          <Check size={16} />
          <span>PDF, DOCX, and TXT · Up to 15 MB</span>
        </div>
      </div>

      <form className="upload-card" onSubmit={handleSubmit}>
        <div className="form-section">
          <label className="form-label">What would you like to do?</label>
          <div className="mode-selector">
            {Object.entries(MODES).map(([value, mode]) => {
              const Icon = mode.icon;
              const active = taskType === value;
              return (
                <button
                  key={value}
                  type="button"
                  className={`mode-button ${active ? 'active' : ''}`}
                  onClick={() => setTaskType(value)}
                  aria-pressed={active}
                >
                  <Icon size={19} />
                  <span>
                    <strong>{mode.label}</strong>
                    <small>{mode.description}</small>
                  </span>
                  <span className="mode-check">{active && <Check size={14} />}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="form-section">
          <label className="form-label">Choose your document</label>
          <div
            className={`drop-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={(event) => { event.preventDefault(); setDragActive(false); }}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              selectFile(event.dataTransfer.files?.[0]);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(event) => selectFile(event.target.files?.[0])}
              hidden
            />
            {file ? (
              <>
                <div className="file-icon"><FileText size={22} /></div>
                <div className="file-copy">
                  <strong>{file.name}</strong>
                  <span>{(file.size / 1024 / 1024).toFixed(2)} MB · Click to replace</span>
                </div>
                <Check className="file-check" size={18} />
              </>
            ) : (
              <>
                <div className="upload-icon"><Upload size={22} /></div>
                <strong>Drop a file here or click to browse</strong>
                <span>PDF, DOCX, or TXT</span>
              </>
            )}
          </div>
        </div>

        {taskType === 'analyze_contract' && (
          <div className="library-option">
            <label className="library-consent">
              <input
                type="checkbox"
                checked={retainInLibrary}
                onChange={(event) => setRetainInLibrary(event.target.checked)}
              />
              <span>
                <strong>Add clauses to my private library</strong>
                <small>Enables future similarity searches. You can remove stored documents later.</small>
              </span>
            </label>
            {retainInLibrary && (
              <input
                className="jurisdiction-input"
                value={jurisdiction}
                onChange={(event) => setJurisdiction(event.target.value)}
                placeholder="Jurisdiction (optional, e.g. India)"
                aria-label="Document jurisdiction"
              />
            )}
          </div>
        )}

        <button className="primary-button" type="submit" disabled={!file}>
          {activeMode.cta}
        </button>
        <p className="form-note">AI-assisted review. Always verify important decisions with qualified counsel.</p>

        <button type="button" className="library-manager-toggle" onClick={loadLibrary}>
          <BookOpen size={15} />
          Manage private clause library
          <ChevronDown size={15} className={libraryOpen ? 'rotate' : ''} />
        </button>
        
        {libraryOpen && (
          <div className="library-manager">
            {libraryLoading && !libraryStatus && (
              <div className="library-manager-loading"><Loader2 size={15} className="spin-icon" /> Loading library…</div>
            )}
            {libraryStatus && (
              <>
                <div className="library-manager-summary">
                  <span><strong>{libraryStatus.document_count}</strong> documents</span>
                  <span><strong>{libraryStatus.clause_count}</strong> clauses</span>
                </div>
                {libraryStatus.documents?.length === 0 && (
                  <p>{libraryStatus.message || 'No documents have been added yet.'}</p>
                )}
                {libraryStatus.documents?.map((document) => (
                  <div className="library-document" key={document.document_hash}>
                    {/* Fixed: Maps to document.source matching backend schema */}
                    <span>{document.source || 'Unnamed Document'}</span>
                    <button
                      type="button"
                      onClick={() => deleteLibraryDocument(document.document_hash)}
                      disabled={libraryLoading}
                      aria-label={`Remove ${document.source || 'document'} from library`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </form>
    </section>
  );
};

export default UploadForm;