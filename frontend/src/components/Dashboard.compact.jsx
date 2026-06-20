import { useId, useState } from 'react';
import {
  BookOpen,
  Check,
  ChevronDown,
  Download,
  FileText,
  Loader2,
  Sparkles,
  Wand2,
} from 'lucide-react';
import { api } from '../api';

const RISK_COPY = {
  HIGH: { label: 'Needs attention', short: 'High' },
  MEDIUM: { label: 'Review advised', short: 'Medium' },
  LOW: { label: 'Looks standard', short: 'Low' },
};

const RiskBadge = ({ level = 'LOW' }) => (
  <span className={`risk-badge ${level.toLowerCase()}`}>
    <span className="risk-dot" />
    {RISK_COPY[level]?.label || level}
  </span>
);

const downloadAsPDF = (filename) => {
  const previousTitle = document.title;
  document.title = `${filename || 'Legal document'} review`;
  window.print();
  document.title = previousTitle;
};

const extractAnalysis = (data) =>
  data?.results?.contract_analysis ||
  data?.content?.contract_analysis ||
  data?.contract_analysis ||
  {};

const extractSummary = (data) =>
  data?.results?.summary_data?.final_summary ||
  data?.content?.summary_data?.final_summary ||
  data?.summary_data?.final_summary ||
  '';

const formatClauseType = (value) =>
  (value || 'Unclassified clause').replace(/\bclause\b/gi, '').replace(/\s+/g, ' ').trim();

const ClauseAction = ({ icon, children, onClick, loading, active, variant = 'secondary' }) => (
  <button type="button" className={`text-button ${variant} ${active ? 'active' : ''}`} onClick={onClick} disabled={loading}>
    {loading ? <Loader2 size={15} className="spin-icon" /> : icon}
    {children}
  </button>
);

