import React, { useState } from 'react';
import { useOrganization } from '../context/OrganizationContext';
import {
  FolderOpen,
  ShieldCheck,
  HardDrive,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
} from 'lucide-react';

interface LinkLocalStorageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface ScanResult {
  status: string;
  linked_path: string;
  privacy_guarantee: string;
  total_files_scanned: number;
  total_bytes_scanned: number;
  total_mb_scanned: number;
  recommendations_generated: number;
  sample_objects: Array<{
    object_key: string;
    size_bytes: number;
    category: string;
    modified_at: string;
    accessed_at: string;
  }>;
}

export const LinkLocalStorageModal: React.FC<LinkLocalStorageModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { selectedOrg, refreshOrganizations } = useOrganization();

  const [localPath, setLocalPath] = useState('');
  const [maxFiles, setMaxFiles] = useState(1000);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);

  if (!isOpen || !selectedOrg) return null;


  const handleLinkStorage = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setScanResult(null);

    if (!localPath.trim()) {
      setError('Please enter a valid local directory path.');
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch(
        `/api/v1/organizations/${selectedOrg.id}/storage/link-local`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            local_path: localPath.trim(),
            max_files: maxFiles,
            run_ml_recommendations: true,
          }),
        }
      );

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to scan and link local folder.');
      }

      setScanResult(data);
      if (refreshOrganizations) {
        await refreshOrganizations();
      }
      if (onSuccess) {
        onSuccess();
      }
    } catch (err: any) {
      setError(err.message || 'Error occurred while linking storage.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDone = () => {
    setScanResult(null);
    setLocalPath('');
    onClose();
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="link-storage-title">
      <div className="modal-container link-local-modal">
        {/* HEADER */}
        <div className="modal-header">
          <div className="modal-title-wrap">
            <div className="modal-badge">
              <FolderOpen size={16} />
              <span>LOCAL FILESYSTEM INTEGRATION</span>
            </div>
            <h3 id="link-storage-title" className="neon-heading-sm">
              Link Local Storage Directory
            </h3>
            <p className="modal-subtitle">
              Index and analyze storage lifecycles on local folders for{' '}
              <strong style={{ color: 'var(--neon-blue-bright)' }}>
                {selectedOrg.name}
              </strong>
              .
            </p>
          </div>

          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* PRIVACY & ZERO CONTENT ACCESS GUARANTEE BANNER */}
        <div className="privacy-guarantee-banner">
          <div className="privacy-icon-wrap">
            <ShieldCheck size={24} className="privacy-shield-icon" />
          </div>
          <div className="privacy-content">
            <strong className="privacy-title">
              Zero-Content-Read Security & Privacy Guarantee
            </strong>
            <p className="privacy-desc">
              The scanner inspects <strong>strictly file names and filesystem metadata</strong> (file size, created date, modified date, and access timestamps).
              Actual file contents are <strong>NEVER opened, read, streamed, or stored</strong> in any form.
            </p>
          </div>
        </div>

        {error && (
          <div className="login-error-box" style={{ margin: '12px 0' }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* SCAN RESULT DISPLAY */}
        {scanResult ? (
          <div className="scan-results-view animate-fade-in">
            <div className="scan-success-banner">
              <CheckCircle2 size={22} className="text-success" />
              <div>
                <strong style={{ color: '#fff', fontSize: '0.95rem' }}>
                  Successfully Linked & Indexed
                </strong>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  {scanResult.linked_path}
                </p>
              </div>
            </div>

            {/* STATS TILES */}
            <div className="scan-stats-grid">
              <div className="scan-stat-card">
                <span className="stat-label">Indexed Files</span>
                <span className="stat-value">{scanResult.total_files_scanned}</span>
              </div>
              <div className="scan-stat-card">
                <span className="stat-label">Indexed Volume</span>
                <span className="stat-value">{formatBytes(scanResult.total_bytes_scanned)}</span>
              </div>
              <div className="scan-stat-card">
                <span className="stat-label">ML Recommendations</span>
                <span className="stat-value" style={{ color: 'var(--neon-green)' }}>
                  {scanResult.recommendations_generated}
                </span>
              </div>
            </div>

            {/* METADATA PREVIEW */}
            {scanResult.sample_objects && scanResult.sample_objects.length > 0 && (
              <div className="metadata-preview-wrap">
                <span className="input-category-label">
                  Metadata Captured (Sample First 10 Files - Zero File Data Read):
                </span>
                <div className="metadata-table-scroll">
                  <table className="metadata-mini-table">
                    <thead>
                      <tr>
                        <th>Relative Path / Key</th>
                        <th>Category</th>
                        <th>Size</th>
                        <th>Last Modified</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scanResult.sample_objects.map((obj, i) => (
                        <tr key={i}>
                          <td className="font-mono text-neon-blue">{obj.object_key}</td>
                          <td>
                            <span className="badge badge-muted">{obj.category}</span>
                          </td>
                          <td>{formatBytes(obj.size_bytes)}</td>
                          <td className="text-muted">
                            {new Date(obj.modified_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="modal-footer" style={{ marginTop: '20px' }}>
              <button
                type="button"
                className="btn btn-primary btn-block btn-glow"
                onClick={handleDone}
              >
                <span>View in Objects & Recommendations Explorer</span>
              </button>
            </div>
          </div>
        ) : (
          /* FORM VIEW */
          <form onSubmit={handleLinkStorage} className="link-storage-form">
            <div className="form-group">
              <label className="form-label" htmlFor="local-path-input">
                Local Folder Path
              </label>
              <div className="input-icon-wrapper">
                <HardDrive size={18} className="field-icon" />
                <input
                  id="local-path-input"
                  type="text"
                  className="form-input with-left-icon font-mono"
                  placeholder="e.g. D:\MyProjects\Data or C:\Users\Documents\Archive"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  disabled={submitting}
                  required
                />
              </div>
              <span className="input-hint">
                Provide an absolute or relative directory path on the local host filesystem.
              </span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="max-files-input">
                Max Files to Index
              </label>
              <input
                id="max-files-input"
                type="number"
                min="10"
                max="10000"
                className="form-input"
                value={maxFiles}
                onChange={(e) => setMaxFiles(parseInt(e.target.value, 10) || 500)}
                disabled={submitting}
              />
              <span className="input-hint">
                Limits recursive traversal depth to ensure fast indexing and ML inference.
              </span>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary btn-glow"
                disabled={submitting || !localPath.trim()}
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Scanning Metadata & Evaluating ML...</span>
                  </>
                ) : (
                  <>
                    <FolderOpen size={16} />
                    <span>Scan & Link Metadata</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
