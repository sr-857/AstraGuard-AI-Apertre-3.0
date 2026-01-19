import streamlit as st
import pandas as pd
import numpy as np
import time
import sys
import os
from datetime import datetime, timedelta
from collections import deque

# Add parent directory to path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from state_machine.state_engine import StateMachine, MissionPhase
from state_machine.mission_policy import PolicyManager
from state_machine.mission_phase_policy_engine import MissionPhasePolicyEngine

# Import centralized secrets management
from core.secrets import get_secret
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler

# Page configuration
st.set_page_config(
    page_title="AstraGuard Mission Control",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #b8b8d1;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.5);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .alert-critical {
        background: rgba(220, 38, 38, 0.2);
        border-left: 4px solid #dc2626;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .alert-warning {
        background: rgba(249, 115, 22, 0.2);
        border-left: 4px solid #f97316;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .alert-success {
        background: rgba(34, 197, 94, 0.2);
        border-left: 4px solid #22c55e;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize state machine and policy systems
state_machine = StateMachine()
policy_loader = MissionPhasePolicyLoader()
policy_engine = MissionPhasePolicyEngine(policy_loader.get_policy())
phase_aware_handler = PhaseAwareAnomalyHandler(state_machine, policy_loader)
policy_manager = PolicyManager()

# Initialize session state
if "telemetry_active" not in st.session_state:
    st.session_state.telemetry_active = False
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["voltage","temp","gyro","wheel","timestamp"])
if "logs" not in st.session_state:
    st.session_state.logs = []
if "decision_logs" not in st.session_state:
    st.session_state.decision_logs = []
if "mission_phase" not in st.session_state:
    st.session_state.mission_phase = MissionPhase.NOMINAL_OPS.value
if "simulation_mode" not in st.session_state:
    st.session_state.simulation_mode = get_secret("simulation_mode")
if "anomaly_history" not in st.session_state:
    st.session_state.anomaly_history = deque(maxlen=100)
if "anomaly_trend_data" not in st.session_state:
    st.session_state.anomaly_trend_data = pd.DataFrame(columns=["timestamp", "anomaly_count", "avg_severity"])
if "prediction_score" not in st.session_state:
    st.session_state.prediction_score = 0.0
if "total_anomalies" not in st.session_state:
    st.session_state.total_anomalies = 0
if "total_samples" not in st.session_state:
    st.session_state.total_samples = 0
if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = datetime.now()

# Sidebar controls
st.sidebar.title("🎛️ Flight Controls")

# Control buttons
col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    start_btn = st.button("▶️ Start", use_container_width=True)
with col_btn2:
    stop_btn = st.button("⏸️ Stop", use_container_width=True)

# Reset button
if st.sidebar.button("🔄 Reset Data", use_container_width=True):
    st.session_state.df = pd.DataFrame(columns=["voltage","temp","gyro","wheel","timestamp"])
    st.session_state.logs = []
    st.session_state.decision_logs = []
    st.session_state.anomaly_history = deque(maxlen=100)
    st.session_state.total_anomalies = 0
    st.session_state.total_samples = 0
    st.session_state.session_start_time = datetime.now()
    st.sidebar.success("✓ Data reset complete")

st.sidebar.markdown("---")

# Mission Phase Display and Control
st.sidebar.subheader("🚀 Mission Phase")

# Display current phase with description
current_phase = MissionPhase(st.session_state.mission_phase)
phase_description = state_machine.get_phase_description(current_phase)

st.sidebar.write(f"**Current:** {current_phase.value}")
st.sidebar.info(phase_description)