const ClauseCard = ({ clause, number, documentHash, sourceFilename }) => {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [explanation, setExplanation] = useState('');
  const [explanationOpen, setExplanationOpen] = useState(false);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [redraft, setRedraft] = useState('');
  const [redraftOpen, setRedraftOpen] = useState(false);
  const [redraftLoading, setRedraftLoading] = useState(false);
  const [similarResult, setSimilarResult] = useState(null);
  const [similarOpen, setSimilarOpen] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
  const detailsId = useId();

  const recommendations = (clause.recommendations || []).filter(Boolean);
  const matchedRules = clause.matched_rules || [];
  const positiveSignals = clause.positive_signals || [];
  const level = clause.risk_level || 'LOW';

  const explain = async () => {
    if (explanation) {
      setExplanationOpen(!explanationOpen);
      return;
    }
    setExplanationLoading(true);
    setExplanationOpen(true);
    try {
      const response = await api.post('/api/explain-clause', {
        clause_text: clause.clause_text,
        clause_type: clause.type,
        risk_level: level,
        risk_reason: clause.risk_reason,
      });
      setExplanation(response.data.explanation || 'No explanation was generated.');
    } catch {
      setExplanation('The explanation service is unavailable right now.');
    } finally {
      setExplanationLoading(false);
    }
  };

  const createRedraft = async () => {
    if (redraft) {
      setRedraftOpen(!redraftOpen);
      return;
    }
    setRedraftLoading(true);
    setRedraftOpen(true);
    try {
      const response = await api.post('/api/redraft-clause', {
        clause_text: clause.clause_text,
        clause_type: clause.type,
        risk_level: level,
        risk_reason: clause.risk_reason,
        recommendations,
      });
      setRedraft(response.data.redraft || 'No redraft was generated.');
    } catch {
      setRedraft('The redraft service is unavailable right now.');
    } finally {
      setRedraftLoading(false);
    }
  };

  const findSimilar = async () => {
    if (similarResult) {
      setSimilarOpen(!similarOpen);
      return;
    }
    setSimilarLoading(true);
    setSimilarOpen(true);
    try {
      const response = await api.post('/api/similar-clauses', {
        clause_text: clause.clause_text,
        clause_type: clause.type,
        exclude_document_hash: documentHash || '',
        exclude_source: sourceFilename || '',
        top_k: 3,
      });
      setSimilarResult(response.data);
    } catch {
      setSimilarResult({
        status: 'error',
        matches: [],
        message: 'The private clause library is unavailable right now.',
      });
    } finally {
      setSimilarLoading(false);
    }
  };

  return (
    <article className={`clause-card risk-${level.toLowerCase()}`}>
      <div className="clause-topline">
        <div>
          <span className="clause-number">Clause {number}</span>
          <h3>{formatClauseType(clause.type)}</h3>
        </div>
        <RiskBadge level={level} />
      </div>

      <p className="clause-summary">{clause.risk_summary || clause.risk_reason}</p>
      {recommendations[0] && (
        <div className="next-step">
          <Check size={16} />
          <span>{recommendations[0]}</span>
        </div>
      )}

      <button
        type="button"
        className="details-toggle"
        onClick={() => setDetailsOpen(!detailsOpen)}
        aria-expanded={detailsOpen}
        aria-controls={detailsId}
      >
        {detailsOpen ? 'Hide clause' : 'View clause and details'}
        <ChevronDown size={16} className={detailsOpen ? 'rotate' : ''} />
      </button>

      {detailsOpen && (
        <div className="clause-details" id={detailsId}>
          <div className="clause-text">
            <span>Original clause</span>
            <p>{clause.clause_text}</p>
          </div>

          {(matchedRules.length > 0 || positiveSignals.length > 0) && (
            <div className="signals-grid">
              {matchedRules.length > 0 && (
                <div>
                  <span className="detail-label">Why it was flagged</span>
                  <ul>{matchedRules.map((rule) => <li key={rule.rule_id || rule.label}>{rule.label}</li>)}</ul>
                </div>
              )}
              {positiveSignals.length > 0 && (
                <div>
                  <span className="detail-label">Protective language</span>
                  <ul>{positiveSignals.map((signal) => <li key={signal.label}>{signal.label}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          <div className="clause-actions">
            <ClauseAction icon={<Sparkles size={15} />} onClick={explain} loading={explanationLoading} active={explanationOpen}>
              {explanationOpen ? 'Hide explanation' : 'Explain simply'}
            </ClauseAction>
            {level !== 'LOW' && (
              <ClauseAction icon={<Wand2 size={15} />} onClick={createRedraft} loading={redraftLoading} active={redraftOpen}>
                {redraftOpen ? 'Hide redraft' : 'Suggest redraft'}
              </ClauseAction>
            )}
            <ClauseAction icon={<BookOpen size={15} />} onClick={findSimilar} loading={similarLoading} active={similarOpen}>
              {similarOpen ? 'Hide similar clauses' : 'Search private library'}
            </ClauseAction>
          </div>

          {explanationOpen && <div className="action-result">{explanationLoading ? 'Creating explanation…' : explanation}</div>}
          {redraftOpen && <div className="action-result redraft-result">{redraftLoading ? 'Creating redraft…' : redraft}</div>}
          {similarOpen && (
            <div className="action-result">
              {similarLoading && 'Searching your private clause library…'}
              {!similarLoading && similarResult?.matches?.length === 0 && (
                <div className="library-empty">
                  <strong>No sufficiently similar clauses found.</strong>
                  <span>{similarResult?.message || 'Add more contracts to your private library to improve coverage.'}</span>
                </div>
              )}
              {!similarLoading && similarResult?.matches?.length > 0 && (
                <div className="library-disclaimer">{similarResult.message}</div>
              )}
              {!similarLoading && similarResult?.matches?.map((item) => (
                <div className="precedent-item" key={item.id}>
                  <div className="precedent-heading">
                    <strong>{item.metadata?.source || 'Past document'}</strong>
                    <span>{item.similarity_percent}% similar</span>
                  </div>
                  <small>
                    {formatClauseType(item.metadata?.clause_type)}
                    {item.metadata?.jurisdiction && item.metadata.jurisdiction !== 'unspecified'
                      ? ` · ${item.metadata.jurisdiction}`
                      : ''}
                    {item.metadata?.page_number > 0 ? ` · Page ${item.metadata.page_number}` : ''}
                    {item.metadata?.clause_index ? ` · Clause ${item.metadata.clause_index}` : ''}
                  </small>
                  <span>{item.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  );
};

const Dashboard = ({ data }) => {
  const [riskFilter, setRiskFilter] = useState('ALL');
  const analysis = extractAnalysis(data);
  const metadata =
    data?.results?.metadata ||
    data?.content?.metadata ||
    data?.metadata ||
    {};
  const clauses = analysis.analyzed_clauses || [];
  const isSummary = data?.task === 'summarize_case' || data?.type === 'summary';

  if (isSummary) {
    return (
      <div className="report-shell">
        <div className="report-header">
          <div>
            <span className="eyebrow">Document summary</span>
            <h2>{data?.filename || 'Uploaded document'}</h2>
            <p>A concise AI-generated overview of the document.</p>
          </div>
          <button className="secondary-button" onClick={() => downloadAsPDF(data?.filename)}>
            <Download size={17} /> Save as PDF
          </button>
        </div>
        <article className="summary-document">
          <FileText size={22} />
          <div>{extractSummary(data) || 'No summary was generated.'}</div>
        </article>
      </div>
    );
  }

  const counts = {
    HIGH: clauses.filter((clause) => clause.risk_level === 'HIGH').length,
    MEDIUM: clauses.filter((clause) => clause.risk_level === 'MEDIUM').length,
    LOW: clauses.filter((clause) => clause.risk_level === 'LOW').length,
  };

  const filtered = riskFilter === 'ALL'
    ? clauses
    : clauses.filter((clause) => clause.risk_level === riskFilter);

  const keyRecommendations = [...new Set(
    clauses
      .filter((clause) => clause.risk_level !== 'LOW')
      .flatMap((clause) => clause.recommendations || [])
      .filter(Boolean)
  )].slice(0, 3);

  return (
    <>
      {/* 1. SCREEN VIEW LAYER (Visible in Web UI Browser only) */}
      <div className="report-shell screen-only" id="dashboard-pdf-root">
        <div className="report-header">
          <div>
            <span className="eyebrow">Contract review</span>
            <h2>{data?.filename || 'Uploaded document'}</h2>
            <p>{clauses.length} clauses reviewed. Focus on the items that may need a closer look.</p>
          </div>
          <button className="secondary-button" onClick={() => downloadAsPDF(data?.filename)}>
            <Download size={17} /> Save as PDF
          </button>
        </div>

        <section className="overview-card">
          <div className="overview-score">
            <span>Review overview</span>
            <strong>{counts.HIGH > 0 ? 'Action recommended' : counts.MEDIUM > 0 ? 'Some review advised' : 'No major flags'}</strong>
            <p>Automated issue-spotting, not a legal conclusion.</p>
          </div>
          <div className="risk-counts">
            {['HIGH', 'MEDIUM', 'LOW'].map((level) => (
              <div key={level} className={`risk-count ${level.toLowerCase()}`}>
                <strong>{counts[level]}</strong>
                <span>{RISK_COPY[level].short}</span>
              </div>
            ))}
          </div>
        </section>

        {keyRecommendations.length > 0 && (
          <section className="priority-card">
            <span className="section-label">Start here</span>
            <h3>Key points to review</h3>
            <ul>{keyRecommendations.map((item) => <li key={item}>{item}</li>)}</ul>
          </section>
        )}

        <section className="clauses-section">
          {data?.libraryIndexing === 'scheduled' && (
            <div className="library-status">
              <BookOpen size={16} />
              This document is being added to your private clause library.
            </div>
          )}
          <div className="section-heading">
            <div>
              <span className="section-label">Clause review</span>
              <h3>Review by priority</h3>
            </div>
            <div className="filter-tabs" aria-label="Filter clauses by risk">
              {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((level) => (
                <button
                  key={level}
                  type="button"
                  className={riskFilter === level ? 'active' : ''}
                  onClick={() => setRiskFilter(level)}
                >
                  {level === 'ALL' ? `All ${clauses.length}` : `${RISK_COPY[level].short} ${counts[level]}`}
                </button>
              ))}
            </div>
          </div>

          <div className="clause-list">
            {filtered.map((clause) => {
              const originalIndex = clauses.indexOf(clause);
              return (
                <ClauseCard
                  key={`clause-${originalIndex}`}
                  clause={clause}
                  number={originalIndex + 1}
                  documentHash={metadata.document_hash}
                  sourceFilename={metadata.source_filename || data?.filename}
                />
              );
            })}
            {filtered.length === 0 && <div className="empty-state">No clauses in this category.</div>}
          </div>
        </section>
      </div>

      {/* 2. PRINT DESIGN LAYER (Hidden on screen, generated perfectly into the PDF structure) */}
      <div className="print-only-template">
        <div className="print-pdf-header">
          <h1>Contract Review Audit Report</h1>
          <p className="print-meta-line"><strong>Source Document:</strong> {data?.filename || 'Legal Document'}</p>
          <p className="print-meta-line"><strong>Total Clauses Flagged:</strong> {clauses.length}</p>
        </div>

        <div className="print-metrics-summary">
          <div className="print-metric-box high-risk">Needs Attention (High): {counts.HIGH}</div>
          <div className="print-metric-box medium-risk">Review Advised (Medium): {counts.MEDIUM}</div>
          <div className="print-metric-box low-risk">Standard Flags (Low): {counts.LOW}</div>
        </div>

        {/* High Risk Items Chapter */}
        {counts.HIGH > 0 && (
          <section className="print-pdf-section">
            <h2 className="print-section-heading high">1. High Risk Items (Action Recommended)</h2>
            {clauses.filter(c => c.risk_level === 'HIGH').map((clause) => {
              const idx = clauses.indexOf(clause);
              return (
                <div key={`print-high-${idx}`} className="print-clause-item-block high">
                  <h3>Clause {idx + 1}: {formatClauseType(clause.type)}</h3>
                  <p className="print-risk-explanation"><strong>Risk Reason:</strong> {clause.risk_summary || clause.risk_reason}</p>
                  {clause.recommendations?.[0] && <p className="print-recom"><strong>Recommendation:</strong> {clause.recommendations[0]}</p>}
                  <blockquote className="print-original-text">"{clause.clause_text}"</blockquote>
                </div>
              );
            })}
          </section>
        )}

        {/* Medium Risk Items Chapter */}
        {counts.MEDIUM > 0 && (
          <section className="print-pdf-section">
            <h2 className="print-section-heading medium">2. Medium Risk Items (Review Advised)</h2>
            {clauses.filter(c => c.risk_level === 'MEDIUM').map((clause) => {
              const idx = clauses.indexOf(clause);
              return (
                <div key={`print-med-${idx}`} className="print-clause-item-block medium">
                  <h3>Clause {idx + 1}: {formatClauseType(clause.type)}</h3>
                  <p className="print-risk-explanation"><strong>Analysis Notes:</strong> {clause.risk_summary || clause.risk_reason}</p>
                  {clause.recommendations?.[0] && <p className="print-recom"><strong>Recommendation:</strong> {clause.recommendations[0]}</p>}
                  <blockquote className="print-original-text">"{clause.clause_text}"</blockquote>
                </div>
              );
            })}
          </section>
        )}

        {/* Low Risk Items Chapter */}
        {counts.LOW > 0 && (
          <section className="print-pdf-section">
            <h2 className="print-section-heading low">3. Standard / Low Risk Items</h2>
            {clauses.filter(c => c.risk_level === 'LOW').map((clause) => {
              const idx = clauses.indexOf(clause);
              return (
                <div key={`print-low-${idx}`} className="print-clause-item-block low">
                  <h3>Clause {idx + 1}: {formatClauseType(clause.type)}</h3>
                  <blockquote className="print-original-text">"{clause.clause_text}"</blockquote>
                </div>
              );
            })}
          </section>
        )}
      </div>
    </>
  );
};

export default Dashboard;