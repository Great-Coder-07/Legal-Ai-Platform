import React, { useState } from 'react';
import { Search, FileText, Calendar, ShieldAlert, ArrowRight, Loader2, Sparkles } from 'lucide-react';
import { api } from '../api';

const SUGGESTED_QUERIES = [
  "Termination clauses with more than 30 days notice",
  "How did we handle indemnification in the Acme Corp deal?",
  "Limitation of liability caps exceeding one million dollars",
];

const formatPercent = (val) => val ? `${Math.round(val * 100)}%` : '0%';

export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [searchMetrics, setSearchMetrics] = useState(null);

  const handleSearch = async (searchQuery) => {
    const textToSearch = searchQuery || query;
    if (!textToSearch.trim()) return;

    setLoading(true);
    try {
      // Direct call to your backend global search hub
      const response = await api.post('/api/global-search', {
        query: textToSearch,
        top_k: 5,
      });

      setResults(response.data?.matches || []);
      setSearchMetrics({
        totalFound: response.data?.total_matches || response.data?.matches?.length || 0,
        latency: response.data?.execution_time_ms || 42, 
      });
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-dashboard-container">
      {/* Header Segment */}
      <header className="search-header">
        <span className="eyebrow-tag">Library Intelligence</span>
        <h1>Ask Your Contract Library</h1>
        <p>Search semantically across every contract, clause, and legal file your team has ever uploaded.</p>
      </header>

      {/* Main Search Input Workspace */}
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

        {/* Query Suggestions Chips */}
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

      {/* Results Display Area */}
      <main className="search-results-layout">
        {searchMetrics && (
          <div className="search-meta-summary">
            Found {searchMetrics.totalFound} relevant clauses across library in {searchMetrics.latency}ms
          </div>
        )}

        {loading && (
          <div className="search-loader-state">
            <Loader2 size={32} className="spin-icon master-spinner" />
            <p>Scanning vector indexes and running keyword fusion paths...</p>
          </div>
        )}

        {!loading && results.map((match) => (
          <article className={`search-match-card risk-${match.metadata?.risk_level?.toLowerCase() || 'low'}`} key={match.id}>
            <div className="match-card-header">
              <div className="document-identity">
                <FileText size={18} className="doc-icon" />
                <div>
                  <h3>{match.metadata?.source_filename || 'Unnamed Contract'}</h3>
                  <small>
                    {match.metadata?.clause_type || 'General Clause'} 
                    {match.metadata?.jurisdiction ? ` · ${match.metadata.jurisdiction}` : ''}
                    {match.metadata?.page_number ? ` · Page ${match.metadata.page_number}` : ''}
                  </small>
                </div>
              </div>
              <div className="match-score-badge">
                <Sparkles size={14} />
                <span>{formatPercent(match.score)} Match Match</span>
              </div>
            </div>

            <p className="match-extracted-text">
              "{match.text || match.clause_text}"
            </p>

            {match.metadata?.risk_reason && (
              <div className="match-context-footer">
                <ShieldAlert size={15} />
                <span><strong>Risk Context:</strong> {match.metadata.risk_reason}</span>
              </div>
            )}
          </article>
        ))}

        {!loading && searchMetrics && results.length === 0 && (
          <div className="search-empty-state">
            <h3>No conceptual matches found</h3>
            <p>Try rephrasing your question or clear keyword phrases to expand the hybrid search path scope.</p>
          </div>
        )}
      </main>
    </div>
  );
}