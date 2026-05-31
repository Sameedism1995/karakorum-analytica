"""Custom CSS for the KarakorumAnalytica dashboard."""

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

.main-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 55%, #0d9488 100%);
    border-radius: 16px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    color: #f8fafc;
    box-shadow: 0 4px 24px rgba(15, 23, 42, 0.12);
}

.main-header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.35rem 0;
    letter-spacing: -0.02em;
}

.main-header p {
    margin: 0;
    opacity: 0.88;
    font-size: 0.95rem;
}

.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    height: 100%;
    transition: box-shadow 0.2s ease;
}

.kpi-card:hover {
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
}

.kpi-label {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748b;
    margin-bottom: 0.35rem;
}

.kpi-value {
    font-size: 1.65rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.2;
}

.kpi-sub {
    font-size: 0.8rem;
    color: #94a3b8;
    margin-top: 0.25rem;
}

.status-pill {
    display: inline-block;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.status-connected {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #bbf7d0;
}

.status-disconnected {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
}

.badge {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.badge-grey {
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.badge-orange {
    background: #ffedd5;
    color: #c2410c;
    border: 1px solid #fed7aa;
}

.badge-green {
    background: #dcfce7;
    color: #15803d;
    border: 1px solid #bbf7d0;
}

.badge-blue {
    background: #dbeafe;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
}

.badge-red {
    background: #fee2e2;
    color: #b91c1c;
    border: 1px solid #fecaca;
}

.badge-purple {
    background: #ede9fe;
    color: #6d28d9;
    border: 1px solid #ddd6fe;
}

.item-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.25rem 1.35rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.item-card-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #0f172a;
    margin-bottom: 0.65rem;
    line-height: 1.4;
}

.item-meta {
    font-size: 0.84rem;
    color: #64748b;
    margin-bottom: 0.35rem;
}

.item-meta strong {
    color: #334155;
    font-weight: 600;
}

.confidence-bar-wrap {
    background: #f1f5f9;
    border-radius: 999px;
    height: 10px;
    overflow: hidden;
    margin: 0.5rem 0 0.35rem 0;
}

.confidence-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #0d9488, #14b8a6);
}

.draft-text {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.92rem;
    line-height: 1.55;
    color: #1e293b;
    white-space: pre-wrap;
    margin: 0.65rem 0;
}

.section-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #0f172a;
    margin: 1.25rem 0 0.75rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid #e2e8f0;
}

.info-box {
    background: #f0fdfa;
    border: 1px solid #99f6e4;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    color: #115e59;
    font-size: 0.88rem;
    margin: 0.75rem 0;
}

.warn-box {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    color: #92400e;
    font-size: 0.88rem;
    margin: 0.75rem 0;
}

.error-box {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    color: #991b1b;
    font-size: 0.88rem;
    margin: 0.75rem 0;
}

.sidebar-status-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.85rem;
    margin-top: 0.75rem;
}

.chart-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 0.5rem 0.25rem 0.25rem 0.25rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

div[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}

div[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 0.35rem;
    background: transparent;
    border-bottom: 2px solid #e2e8f0;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1.1rem;
    font-weight: 600;
    color: #64748b;
}

.stTabs [aria-selected="true"] {
    background: #ffffff;
    color: #0f172a !important;
    border: 1px solid #e2e8f0;
    border-bottom: 2px solid #ffffff;
}

.source-tag {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.35rem;
}

.source-gdelt { background: #dbeafe; color: #1e40af; }
.source-reliefweb { background: #fce7f3; color: #9d174d; }
.source-acled { background: #fef3c7; color: #92400e; }
</style>
"""