# Phase transition controls - only in simulation mode
if st.session_state.simulation_mode:
    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ **SIMULATION MODE** - Phase control enabled")
    
    phase_options = [p.value for p in MissionPhase]
    new_phase_value = st.sidebar.selectbox(
        "Simulate Phase Transition", 
        phase_options,
        index=phase_options.index(st.session_state.mission_phase)
    )
    
    if new_phase_value != st.session_state.mission_phase:
        try:
            new_phase = MissionPhase(new_phase_value)
            if state_machine.is_phase_transition_valid(new_phase):
                state_machine.set_phase(new_phase)
                st.session_state.mission_phase = new_phase.value
                st.sidebar.success(f"✓ Transitioned to {new_phase.value}")
            else:
                if st.sidebar.button(f"Force transition to {new_phase_value}?"):
                    state_machine.force_safe_mode() if new_phase == MissionPhase.SAFE_MODE else state_machine.set_phase(new_phase)
                    st.session_state.mission_phase = new_phase.value
                    st.sidebar.success(f"✓ Forced transition to {new_phase.value}")
        except Exception as e:
            st.sidebar.error(f"Transition error: {e}")
else:
    st.sidebar.caption("💡 Set `ASTRAGUARD_SIMULATION_MODE=true` to enable phase control")

# Phase constraints display
constraints = phase_aware_handler.get_phase_constraints(current_phase)
with st.sidebar.expander("🔒 Phase Constraints"):
    st.write("**Allowed Actions:**")
    st.write(", ".join(constraints['allowed_actions']) if constraints['allowed_actions'] else "None")
    st.write("\n**Forbidden Actions:**")
    st.write(", ".join(constraints['forbidden_actions']) if constraints['forbidden_actions'] else "None")
    st.write(f"\n**Threshold Multiplier:** {constraints['threshold_multiplier']}x")

# Trend Analysis Controls
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Trend Analysis")
show_trends = st.sidebar.checkbox("Enable Anomaly Trends", value=True)
if show_trends:
    trend_window = st.sidebar.slider("Analysis Window", 10, 100, 30)
    show_predictions = st.sidebar.checkbox("Show Predictions", value=True)
else:
    trend_window = 30
    show_predictions = False

# Export options
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Data Export")
if st.sidebar.button("📥 Export Telemetry CSV", use_container_width=True):
    if len(st.session_state.df) > 0:
        csv = st.session_state.df.to_csv(index=False)
        st.sidebar.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"astraguard_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

if start_btn:
    st.session_state.telemetry_active = True
if stop_btn:
    st.session_state.telemetry_active = False

# Detection and Analysis Functions
def detect_anomaly(row):
    """Detect anomalies with phase-aware thresholds."""
    multiplier = policy_manager.get_threshold_multiplier(st.session_state.mission_phase)
    return row["voltage"] > (4.2 * multiplier) or row["temp"] > (75 * multiplier)

def classify_anomaly_type(row):
    """Classify the type of fault based on telemetry."""
    if row.get("voltage", 8.0) < 7.0:
        return "power_fault"
    elif row.get("temp", 25.0) > 40.0:
        return "thermal_fault"
    elif abs(row.get("gyro", 0.0)) > 0.1:
        return "attitude_fault"
    else:
        return "unknown_fault"

def calculate_severity_score(row):
    """Calculate a normalized severity score from 0-1."""
    score = 0.0
    if row.get("voltage", 8.0) < 7.0:
        score += 0.4
    if row.get("temp", 25.0) > 40.0:
        score += 0.3
    if abs(row.get("gyro", 0.0)) > 0.1:
        score += 0.3
    return min(1.0, score / 0.7 * np.random.uniform(0.8, 1.0))

