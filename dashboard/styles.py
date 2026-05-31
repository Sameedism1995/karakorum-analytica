"""Custom CSS for the KarakorumAnalytica dashboard."""

from dashboard.theme import (
    ARCTIC_WHITE,
    CRIMSON_BORDER,
    CRIMSON_SOFT,
    MIDNIGHT_NAVY,
    NAVY_SOFT,
    SIGNAL_CRIMSON,
    SLATE_BLUE,
    SLATE_SOFT,
    STEEL_MIST,
)

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {{
    --ka-midnight: {MIDNIGHT_NAVY};
    --ka-slate: {SLATE_BLUE};
    --ka-mist: {STEEL_MIST};
    --ka-white: {ARCTIC_WHITE};
    --ka-crimson: {SIGNAL_CRIMSON};
}}

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {MIDNIGHT_NAVY};
}}

.stApp {{
    background-color: {ARCTIC_WHITE};
}}

.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}}

.main-header {{
    background: linear-gradient(135deg, {MIDNIGHT_NAVY} 0%, {SLATE_BLUE} 100%);
    border-radius: 14px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    color: {ARCTIC_WHITE};
    box-shadow: 0 8px 32px rgba(11, 22, 35, 0.18);
    border-left: 4px solid {SIGNAL_CRIMSON};
}}

.main-header h1 {{
    font-size: 1.65rem;
    font-weight: 700;
    margin: 0 0 0.35rem 0;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}}

.main-header p {{
    margin: 0;
    color: {STEEL_MIST};
    font-size: 0.92rem;
}}

.kpi-card {{
    background: #ffffff;
    border: 1px solid {SLATE_SOFT};
    border-radius: 12px;
    padding: 1.1rem 1.25rem;
    box-shadow: 0 1px 3px rgba(11, 22, 35, 0.05);
    height: 100%;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
}}

.kpi-card:hover {{
    box-shadow: 0 6px 16px rgba(11, 22, 35, 0.08);
    border-color: {STEEL_MIST};
}}

.kpi-label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {STEEL_MIST};
    margin-bottom: 0.35rem;
}}

.kpi-value {{
    font-size: 1.65rem;
    font-weight: 700;
    color: {MIDNIGHT_NAVY};
    line-height: 1.2;
}}

.kpi-sub {{
    font-size: 0.8rem;
    color: {SLATE_BLUE};
    margin-top: 0.25rem;
}}

.status-pill {{
    display: inline-block;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}}

.status-connected {{
    background: {SLATE_SOFT};
    color: {SLATE_BLUE};
    border: 1px solid {STEEL_MIST};
}}

.status-disconnected {{
    background: {CRIMSON_SOFT};
    color: {SIGNAL_CRIMSON};
    border: 1px solid {CRIMSON_BORDER};
}}

.badge {{
    display: inline-block;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}

.badge-grey {{
    background: {SLATE_SOFT};
    color: {SLATE_BLUE};
    border: 1px solid {STEEL_MIST};
}}

.badge-orange {{
    background: {CRIMSON_SOFT};
    color: {SIGNAL_CRIMSON};
    border: 1px solid {CRIMSON_BORDER};
}}

.badge-green {{
    background: {NAVY_SOFT};
    color: {ARCTIC_WHITE};
    border: 1px solid {SLATE_BLUE};
}}

.badge-blue {{
    background: {SLATE_SOFT};
    color: {MIDNIGHT_NAVY};
    border: 1px solid {STEEL_MIST};
}}

.badge-red {{
    background: {CRIMSON_SOFT};
    color: {SIGNAL_CRIMSON};
    border: 1px solid {CRIMSON_BORDER};
}}

.badge-purple {{
    background: {MIDNIGHT_NAVY};
    color: {ARCTIC_WHITE};
    border: 1px solid {MIDNIGHT_NAVY};
}}

.item-card {{
    background: #ffffff;
    border: 1px solid {SLATE_SOFT};
    border-radius: 12px;
    padding: 1.25rem 1.35rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 1px 2px rgba(11, 22, 35, 0.04);
}}

.item-card-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: {MIDNIGHT_NAVY};
    margin-bottom: 0.65rem;
    line-height: 1.4;
}}

.item-meta {{
    font-size: 0.84rem;
    color: {STEEL_MIST};
    margin-bottom: 0.35rem;
}}

.item-meta strong {{
    color: {SLATE_BLUE};
    font-weight: 600;
}}

.item-meta a {{
    color: {SIGNAL_CRIMSON};
    text-decoration: none;
    font-weight: 500;
}}

.item-meta a:hover {{
    text-decoration: underline;
}}

