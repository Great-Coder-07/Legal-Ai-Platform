import React, { useState, useEffect } from 'react';
import { 
  Search, 
  FileText, 
  ShieldAlert, 
  ArrowRight, 
  Loader2, 
  Sparkles, 
  BookOpen, 
  ListFilter, 
  ChevronDown, 
  ChevronUp, 
  Wand2 
} from 'lucide-react';
import { api } from '../api';

const SUGGESTED_QUERIES = [
  "Termination clauses with more than 30 days notice",
  "How did we handle indemnification in the Acme Corp deal?",
  "Limitation of liability caps exceeding one million dollars",
];

// Helper to highlight terms in match text dynamically
const highlightText = (text, query) => {
  if (!text) return '';
  if (!query || !query.trim()) return text;
  
  // Tokenize query into search terms, removing common stop words
  const stopWords = new Set([
    'what', 'is', 'a', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 
    'with', 'by', 'of', 'about', 'how', 'did', 'we', 'handle', 'under', 
    'clause', 'clauses', 'contract', 'agreement'
  ]);
  
  const terms = query
    .toLowerCase()
    .split(/[^a-zA-Z0-9]+/)
    .filter(term => term.length > 2 && !stopWords.has(term));
    
  if (terms.length === 0) return text;
  
  // Build a safe regex pattern combining all terms
  const pattern = terms.map(term => term.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')).join('|');
  const regex = new RegExp(`(${pattern})`, 'gi');
  const parts = text.split(regex);
  
  return (
    <span>
      {parts.map((part, i) => 
        regex.test(part) ? (
          <mark key={i} className="search-highlight">{part}</mark>
        ) : (
          part
        )
      )}
    </span>
  );
};

// Interactive result card managing its own explanation/redraft state
function MatchCard({ match, query }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [explanation, setExplanation] = useState('');
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [redraft, setRedraft] = useState('');
  const [redraftLoading, setRedraftLoading] = useState(false);
  const [activeAction, setActiveAction] = useState(null); // 'explain', 'redraft', or null

  const level = match.metadata?.risk_level || 'LOW';

  const formatClauseType = (value) =>
    (value || 'General Clause').replace(/\bclause\b/gi, '').replace(/\s+/g, ' ').trim();

  const handleExplain = async (e) => {
    e.stopPropagation(); // Block card collapse trigger
    if (activeAction === 'explain') {
      setActiveAction(null);
      return;
    }
    setActiveAction('explain');
    if (explanation) return;

    setExplanationLoading(true);
    try {
      const response = await api.post('/api/explain-clause', {
        clause_text: match.text,
        clause_type: match.metadata?.clause_type || 'General',
        risk_level: level,
        risk_reason: match.metadata?.risk_reason || '',
      });
      setExplanation(response.data.explanation || 'No explanation was generated.');
    } catch (err) {
      setExplanation('The explanation service is unavailable right now.');
    } finally {
      setExplanationLoading(false);
    }
  };

  const handleRedraft = async (e) => {
    e.stopPropagation(); // Block card collapse trigger
    if (activeAction === 'redraft') {
      setActiveAction(null);
      return;
    }
    setActiveAction('redraft');
    if (redraft) return;

    setRedraftLoading(true);
    try {
      const response = await api.post('/api/redraft-clause', {
        clause_text: match.text,
        clause_type: match.metadata?.clause_type || 'General',
        risk_level: level,
        risk_reason: match.metadata?.risk_reason || '',
        recommendations: [],
      });
      setRedraft(response.data.redraft || 'No redraft was generated.');
    } catch (err) {
      setRedraft('The redraft service is unavailable right now.');
    } finally {
      setRedraftLoading(false);
    }
  };

  const formattedDate = match.metadata?.ingested_at 
    ? new Date(match.metadata.ingested_at).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    : '';

  return (
    <article 
      className={`search-match-card risk-${level.toLowerCase()} ${isExpanded ? 'is-expanded' : ''}`}
      onClick={() => setIsExpanded(!isExpanded)}
    >
      <div className="match-card-header">
        <div className="document-identity">
          <FileText size={18} className="doc-icon" />
          <div>
            <h3>{match.metadata?.source_filename || 'Unnamed Contract'}</h3>
            <small>
              {formatClauseType(match.metadata?.clause_type)}
              {match.metadata?.jurisdiction && match.metadata.jurisdiction !== 'unspecified' ? ` · ${match.metadata.jurisdiction}` : ''}
              {match.metadata?.page_number ? ` · Page ${match.metadata.page_number}` : ''}
            </small>
          </div>
        </div>
        <div className="match-score-badge">
          <Sparkles size={14} />
          <span>{match.similarity_percent || Math.round((match.score || 0) * 100)}% Match</span>
        </div>
      </div>

      <p className="match-extracted-text">
        "{highlightText(match.text, query)}"
      </p>

      {match.metadata?.risk_reason && (
        <div className="match-context-footer">
          <ShieldAlert size={15} />
          <span><strong>Risk Context:</strong> {match.metadata.risk_reason}</span>
        </div>
      )}

      <div className="match-card-expand-indicator">
        {isExpanded ? (
          <>
            <span>Hide interactive workspace</span>
            <ChevronUp size={14} />
          </>
        ) : (
          <>
            <span>Expand clause actions & metadata</span>
            <ChevronDown size={14} />
          </>
        )}
      </div>

      {isExpanded && (
        <div className="match-card-details" onClick={(e) => e.stopPropagation()}>
          <div className="match-metadata-grid">
            <div className="match-metadata-item">
              <span>Jurisdiction</span>
              <strong>{match.metadata?.jurisdiction || 'Unspecified'}</strong>
            </div>
            <div className="match-metadata-item">
              <span>Location</span>
              <strong>
                {match.metadata?.page_number ? `Page ${match.metadata.page_number}` : 'N/A'}
                {match.metadata?.clause_index ? `, Clause ${match.metadata.clause_index}` : ''}
              </strong>
            </div>
            {formattedDate && (
              <div className="match-metadata-item">
                <span>Ingested At</span>
                <strong>{formattedDate}</strong>
              </div>
            )}
            <div className="match-metadata-item">
              <span>Char Count</span>
              <strong>{match.metadata?.character_count || match.text?.length || 0} characters</strong>
            </div>
          </div>

          <div className="match-card-actions">
            <button 
              type="button" 
              className={`text-button ${activeAction === 'explain' ? 'active' : ''}`}
              onClick={handleExplain}
              disabled={explanationLoading}
            >
              {explanationLoading ? (
                <Loader2 size={15} className="spin-icon" />
              ) : (
                <Sparkles size={15} />
              )}
              {activeAction === 'explain' ? 'Hide explanation' : 'Explain simply'}
            </button>
            <button 
              type="button" 
              className={`text-button ${activeAction === 'redraft' ? 'active' : ''}`}
              onClick={handleRedraft}
              disabled={redraftLoading}
            >
              {redraftLoading ? (
                <Loader2 size={15} className="spin-icon" />
              ) : (
                <Wand2 size={15} />
              )}
              {activeAction === 'redraft' ? 'Hide redraft' : 'Suggest redraft'}
            </button>
          </div>

          {activeAction === 'explain' && (
            <div className="action-result animate-slide-up">
              {explanationLoading ? 'Creating explanation…' : explanation}
            </div>
          )}

          {activeAction === 'redraft' && (
            <div className="action-result redraft-result animate-slide-up">
              {redraftLoading ? 'Creating redraft…' : redraft}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [searchMetrics, setSearchMetrics] = useState(null);
  
  // Library status (metrics & file list)
  const [libraryStatus, setLibraryStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [libraryError, setLibraryError] = useState('');

  // UI state toggles
  const [groupByDoc, setGroupByDoc] = useState(false);

  // Filters state
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [selectedClauseTypes, setSelectedClauseTypes] = useState([]);
  const [selectedJurisdictions, setSelectedJurisdictions] = useState([]);

  const fetchLibraryStatus = async () => {
    try {
      setLoadingStatus(true);
      setLibraryError('');
      const response = await api.get('/api/clause-library/status');
      setLibraryStatus(response.data);
    } catch (err) {
      console.error('Failed to load library metrics:', err);
      setLibraryError('Failed to load library database statistics.');
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchLibraryStatus();
  }, []);

  const handleSearch = async (searchQuery) => {
    const textToSearch = searchQuery || query;
    if (!textToSearch.trim()) return;

    setLoading(true);
    try {
      // Fetch larger candidate pool (20) to filter correctly on client-side
      const response = await api.post('/api/global-search', {
        query: textToSearch,
        top_k: 20,
      });

      setResults(response.data?.matches || []);
      setSearchMetrics({
        totalFound: response.data?.total_matches || response.data?.matches?.length || 0,
        latency: response.data?.execution_time_ms || 35, 
      });
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Collect unique properties from search results for dynamic filter checkboxes
  const availableClauseTypes = [...new Set(results.map(r => r.metadata?.clause_type).filter(Boolean))].sort();
  const availableJurisdictions = [...new Set(results.map(r => r.metadata?.jurisdiction).filter(Boolean))].sort();

  const handleResetFilters = () => {
    setSelectedDocs([]);
    setSelectedClauseTypes([]);
    setSelectedJurisdictions([]);
  };

  // Client-side filtering implementation
  const filteredResults = results.filter(match => {
    if (selectedDocs.length > 0 && !selectedDocs.includes(match.metadata?.document_hash)) {
      return false;
    }
    if (selectedClauseTypes.length > 0 && !selectedClauseTypes.includes(match.metadata?.clause_type)) {
      return false;
    }
    if (selectedJurisdictions.length > 0 && !selectedJurisdictions.includes(match.metadata?.jurisdiction)) {
      return false;
    }
    return true;
  });

  const visibleCount = filteredResults.length;

  return (
    <div className="search-dashboard-container">
      <header className="search-header">
        <span className="eyebrow-tag">Library Intelligence</span>
        <h1>Ask Your Contract Library</h1>
        <p>Search semantically across every contract, clause, and legal file your team has ever uploaded.</p>
      </header>

      <div className="search-layout-grid animate-slide-up">
        {/* SIDEBAR */}
        <aside className="search-sidebar">
          {/* Library Status metrics card */}
          <section className="search-sidebar-panel">
            <h3>
              <BookOpen size={16} />
              <span>Library Status</span>
            </h3>
            {loadingStatus ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--muted)', fontSize: '0.82rem' }}>
                <Loader2 size={16} className="spin-icon" />
                <span>Loading metrics...</span>
              </div>
            ) : libraryError ? (
              <div style={{ color: 'var(--high)', fontSize: '0.82rem' }}>{libraryError}</div>
            ) : (
              <div className="search-stats-grid">
                <div className="search-stat-card">
                  <strong>{libraryStatus?.document_count || 0}</strong>
                  <span>Contracts</span>
                </div>
                <div className="search-stat-card">
                  <strong>{libraryStatus?.clause_count || 0}</strong>
                  <span>Clauses</span>
                </div>
              </div>
            )}
          </section>

          {/* Search Filters Checkboxes sidebar */}
          <section className="search-sidebar-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>
              <h3 style={{ border: 'none', margin: 0, padding: 0 }}>
                <ListFilter size={16} />
                <span>Search Filters</span>
              </h3>
              {(selectedDocs.length > 0 || selectedClauseTypes.length > 0 || selectedJurisdictions.length > 0) && (
                <button 
                  type="button" 
                  onClick={handleResetFilters}
                  style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '0.72rem', fontWeight: 700, cursor: 'pointer', padding: 0 }}
                >
                  Reset
                </button>
              )}
            </div>

            {/* Document checklist filter */}
            <div className="filter-group">
              <span className="filter-group-title">Filter by Document</span>
              {loadingStatus ? (
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>Loading documents...</span>
              ) : !libraryStatus?.documents?.length ? (
                <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>No documents saved.</span>
              ) : (
                <div className="filter-checkbox-list">
                  {libraryStatus.documents.map(doc => (
                    <label key={doc.document_hash} className="filter-checkbox-item">
                      <input 
                        type="checkbox" 
                        checked={selectedDocs.includes(doc.document_hash)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDocs([...selectedDocs, doc.document_hash]);
                          } else {
                            setSelectedDocs(selectedDocs.filter(hash => hash !== doc.document_hash));
                          }
                        }}
                      />
                      <span className="filter-checkbox-text" title={doc.source}>{doc.source}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Dynamic Clause type checklist filter */}
            {availableClauseTypes.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-title">Filter by Clause Type</span>
                <div className="filter-checkbox-list">
                  {availableClauseTypes.map(cType => (
                    <label key={cType} className="filter-checkbox-item">
                      <input 
                        type="checkbox" 
                        checked={selectedClauseTypes.includes(cType)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedClauseTypes([...selectedClauseTypes, cType]);
                          } else {
                            setSelectedClauseTypes(selectedClauseTypes.filter(t => t !== cType));
                          }
                        }}
                      />
                      <span className="filter-checkbox-text">{cType}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Dynamic Jurisdiction checklist filter */}
            {availableJurisdictions.length > 0 && (
              <div className="filter-group">
                <span className="filter-group-title">Filter by Jurisdiction</span>
                <div className="filter-checkbox-list">
                  {availableJurisdictions.map(juris => (
                    <label key={juris} className="filter-checkbox-item">
                      <input 
                        type="checkbox" 
                        checked={selectedJurisdictions.includes(juris)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedJurisdictions([...selectedJurisdictions, juris]);
                          } else {
                            setSelectedJurisdictions(selectedJurisdictions.filter(j => j !== juris));
                          }
                        }}
                      />
                      <span className="filter-checkbox-text">{juris}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </section>
        </aside>

        {/* MAIN SEARCH PANEL */}
        <main className="search-main-content">
          <section className="search-input-wrapper">
            <div className="input-bar-container">
              <Search className="search-icon-hint" size={22} />
              <input
                type="text"
                placeholder="Type a question or legal concept (e.g., 'IP ownership under contractor agreements')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
              <button 
                type="button" 
                className="search-submit-btn" 
                onClick={() => handleSearch()} 
                disabled={loading}
              >
                {loading ? <Loader2 size={18} className="spin-icon" /> : <ArrowRight size={18} />}
              </button>
            </div>

            <div className="suggestions-row">
              <span>Try searching:</span>
              {SUGGESTED_QUERIES.map((suggestion, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="suggestion-chip"
                  onClick={() => {
                    setQuery(suggestion);
                    handleSearch(suggestion);
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>

          {/* Results controls: group switch & metrics */}
          {searchMetrics && (
            <div className="search-controls-bar animate-slide-up">
              <div className="search-meta-summary">
                Found {searchMetrics.totalFound} matches in {searchMetrics.latency}ms
                {visibleCount !== searchMetrics.totalFound && (
                  <span> ({visibleCount} shown after filtering)</span>
                )}
              </div>
              <div className="search-toggles">
                <button 
                  type="button" 
                  className={`toggle-btn ${!groupByDoc ? 'active' : ''}`}
                  onClick={() => setGroupByDoc(false)}
                >
                  Flat List
                </button>
                <button 
                  type="button" 
                  className={`toggle-btn ${groupByDoc ? 'active' : ''}`}
                  onClick={() => setGroupByDoc(true)}
                >
                  Group by Document
                </button>
              </div>
            </div>
          )}

          {/* Search loader spinner state */}
          {loading && (
            <div className="search-loader-state">
              <Loader2 size={32} className="spin-icon master-spinner" />
              <p>Scanning vector indexes and running keyword fusion paths...</p>
            </div>
          )}

          {/* Results displays */}
          {!loading && results.length > 0 && (
            <div className="search-results-list animate-slide-up">
              {groupByDoc ? (
                // Grouped by document layout
                Object.entries(
                  filteredResults.reduce((acc, match) => {
                    const docName = match.metadata?.source_filename || match.metadata?.source || 'Unnamed Document';
                    if (!acc[docName]) acc[acc[docName] = []] = acc[docName] || []; // safe mapping init
                    acc[docName].push(match);
                    return acc;
                  }, {})
                ).map(([docName, matches]) => (
                  <div key={docName} className="search-document-group">
                    <div className="search-document-group-header">
                      <div className="search-document-group-title">
                        <FileText size={18} className="doc-icon" />
                        <h3>{docName}</h3>
                      </div>
                      <span className="search-document-group-badge">
                        {matches.length} {matches.length === 1 ? 'match' : 'matches'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                      {matches.map(match => (
                        <MatchCard 
                          key={match.id} 
                          match={match} 
                          query={query} 
                        />
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                // Flat layout results list
                filteredResults.map(match => (
                  <MatchCard 
                    key={match.id} 
                    match={match} 
                    query={query} 
                  />
                ))
              )}

              {filteredResults.length === 0 && (
                <div className="search-empty-state">
                  <h3>No matches match your filter criteria</h3>
                  <p>Try resetting some filters in the sidebar to view all relevant matches.</p>
                </div>
              )}
            </div>
          )}

          {/* Search performed but returned no records */}
          {!loading && searchMetrics && results.length === 0 && (
            <div className="search-empty-state">
              <h3>No conceptual matches found</h3>
              <p>Try rephrasing your question or using clear keyword phrases to expand the hybrid search path scope.</p>
            </div>
          )}

          {/* Default initial landing state */}
          {!loading && !searchMetrics && (
            <div className="search-empty-state" style={{ padding: '64px 32px' }}>
              <BookOpen size={48} style={{ color: 'var(--primary)', marginBottom: '16px', opacity: 0.8 }} />
              <h3>Search your private database</h3>
              <p>Type a natural language query above to scan your entire library of contracts using AI semantics.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}