def analyze_anomaly_trends(anomaly_history, window_size=30):
    """Analyze recent anomaly patterns and generate trend metrics."""
    if len(anomaly_history) < 5:
        return {
            "trend": "insufficient_data",
            "frequency": 0,
            "severity_trend": "stable",
            "prediction_score": 0.0,
            "risk_level": "low",
            "anomaly_count": 0,
            "total_samples": len(anomaly_history)
        }
    
    recent = list(anomaly_history)[-window_size:]
    
    # Calculate anomaly frequency (per 10 samples)
    frequency = (sum(1 for a in recent if a['is_anomaly']) / len(recent)) * 10
    
    # Analyze severity trend
    anomaly_severities = [a['severity'] for a in recent if a['is_anomaly']]
    if len(anomaly_severities) >= 3:
        recent_avg = np.mean(anomaly_severities[-5:]) if len(anomaly_severities) >= 5 else np.mean(anomaly_severities)
        older_avg = np.mean(anomaly_severities[:-5]) if len(anomaly_severities) > 5 else recent_avg
        
        if recent_avg > older_avg * 1.2:
            severity_trend = "increasing"
        elif recent_avg < older_avg * 0.8:
            severity_trend = "decreasing"
        else:
            severity_trend = "stable"
    else:
        severity_trend = "stable"
    
    # Calculate prediction score
    recent_anomalies = [a for a in recent[-10:] if a['is_anomaly']]
    prediction_score = min(1.0, len(recent_anomalies) / 5 * (1 + frequency / 10))
    
    # Determine overall trend
    if frequency > 5 and severity_trend == "increasing":
        trend = "critical_increase"
        risk_level = "critical"
    elif frequency > 3:
        trend = "increasing"
        risk_level = "high"
    elif frequency > 1:
        trend = "moderate"
        risk_level = "medium"
    else:
        trend = "stable"
        risk_level = "low"
    
    return {
        "trend": trend,
        "frequency": frequency,
        "severity_trend": severity_trend,
        "prediction_score": prediction_score,
        "risk_level": risk_level,
        "anomaly_count": len(recent_anomalies),
        "total_samples": len(recent)
    }

def get_trend_color(trend):
    """Return color for trend visualization."""
    colors = {
        "critical_increase": "#dc2626",
        "increasing": "#f97316",
        "moderate": "#eab308",
        "stable": "#22c55e",
        "decreasing": "#3b82f6",
        "insufficient_data": "#6b7280"
    }
    return colors.get(trend, "#6b7280")

def memory_search(row):
    """Simulate memory search for similar past events."""
    if len(st.session_state.df) < 3:
        return []
    past = st.session_state.df.tail(3)
    results = []
    for _, r in past.iterrows():
        sim = 100 - abs(r["voltage"] - row["voltage"])*10
        results.append({
            "summary": f"Voltage {r['voltage']:.2f}V, Temp {r['temp']:.1f}C",
            "similarity": max(0, min(100, sim)),
            "timestamp": time.strftime("%H:%M:%S")
        })
    return results

# Main Header
st.markdown('<div class="main-header">🛰️ AstraGuard Mission Control</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Real-time telemetry monitoring with AI-powered anomaly detection and mission-phase awareness</div>', unsafe_allow_html=True)

# Top metrics row
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

with metric_col1:
    status_emoji = "🟢" if st.session_state.telemetry_active else "🔴"
    status_text = "ACTIVE" if st.session_state.telemetry_active else "OFFLINE"
    st.metric("Telemetry Status", f"{status_emoji} {status_text}")

with metric_col2:
    st.metric("Mission Phase", st.session_state.mission_phase, "🚀")

with metric_col3:
    uptime = datetime.now() - st.session_state.session_start_time
    st.metric("Session Uptime", f"{uptime.seconds // 60}m {uptime.seconds % 60}s")

with metric_col4:
    anomaly_rate = (st.session_state.total_anomalies / st.session_state.total_samples * 100) if st.session_state.total_samples > 0 else 0
    st.metric("Anomaly Rate", f"{anomaly_rate:.1f}%", f"{st.session_state.total_anomalies} detected")

st.markdown("---")

