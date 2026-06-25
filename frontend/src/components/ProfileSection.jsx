import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';
import {
  Key,
  Trash2,
  Shield,
  Folder,
  FileText,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
  RefreshCw,
} from 'lucide-react';

export default function ProfileSection() {
  const { user } = useAuth();
  const [libraryStatus, setLibraryStatus] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [libraryError, setLibraryError] = useState('');

  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passError, setPassError] = useState('');
  const [passSuccess, setPassSuccess] = useState('');
  const [passLoading, setPassLoading] = useState(false);

  const fetchLibraryStatus = async () => {
    try {
      setLoadingStatus(true);
      setLibraryError('');
      const response = await api.get('/api/clause-library/status');
      setLibraryStatus(response.data);
    } catch (err) {
      console.error('Failed to fetch tenant library status:', err);
      setLibraryError('We could not load your document library. Please try again.');
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchLibraryStatus();
  }, []);

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPassError('');
    setPassSuccess('');
    setPassLoading(true);

    try {
      const response = await api.post('/api/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
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

  const handleDeleteDocument = async (documentHash) => {
    if (
      !window.confirm(
        'Remove this document from your private library? Indexed clauses will be deleted permanently.'
      )
    ) {
      return;
    }

    try {
      await api.delete(`/api/clause-library/documents/${documentHash}`);
      fetchLibraryStatus();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to remove the document.');
    }
  };

  const usernameInitial = user?.username?.charAt(0)?.toUpperCase() || '?';

  return (
    <div className="profile-layout animate-slide-up">
      <header className="profile-header">
        <div>
          <span className="section-label">Account settings</span>
          <h2 className="profile-title">Profile &amp; storage</h2>
          <p className="profile-lead">
            Manage your account security and the documents saved in your private clause library.
          </p>
        </div>
      </header>

      <div className="profile-account-card">
        <div className="profile-avatar" aria-hidden="true">
          {usernameInitial}
        </div>
        <div className="profile-account-details">
          <span className="profile-account-label">Signed in as</span>
          <strong>{user?.username}</strong>
        </div>
        <div className="profile-account-meta">
          <span className="profile-status-pill">
            <CheckCircle2 size={14} />
            Active account
          </span>
        </div>
      </div>

      <div className="profile-grid">
        <section className="profile-panel profile-panel--library">
          <h3 className="profile-panel-title">
            <Folder size={20} />
            Private clause library
          </h3>
          <p className="profile-panel-desc">
            Documents you chose to retain during contract review are indexed here for semantic search.
          </p>

          {loadingStatus ? (
            <div className="profile-loading">
              <Loader2 className="spin-icon" size={32} />
              <span>Loading library…</span>
            </div>
          ) : libraryError ? (
            <div className="profile-empty-state">
              <AlertCircle size={28} />
              <p>{libraryError}</p>
              <button type="button" className="secondary-button" onClick={fetchLibraryStatus}>
                <RefreshCw size={16} />
                Retry
              </button>
            </div>
          ) : (
            <div className="profile-panel-body">
              <div className="metrics-summary">
                <div className="metric-box">
                  <strong>{libraryStatus?.document_count || 0}</strong>
                  <span>Documents</span>
                </div>
                <div className="metric-box">
                  <strong>{libraryStatus?.clause_count || 0}</strong>
                  <span>Clauses</span>
                </div>
              </div>

              <h4 className="profile-subheading">Saved documents</h4>

              {!libraryStatus?.documents?.length ? (
                <div className="profile-empty-state">
                  <FileText size={32} />
                  <p>No documents in your library yet.</p>
                  <span>Enable &quot;Retain in library&quot; when reviewing a contract to add one.</span>
                </div>
              ) : (
                <div className="document-rows-container">
                  {libraryStatus.documents.map((doc) => (
                    <div key={doc.document_hash} className="doc-row">
                      <div className="doc-row-content">
                        <FileText size={16} className="doc-row-icon" />
                        <span className="doc-row-name" title={doc.source}>
                          {doc.source}
                        </span>
                      </div>
                      <button
                        type="button"
                        className="doc-delete-btn"
                        onClick={() => handleDeleteDocument(doc.document_hash)}
                        title="Remove from library"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        <section className="profile-panel profile-panel--security">
          <h3 className="profile-panel-title">
            <Shield size={20} />
            Security
          </h3>
          <p className="profile-panel-desc">
            Update your password to keep your account and private document library secure.
          </p>

          <form className="profile-security-form" onSubmit={handlePasswordChange}>
            {passError && (
              <div className="auth-alert error">
                <AlertCircle size={18} />
                <span>{passError}</span>
              </div>
            )}
            {passSuccess && (
              <div className="auth-alert success">
                <CheckCircle2 size={18} />
                <span>{passSuccess}</span>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="current-password">Current password</label>
              <div className="input-wrapper">
                <Lock size={18} className="input-icon" />
                <input
                  id="current-password"
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  required
                  placeholder="Enter current password"
                  autoComplete="current-password"
                />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="new-password">New password</label>
              <div className="input-wrapper">
                <Key size={18} className="input-icon" />
                <input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  placeholder="Enter new password"
                  autoComplete="new-password"
                />
              </div>
            </div>

            <button type="submit" className="primary-button" disabled={passLoading}>
              {passLoading ? (
                <Loader2 size={18} className="spin-icon" />
              ) : (
                <Key size={18} />
              )}
              Update password
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
