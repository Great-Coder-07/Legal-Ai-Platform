import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';
import { Key, Trash2, Shield, Folder, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function ProfileSection() {
  const { user } = useAuth();
  const [libraryStatus, setLibraryStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  
  // Password Change States
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passError, setPassError] = useState('');
  const [passSuccess, setPassSuccess] = useState('');
  const [passLoading, setPassLoading] = useState(false);

  // Load Library metrics scoped to this authenticated user tenant
  const fetchLibraryStatus = async () => {
    try {
      setLoadingStatus(true);
      const response = await api.get('/api/clause-library/status');
      setLibraryStatus(response.data);
    } catch (err) {
      console.error("Failed to fetch tenant library status:", err);
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchLibraryStatus();
  }, []);

  // Handle password modification submit execution
  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPassError('');
    setPassSuccess('');
    setPassLoading(true);

    try {
      const response = await api.post('/api/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      });
      setPassSuccess(response.data.message || 'Password updated successfully.');
      setOldPassword('');
      setNewPassword('');
    } catch (err) {
      setPassError(err.response?.data?.detail || 'Could not change password.');
    } finally {
      setPassLoading(false);
    }
  };

  // Securely delete document chunks from active tenant library scope
  const handleDeleteDocument = async (documentHash) => {
    if (!window.confirm("Are you sure you want to permanently remove this document and all its matching vector clauses?")) return;
    
    try {
      await api.delete(`/api/clause-library/documents/${documentHash}`);
      // Refresh statistics counts array dynamically
      fetchLibraryStatus();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to drop document target pipeline.");
    }
  };

  return (
    <div className="profile-layout animate-slide-up" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      
      {/* SECTION HEADER BLOCK ROW */}
      <div className="section-heading" style={{ marginBottom: '2rem' }}>
        <div>
          <span className="section-label">Account Settings</span>
          <h3>User Profile & Storage Center</h3>
          <p style={{ color: 'var(--text-secondary)' }}>Manage your personal tenant settings and private RAG vector allocations.</p>
        </div>
      </div>

      <div className="profile-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        
        {/* LEFT COLUMN: MANAGE PRIVATE CLAUSE LIBRARY */}
        <section className="glass-panel" style={{ padding: '2rem' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1.5rem', fontSize: '18px' }}>
            <Folder size={20} style={{ color: 'var(--accent-color, #007bff)' }} />
            Manage Private Clause Library
          </h2>

          {loadingStatus ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
              <Loader2 className="spin-icon" size={32} />
            </div>
          ) : (
            <>
              {/* STATUS MATRIX METRICS BAR COUNTS */}
              <div className="metrics-summary" style={{ display: 'flex', gap: '1.5rem', marginBottom: '2rem' }}>
                <div className="metric-box" style={{ flex: 1, padding: '1rem', background: 'rgba(0,0,0,0.02)', borderRadius: '6px', textAlign: 'center' }}>
                  <strong style={{ fontSize: '24px', display: 'block' }}>{libraryStatus?.document_count || 0}</strong>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Documents</span>
                </div>
                <div className="metric-box" style={{ flex: 1, padding: '1rem', background: 'rgba(0,0,0,0.02)', borderRadius: '6px', textAlign: 'center' }}>
                  <strong style={{ fontSize: '24px', display: 'block' }}>{libraryStatus?.clause_count || 0}</strong>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Clauses</span>
                </div>
              </div>

              {/* DOCUMENTS DATA LIST GENERATOR */}
              <h4 style={{ marginBottom: '1rem', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Uploaded Documents Registry</h4>
              
              {!libraryStatus?.documents || libraryStatus.documents.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem', textAlign: 'center', border: '1px dashed #ccc', borderRadius: '6px' }}>
                  <FileText size={32} style={{ color: '#ccc', marginBottom: '0.5rem' }} />
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>No documents have been added yet.</p>
                </div>
              ) : (
                <div className="document-rows-container" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
                  {libraryStatus.documents.map((doc) => (
                    <div key={doc.document_hash} className="doc-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', background: 'rgba(255,255,255,0.4)', border: '1px solid #eee', borderRadius: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                        <FileText size={16} style={{ flexShrink: 0, color: 'var(--text-secondary)' }} />
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '14px' }} title={doc.source}>
                          {doc.source}
                        </span>
                      </div>
                      <button 
                        type="button" 
                        onClick={() => handleDeleteDocument(doc.document_hash)}
                        style={{ background: 'none', border: 'none', color: 'var(--risk-high, #dc3545)', cursor: 'pointer', padding: '4px' }}
                        title="Delete document database chunks"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        {/* RIGHT COLUMN: SECURITY & PASSWORD PANEL */}
        <section className="glass-panel" style={{ padding: '2rem' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1.5rem', fontSize: '18px' }}>
            <Shield size={20} style={{ color: 'var(--accent-color, #007bff)' }} />
            Security & Authentication
          </h2>

          <form onSubmit={handlePasswordChange}>
            {passError && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--risk-high, #dc3545)', background: 'rgba(220,53,69,0.05)', padding: '0.75rem', borderRadius: '4px', marginBottom: '1rem', fontSize: '14px' }}>
                <AlertCircle size={16} /> <span>{passError}</span>
              </div>
            )}
            {passSuccess && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'green', background: 'rgba(0,128,0,0.05)', padding: '0.75rem', borderRadius: '4px', marginBottom: '1rem', fontSize: '14px' }}>
                <CheckCircle2 size={16} /> <span>{passSuccess}</span>
              </div>
            )}

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '14px' }}>Current Password</label>
              <input 
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', boxSizing: 'border-box' }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '14px' }}>New Password</label>
              <input 
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '10px', border: '1px solid #ccc', borderRadius: '4px', boxSizing: 'border-box' }}
              />
            </div>

            <button 
              type="submit" 
              disabled={passLoading}
              className="btn-primary"
              style={{ width: '100%', padding: '12px', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              {passLoading ? <Loader2 className="spin-icon" size={16} /> : <Key size={16} />}
              Update Account Password
            </button>
          </form>
        </section>

      </div>
    </div>
  );
}