import { useState } from 'react';
import './index.css';
import UploadForm from './components/UploadForm.next.jsx';
import Dashboard from './components/Dashboard.compact.jsx';
import GlobalSearch from './components/GlobalSearch.jsx'; // Import your new search engine view
import { Search, FileText } from 'lucide-react'; // Imports modern vector icons for your tabs

function App() {
  const [reportData, setReportData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentView, setCurrentView] = useState('review'); // Views: 'review' or 'search'

  const isLandingState = !reportData && !isLoading;

  const handleUploadComplete = (rawResponse) => {
    console.log('[App] Raw backend response:', JSON.stringify(rawResponse, null, 2));

    const type = rawResponse.type || 'contract';
    const task = type === 'summary' ? 'summarize_case' : 'analyze_contract';

    const normalized = {
      filename: rawResponse.filename || rawResponse.content?.filename || 'Uploaded Document',
      task,
      type,
      results: rawResponse.content || rawResponse.results || {},
      libraryIndexing: rawResponse.libraryIndexing || 'not_requested',
    };

    console.log('[App] Normalized clause count:', normalized.results?.contract_analysis?.analyzed_clauses?.length ?? 0);

    setReportData(normalized);
    setIsLoading(false);
  };

  const handleUploadStart = () => {
    setIsLoading(true);
    setError(null);
    setReportData(null);
  };

  const handleError = (errMsg) => {
    setError(errMsg);
    setIsLoading(false);
  };

  const resetUpload = () => {
    setReportData(null);
    setError(null);
  };

  return (
    <div className={`app-container${isLandingState ? ' landing-mode' : ''}`}>
      {/* GLOBAL APPMENU HEADER BAR */}
      <header className="app-main-header">
        <div className="brand-lockup">
          <h1>Legal AI Platform</h1>
          <p>Clearer legal documents. Better-informed decisions.</p>
        </div>
        
        {/* Navigation control switch */}
        <nav className="view-navigation-tabs">
          <button 
            type="button"
            className={`tab-btn ${currentView === 'review' ? 'active' : ''}`}
            onClick={() => setCurrentView('review')}
          >
            <FileText size={16} />
            <span>Review & Analysis</span>
          </button>
          
          <button 
            type="button"
            className={`tab-btn ${currentView === 'search' ? 'active' : ''}`}
            onClick={() => setCurrentView('search')}
          >
            <Search size={16} />
            <span>Library Intelligence</span>
          </button>
        </nav>
      </header>

      <main>
        {/* Render View Layer: Global Vector Knowledge Base */}
        {currentView === 'search' ? (
          <div className="animate-slide-up">
            <GlobalSearch />
          </div>
        ) : (
          /* Render View Layer: Classical Core Document Review Pipeline */
          <>
            {error && (
              <div className="glass-panel" style={{ borderColor: 'var(--risk-high)', marginBottom: '2rem' }}>
                <h3 style={{ color: 'var(--risk-high)' }}>Error</h3>
                <p>{error}</p>
                <button className="btn-primary" onClick={resetUpload} style={{ marginTop: '1rem' }}>
                  Try Again
                </button>
              </div>
            )}

            {!reportData && !isLoading && (
              <div className="animate-slide-up">
                <UploadForm
                  onUploadStart={handleUploadStart}
                  onUploadComplete={handleUploadComplete}
                  onError={handleError}
                />
              </div>
            )}

            {isLoading && (
              <div className="glass-panel animate-slide-up" style={{ textAlign: 'center', padding: '4rem' }}>
                <div className="loader" style={{ width: '48px', height: '48px', marginBottom: '1rem' }}></div>
                <h2>Processing Document...</h2>
                <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                  Our AI pipelines are processing your document. This may take a moment.
                </p>
              </div>
            )}

            {reportData && !isLoading && (
              <div className="animate-slide-up">
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.25rem' }}>
                  <button className="secondary-button" onClick={resetUpload}>
                    Review another document
                  </button>
                </div>

                {reportData.type === 'summary' ? (
                  <div className="glass-panel" style={{ padding: '2rem' }}>
                    <h2 style={{ marginBottom: '1rem' }}>📄 Document Summary</h2>
                    <p style={{ whiteSpace: 'pre-line', lineHeight: '1.6' }}>
                      {reportData.results?.summary_data?.final_summary || 'Summarization failed or returned empty.'}
                    </p>
                  </div>
                ) : (
                  <Dashboard data={reportData} />
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;