# Main content area
if st.session_state.telemetry_active:
    # Generate new telemetry data
    current_time = datetime.now()
    new_row = {
        "voltage": np.random.uniform(3.5, 5.0),
        "temp": np.random.uniform(20, 90),
        "gyro": np.random.uniform(-5, 5),
        "wheel": np.random.uniform(2000, 8000),
        "timestamp": current_time
    }
    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state.total_samples += 1

    # Detect anomaly
    anomaly = detect_anomaly(new_row)
    if anomaly:
        st.session_state.total_anomalies += 1
    
    mem = memory_search(new_row)

    # Log event
    timestamp = time.strftime('%H:%M:%S')
    log = f"[{timestamp}] {'⚠️ ANOMALY' if anomaly else '✓ OK'} | {new_row['voltage']:.2f}V | {new_row['temp']:.1f}°C | Phase: {st.session_state.mission_phase}"
    st.session_state.logs.append(log)

    # Track anomaly in history
    severity = calculate_severity_score(new_row) if anomaly else 0.0
    st.session_state.anomaly_history.append({
        "timestamp": current_time,
        "is_anomaly": anomaly,
        "severity": severity,
        "phase": st.session_state.mission_phase
    })

    # Process anomaly through phase-aware handler
    policy_decision = None
    if anomaly:
        anomaly_type = classify_anomaly_type(new_row)
        severity_score = calculate_severity_score(new_row)
        
        policy_decision = phase_aware_handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=severity_score,
            confidence=0.87,
            anomaly_metadata={"subsystem": "POWER_THERMAL"}
        )
        
        st.session_state.decision_logs.append(policy_decision)
        
        # Update mission phase if escalation occurred
        current_phase = state_machine.get_current_phase()
        st.session_state.mission_phase = current_phase.value

    # Calculate trend analysis
    trend_analysis = analyze_anomaly_trends(st.session_state.anomaly_history, trend_window)
    st.session_state.prediction_score = trend_analysis['prediction_score']

    # Two-column layout
    col_main, col_status = st.columns([2, 1])

    with col_main:
        st.subheader("📡 Live Telemetry Stream")
        
        # Show last 50 data points for better visualization
        display_df = st.session_state.df.tail(50)
        if len(display_df) > 0:
            chart_data = display_df[["voltage", "temp", "gyro", "wheel"]].copy()
            st.line_chart(chart_data)
        else:
            st.info("Collecting telemetry data...")

    with col_status:
        st.subheader("🎯 Anomaly Radar")
        
        if anomaly and policy_decision:
            if policy_decision['should_escalate_to_safe_mode']:
                st.markdown('<div class="alert-critical">🚨 <strong>CRITICAL ANOMALY</strong><br>Escalating to SAFE_MODE!</div>', unsafe_allow_html=True)
                st.metric("Severity Score", f"{policy_decision['severity_score']:.2f}", delta="ESCALATE", delta_color="inverse")
            else:
                st.markdown('<div class="alert-warning">⚠️ <strong>Anomaly Detected</strong></div>', unsafe_allow_html=True)
                st.metric("Severity Score", f"{policy_decision['severity_score']:.2f}")
            
            st.write(f"**Type:** {policy_decision['anomaly_type']}")
            st.write(f"**Confidence:** {policy_decision['detection_confidence']:.1%}")
            st.write(f"**Recurrence:** {policy_decision['recurrence_info']['count']}×")
            
            if policy_decision['recurrence_info']['count'] > 3:
                st.warning("⚠️ High recurrence detected")
        else:
            st.markdown('<div class="alert-success">✅ <strong>All Systems Nominal</strong></div>', unsafe_allow_html=True)
            st.metric("System Health", "100%", delta="+0%")

    # Trend Analysis Section
    if show_trends:
        st.markdown("---")
        st.subheader("📈 Anomaly Trend Analysis")
        
        trend_metrics_col1, trend_metrics_col2, trend_metrics_col3, trend_metrics_col4 = st.columns(4)
        
        with trend_metrics_col1:
            st.metric(
                "Frequency", 
                f"{trend_analysis['frequency']:.1f}/10",
                delta=f"{trend_analysis['anomaly_count']} in window"
            )
        
        with trend_metrics_col2:
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
            st.metric(
                "Risk Level",
                f"{risk_emoji.get(trend_analysis['risk_level'], '⚪')} {trend_analysis['risk_level'].upper()}",
                delta=trend_analysis['severity_trend']
            )
        
        with trend_metrics_col3:
            if show_predictions:
                st.metric(
                    "Next Anomaly Likelihood",
                    f"{trend_analysis['prediction_score']*100:.0f}%",
                    delta=f"{trend_analysis['trend'].replace('_', ' ')}"
                )
            else:
                st.metric("Prediction", "Disabled")
        
        with trend_metrics_col4:
            st.metric(
                "Analysis Window",
                f"{trend_analysis['total_samples']} samples",
                delta=f"{trend_window} max"
            )
        
        # Trend visualization
        trend_chart_data = pd.DataFrame([
            {
                "sample": i, 
                "anomaly": 1 if a['is_anomaly'] else 0, 
                "severity": a['severity'] * 100
            } 
            for i, a in enumerate(list(st.session_state.anomaly_history)[-trend_window:])
        ])
        
        if len(trend_chart_data) > 0:
            st.line_chart(trend_chart_data.set_index("sample")[["anomaly", "severity"]])
            
            # Trend insights
            trend_color = get_trend_color(trend_analysis['trend'])
            insight_text = f"System showing <strong>{trend_analysis['trend'].replace('_', ' ')}</strong> pattern. "
            insight_text += f"Severity trend is <strong>{trend_analysis['severity_trend']}</strong> over last {trend_window} samples."
            
            if trend_analysis['risk_level'] in ['high', 'critical']:
                insight_text += " <strong>⚠️ Immediate attention recommended.</strong>"
            
            st.markdown(f"""
            <div style="padding: 1rem; background: {trend_color}22; border-left: 4px solid {trend_color}; border-radius: 4px; margin-top: 1rem;">
                <strong>Trend Insight:</strong> {insight_text}
            </div>
            """, unsafe_allow_html=True)

    # Memory Matches and Reasoning
    col_memory, col_reasoning = st.columns(2)
    
    with col_memory:
        st.subheader("🧠 Memory Matches")
        if mem:
            for i, m in enumerate(mem, 1):
                similarity_color = "#22c55e" if m['similarity'] > 80 else "#eab308" if m['similarity'] > 50 else "#ef4444"
                st.markdown(f"""
                <div style="padding: 0.5rem; margin: 0.5rem 0; background: rgba(30, 41, 59, 0.3); border-radius: 4px; border-left: 3px solid {similarity_color};">
                    <strong>Match {i}:</strong> {m['summary']}<br>
                    <small>Similarity: {m['similarity']:.1f}% | Time: {m['timestamp']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("🔄 Memory system warming up... (need 3+ samples)")

    with col_reasoning:
        st.subheader("💭 Reasoning Console")
        if anomaly and policy_decision:
            reasoning_text = policy_decision['reasoning']
            st.info(f"🧠 {reasoning_text}")
            
            with st.expander("📋 Policy Decision Details"):
                pd_info = policy_decision['policy_decision']
                st.write(f"**Mission Phase:** {pd_info['mission_phase']}")
                st.write(f"**Anomaly Type:** {pd_info['anomaly_type']}")
                st.write(f"**Severity Level:** {pd_info['severity']}")
                st.write(f"**Response Allowed:** {'✅ Yes' if pd_info['is_allowed'] else '❌ No'}")
                st.write(f"**Escalation Level:** {pd_info['escalation_level']}")
                if pd_info['allowed_actions']:
                    st.write(f"**Allowed Actions:**")
                    for action in pd_info['allowed_actions']:
                        st.write(f"  • {action}")
        else:
            st.success("✅ No anomalies detected - system nominal")

    # Response & Recovery
    st.markdown("---")
    st.subheader("🛠️ Response & Recovery")
    
    if anomaly and policy_decision:
        response_col1, response_col2 = st.columns([2, 1])
        
        with response_col1:
            st.write(f"**Recommended Action:** `{policy_decision['recommended_action']}`")
            
            if policy_decision['should_escalate_to_safe_mode']:
                st.error("🚨 **CRITICAL:** Escalating to SAFE_MODE for critical anomaly")
            else:
                allowed_actions = policy_decision['policy_decision']['allowed_actions']
                if allowed_actions:
                    st.success(f"**Available actions in {st.session_state.mission_phase}:**")
                    for action in allowed_actions:
                        st.write(f"  ✓ {action}")
                else:
                    st.warning(f"⚠️ No automated actions available in {st.session_state.mission_phase}")
        
        with response_col2:
            st.metric("Action Priority", "HIGH" if policy_decision['should_escalate_to_safe_mode'] else "MEDIUM")
            st.metric("Response Time", f"{np.random.randint(50, 200)}ms")
    else:
        st.info("ℹ️ No active recovery actions required")

    # Logs Section
    st.markdown("---")
    log_col1, log_col2 = st.columns(2)
    
    with log_col1:
        st.subheader("📜 Event Log Stream")
        log_text = "\n".join(st.session_state.logs[-15:])
        st.code(log_text, language="log")
    
    with log_col2:
        st.subheader("📊 Decision Log")
        if st.session_state.decision_logs:
            decision_display = []
            for d in st.session_state.decision_logs[-10:]:
                decision_display.append({
                    "Time": d['timestamp'].strftime("%H:%M:%S"),
                    "Phase": d['mission_phase'],
                    "Anomaly": d['anomaly_type'],
                    "Severity": f"{d['severity_score']:.2f}",
                    "Action": d['recommended_action'][:20] + "...",
                    "Escalated": "🔴" if d['should_escalate_to_safe_mode'] else "🟢"
                })
            st.dataframe(pd.DataFrame(decision_display), use_container_width=True, hide_index=True)
        else:
            st.info("No decisions logged yet")

    # Phase History
    with st.expander("🕐 Phase History & Timeline"):
        history = state_machine.get_phase_history()
        if history:
            history_df = pd.DataFrame([
                {"Phase": p[0], "Timestamp": p[1]} for p in history[-15:]
            ])
            st.dataframe(history_df, use_container_width=True, hide_index=True)
        else:
            st.info("No phase transitions recorded")

    # Footer
    st.markdown("---")
    year = datetime.now().year
    st.markdown(f"""
    <div style="background: rgba(10, 14, 26, 0.8); border-top: 1px solid rgba(255, 255, 255, 0.1); padding: 2rem 0; margin-top: 2rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; color: #b8b8d1;">
            <div style="font-weight: 700; color: #ffffff;">🛰️ AstraGuard Mission Control</div>
            <div style="font-size: 0.9rem;">Powered by AI-driven anomaly detection</div>
            <div style="font-size: 0.85rem; color: #8b8ba7;">&copy; {year} AstraGuard AI. All rights reserved.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    time.sleep(0.5)
    st.rerun()

else:
    # Offline state
    st.info("📡 **Telemetry is currently offline.** Click the '▶️ Start' button in the sidebar to begin monitoring.")
    
    # Show system readiness
    st.markdown("---")
    st.subheader("🔧 System Readiness")
    
    ready_col1, ready_col2, ready_col3 = st.columns(3)
    with ready_col1:
        st.metric("State Machine", "✅ Ready")
    with ready_col2:
        st.metric("Policy Engine", "✅ Ready")
    with ready_col3:
        st.metric("Phase Handler", "✅ Ready")
    
    # Show last session stats if available
    if st.session_state.total_samples > 0:
        st.markdown("---")
        st.subheader("📊 Last Session Statistics")
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        with stat_col1:
            st.metric("Total Samples", st.session_state.total_samples)
        with stat_col2:
            st.metric("Total Anomalies", st.session_state.total_anomalies)
        with stat_col3:
            rate = (st.session_state.total_anomalies / st.session_state.total_samples * 100) if st.session_state.total_samples > 0 else 0
            st.metric("Anomaly Rate", f"{rate:.1f}%")
        with stat_col4:
            st.metric("Last Phase", st.session_state.mission_phase)
    
    # Footer for offline state
    st.markdown("---")
    year = datetime.now().year
    st.markdown(f"""
    <div style="background: rgba(10, 14, 26, 0.8); border-top: 1px solid rgba(255, 255, 255, 0.1); padding: 2rem 0; margin-top: 3rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; color: #b8b8d1;">
            <div style="font-weight: 700; color: #ffffff;">🛰️ AstraGuard Mission Control</div>
            <div style="font-size: 0.9rem;">Powered by AI-driven anomaly detection</div>
            <div style="font-size: 0.85rem; color: #8b8ba7;">&copy; {year} AstraGuard AI. All rights reserved.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
