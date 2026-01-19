"""
AstraGuard Health Dashboard

Live observability dashboard using Streamlit.
Displays real-time health metrics, circuit breaker status,
fallback cascade status, and component health.

Backend endpoint: http://localhost:8000/health/state
Auto-refresh every 2 seconds for live updates.
"""

import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import sys
import os

# Import centralized secrets management
from core.secrets import get_secret

# Configure page
st.set_page_config(
    page_title="🛡️ AstraGuard Health Monitor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CONFIG & CONSTANTS
# ============================================================================

BACKEND_URL = get_secret("backend_url")
HEALTH_ENDPOINT = f"{BACKEND_URL}/health/state"
REFRESH_INTERVAL = 2  # seconds
MAX_HISTORY = 100

# Status colors
STATUS_COLORS = {
    "healthy": "#00CC96",      # Green
    "degraded": "#FFA15A",     # Orange
    "failed": "#EF553B",       # Red
    "unknown": "#636EFA",      # Blue
}

MODE_COLORS = {
    "primary": "#00CC96",      # Green
    "heuristic": "#FFA15A",    # Orange
    "safe": "#EF553B",         # Red
}

CIRCUIT_STATE_COLORS = {
    "CLOSED": "#00CC96",       # Green
    "HALF_OPEN": "#FFA15A",    # Orange
    "OPEN": "#EF553B",         # Red
    "UNKNOWN": "#636EFA",      # Blue
}

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

if "health_history" not in st.session_state:
    st.session_state.health_history = []

if "last_fetch_time" not in st.session_state:
    st.session_state.last_fetch_time = None

if "error_message" not in st.session_state:
    st.session_state.error_message = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def fetch_health_state() -> dict:
    """Fetch health state from backend."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Backend unavailable", "error_type": "connection"}
    except requests.exceptions.Timeout:
        return {"error": "Backend timeout", "error_type": "timeout"}
    except Exception as e:
        return {"error": str(e), "error_type": "unknown"}


def get_status_icon(status: str) -> str:
    """Get emoji icon for status."""
    icons = {
        "healthy": "✅",
        "degraded": "⚠️",
        "failed": "❌",
        "unknown": "❓",
    }
    return icons.get(status, "❓")


def get_circuit_icon(state: str) -> str:
    """Get emoji icon for circuit state."""
    icons = {
        "CLOSED": "🟢",
        "HALF_OPEN": "🟡",
        "OPEN": "🔴",
        "UNKNOWN": "⚪",
    }
    return icons.get(state, "⚪")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def get_health_card_color(status: str) -> str:
    """Get color for health card background."""
    return STATUS_COLORS.get(status, "#F0F0F0")


# ============================================================================
# HEADER & TITLE
# ============================================================================

st.title("🛡️ AstraGuard Health Monitor")
st.markdown("**Live Reliability Metrics & Observability Dashboard**")

# Auto-refresh notice
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("*Auto-refreshing every 2 seconds for live updates*")
with col2:
    if st.button("🔄 Refresh Now"):
        st.rerun()

st.divider()

# ============================================================================
# FETCH HEALTH STATE
# ============================================================================

health_state = fetch_health_state()

# Handle errors
if "error" in health_state:
    st.error(f"❌ **Backend Connection Error**\n\n{health_state['error']}")
    st.info(f"Backend URL: {BACKEND_URL}")
    st.stop()

# Update history
if "timestamp" in health_state:
    st.session_state.health_history.append(health_state)
    st.session_state.health_history = st.session_state.health_history[-MAX_HISTORY:]

# ============================================================================
# MAIN METRICS GRID (4 COLUMNS)
# ============================================================================

st.subheader("📊 Key Metrics")

system = health_state.get("system", {})
cb = health_state.get("circuit_breaker", {})
retry = health_state.get("retry", {})
fallback = health_state.get("fallback", {})

col1, col2, col3, col4 = st.columns(4)

with col1:
    system_status = system.get("status", "unknown")
    icon = get_status_icon(system_status)
    st.metric(
        label="System Health",
        value=f"{icon} {system_status.upper()}",
        delta=f"{system.get('healthy_components', 0)}/{system.get('total_components', 0)} OK",
    )

with col2:
    cb_state = cb.get("state", "UNKNOWN")
    icon = get_circuit_icon(cb_state)
    st.metric(
        label="Circuit Breaker",
        value=f"{icon} {cb_state}",
        delta=f"Open: {format_duration(cb.get('open_duration_seconds', 0))}",
    )

with col3:
    mode = fallback.get("mode", "primary").upper()
    mode_color = MODE_COLORS.get(fallback.get("mode"), "#636EFA")
    st.metric(
        label="Fallback Mode",
        value=f"⚙️ {mode}",
        delta="Cascading" if fallback.get("mode") != "primary" else "Nominal",
    )

with col4:
    failures_1h = retry.get("failures_1h", 0)
    icon = "✅" if failures_1h < 10 else "⚠️" if failures_1h < 50 else "❌"
    st.metric(
        label="Retry Failures (1h)",
        value=f"{icon} {failures_1h}",
        delta="High" if failures_1h > 50 else "Normal",
    )

st.divider()

# ============================================================================
# COMPONENT HEALTH GRID
# ============================================================================

st.subheader("🔧 Component Status")

components = health_state.get("components", {})

if components:
    # Create component status dataframe
    comp_data = []
    for name, comp_health in components.items():
        comp_data.append({
            "Component": name,
            "Status": comp_health.get("status", "unknown"),
            "Errors": comp_health.get("error_count", 0),
            "Fallback": "🔄 YES" if comp_health.get("fallback_active") else "❌ NO",
            "Last Updated": comp_health.get("last_updated", "N/A")[:19],
        })
    
    df_components = pd.DataFrame(comp_data)
    
    # Color the Status column
    def color_status(val):
        color = STATUS_COLORS.get(val, "#F0F0F0")
        return f"background-color: {color}; color: white; font-weight: bold;"
    
    styled_df = df_components.style.applymap(
        color_status,
        subset=["Status"]
    )
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("No components registered yet")

st.divider()

# ============================================================================
# CIRCUIT BREAKER DETAILS
# ============================================================================

st.subheader("🔌 Circuit Breaker Status")

cb_col1, cb_col2, cb_col3 = st.columns(3)

with cb_col1:
    st.metric(
        label="Total Failures",
        value=f"{cb.get('failures_total', 0):,}",
    )

with cb_col2:
    st.metric(
        label="Total Successes",
        value=f"{cb.get('successes_total', 0):,}",
    )

with cb_col3:
    st.metric(
        label="Total Trips",
        value=f"{cb.get('trips_total', 0):,}",
    )

# Circuit breaker state gauge
fig_cb_state = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value={"CLOSED": 100, "HALF_OPEN": 50, "OPEN": 0}.get(cb.get("state"), 25),
    title="Circuit State",
    delta={"reference": 100},
    gauge={
        "axis": {"range": [0, 100]},
        "bar": {"color": CIRCUIT_STATE_COLORS.get(cb.get("state"), "#636EFA")},
        "steps": [
            {"range": [0, 33], "color": "#EF553B"},
            {"range": [33, 66], "color": "#FFA15A"},
            {"range": [66, 100], "color": "#00CC96"},
        ],
        "threshold": {
            "line": {"color": "red", "width": 4},
            "thickness": 0.75,
            "value": 90,
        },
    },
))
fig_cb_state.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig_cb_state, use_container_width=True)

st.divider()

# ============================================================================
# RETRY FAILURE TRACKING
# ============================================================================

st.subheader("🔁 Retry Failure Rate (1h)")

retry_col1, retry_col2 = st.columns(2)

with retry_col1:
    st.metric(
        label="Failures in Last Hour",
        value=retry.get("failures_1h", 0),
        delta=f"Rate: {retry.get('failure_rate', 0):.4f}/sec",
    )

with retry_col2:
    st.metric(
        label="Total Attempts",
        value=f"{retry.get('total_attempts', 0):,}",
    )

# Retry failure history (if available)
if len(st.session_state.health_history) > 1:
    retry_history = []
    for h in st.session_state.health_history:
        retry_history.append({
            "timestamp": datetime.fromisoformat(h.get("timestamp", datetime.now().isoformat())),
            "failures_1h": h.get("retry", {}).get("failures_1h", 0),
        })
    
    if retry_history:
        df_retry = pd.DataFrame(retry_history)
        df_retry["timestamp"] = pd.to_datetime(df_retry["timestamp"])
        
        fig_retry = px.line(
            df_retry,
            x="timestamp",
            y="failures_1h",
            title="Retry Failures Over Time",
            labels={"failures_1h": "Failures (1h window)", "timestamp": "Time"},
        )
        fig_retry.update_layout(height=300, hovermode="x unified")
        st.plotly_chart(fig_retry, use_container_width=True)

st.divider()

# ============================================================================
# FALLBACK CASCADE LOG
# ============================================================================

st.subheader("📋 Fallback Cascade Log")

cascade_log = fallback.get("cascade_log", [])

if cascade_log:
    # Display recent transitions
    for entry in reversed(cascade_log[-10:]):
        cols = st.columns([1, 2, 2, 1])
        with cols[0]:
            st.write(entry.get("timestamp", "N/A")[:19])
        with cols[1]:
            st.write(f"From: **{entry.get('from', 'N/A').upper()}**")
        with cols[2]:
            st.write(f"To: **{entry.get('to', 'N/A').upper()}**")
        with cols[3]:
            st.write(entry.get("reason", "N/A"))
        st.divider()
else:
    st.info("No cascade transitions recorded")

st.divider()

# ============================================================================
# SYSTEM INFO
# ============================================================================

st.subheader("ℹ️ System Information")

info_col1, info_col2 = st.columns(2)

with info_col1:
    uptime_sec = health_state.get("uptime_seconds", 0)
    st.metric(
        label="System Uptime",
        value=format_duration(uptime_sec),
    )

with info_col2:
    st.metric(
        label="Last Health Check",
        value=health_state.get("timestamp", "N/A")[:19],
    )

# Display raw JSON (collapsible)
with st.expander("📄 Raw Health State (JSON)"):
    st.json(health_state)

st.divider()

# ============================================================================
# AUTO-REFRESH
# ============================================================================

# Set auto-refresh using streamlit timer
time.sleep(REFRESH_INTERVAL)
st.rerun()