.confidence-bar-wrap {{
    background: {SLATE_SOFT};
    border-radius: 999px;
    height: 10px;
    overflow: hidden;
    margin: 0.5rem 0 0.35rem 0;
}}

.confidence-bar-fill {{
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, {SLATE_BLUE}, {SIGNAL_CRIMSON});
}}

.draft-text {{
    background: {ARCTIC_WHITE};
    border: 1px solid {SLATE_SOFT};
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.92rem;
    line-height: 1.55;
    color: {MIDNIGHT_NAVY};
    white-space: pre-wrap;
    margin: 0.65rem 0;
}}

.section-title {{
    font-size: 1.05rem;
    font-weight: 600;
    color: {MIDNIGHT_NAVY};
    margin: 1.25rem 0 0.75rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 2px solid {SLATE_SOFT};
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}

.info-box {{
    background: {SLATE_SOFT};
    border: 1px solid {STEEL_MIST};
    border-left: 3px solid {SLATE_BLUE};
    border-radius: 10px;
    padding: 0.85rem 1rem;
    color: {SLATE_BLUE};
    font-size: 0.88rem;
    margin: 0.75rem 0;
}}

.warn-box {{
    background: {CRIMSON_SOFT};
    border: 1px solid {CRIMSON_BORDER};
    border-left: 3px solid {SIGNAL_CRIMSON};
    border-radius: 10px;
    padding: 0.85rem 1rem;
    color: {MIDNIGHT_NAVY};
    font-size: 0.88rem;
    margin: 0.75rem 0;
}}

.error-box {{
    background: {CRIMSON_SOFT};
    border: 1px solid {CRIMSON_BORDER};
    border-left: 3px solid {SIGNAL_CRIMSON};
    border-radius: 10px;
    padding: 0.85rem 1rem;
    color: {SIGNAL_CRIMSON};
    font-size: 0.88rem;
    margin: 0.75rem 0;
}}

.sidebar-status-box {{
    background: rgba(245, 247, 250, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.35);
    border-radius: 10px;
    padding: 0.85rem;
    margin-top: 0.75rem;
}}

.chart-card {{
    background: #ffffff;
    border: 1px solid {SLATE_SOFT};
    border-radius: 12px;
    padding: 0.5rem 0.25rem 0.25rem 0.25rem;
}}

div[data-testid="stSidebar"] {{
    background: {MIDNIGHT_NAVY};
    border-right: 1px solid {SLATE_BLUE};
}}

div[data-testid="stSidebar"] h1,
div[data-testid="stSidebar"] h2,
div[data-testid="stSidebar"] h3,
div[data-testid="stSidebar"] label,
div[data-testid="stSidebar"] p,
div[data-testid="stSidebar"] span,
div[data-testid="stSidebar"] .stMarkdown {{
    color: {ARCTIC_WHITE};
}}

div[data-testid="stSidebar"] .stCaption {{
    color: {STEEL_MIST} !important;
}}

div[data-testid="stSidebar"] input,
div[data-testid="stSidebar"] .stSelectbox > div > div {{
    background-color: {NAVY_SOFT} !important;
    color: {ARCTIC_WHITE} !important;
    border-color: {SLATE_BLUE} !important;
}}

div[data-testid="stSidebar"] .block-container {{
    padding-top: 1.5rem;
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 0.35rem;
    background: transparent;
    border-bottom: 2px solid {SLATE_SOFT};
}}

.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    padding: 0.5rem 1.1rem;
    font-weight: 600;
    color: {STEEL_MIST};
}}

.stTabs [aria-selected="true"] {{
    background: #ffffff;
    color: {MIDNIGHT_NAVY} !important;
    border: 1px solid {SLATE_SOFT};
    border-bottom: 2px solid #ffffff;
}}

.stTabs [aria-selected="true"] p {{
    color: {MIDNIGHT_NAVY} !important;
}}

.source-tag {{
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.35rem;
}}

.source-gdelt {{
    background: {SLATE_SOFT};
    color: {SLATE_BLUE};
}}

.source-reliefweb {{
    background: {NAVY_SOFT};
    color: {ARCTIC_WHITE};
}}

.source-acled {{
    background: {CRIMSON_SOFT};
    color: {SIGNAL_CRIMSON};
}}

div[data-testid="stSidebar"] .info-box,
div[data-testid="stSidebar"] .warn-box,
div[data-testid="stSidebar"] .error-box {{
    color: {MIDNIGHT_NAVY} !important;
}}

div[data-testid="stSidebar"] .info-box *,
div[data-testid="stSidebar"] .warn-box *,
div[data-testid="stSidebar"] .error-box * {{
    color: {MIDNIGHT_NAVY} !important;
}}
</style>
"""
