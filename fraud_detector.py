### Fraudulent participation detector for behavioral tasks (GNG, 2AFC, AAT)
### Author: Marie Pittet
### Date: March 2026

import streamlit as st
import pandas as pd
import plotly.express as px
import re

# 1. Task metrics and thresholds for fraud detection
TASK_INFO = {
    "GNG": {
        "min_rt": 250, 
        "rt_col": "rt", 
        "resp_col": "responded", 
        "cond_col": "isgo", 
        "pretty": "Go/No-Go"
    },
    "AFC": {
        "min_rt": 200, # lower threshold since the rule here is purely preference (reaction to prefered item may be fast)
        "rt_col": "afc_rt", 
        "resp_col": "afc_chosen_side", 
        "pretty": "2-AFC"
    },
    "AAT": {
        "min_rt": 250, 
        "rt_col": "aat_rt", 
        "resp_col": "aat_responded", 
        "cond_col": "aat_cond",
        "pretty": "Approach-Avoidance"
    }
}

def extract_pid(filename):
    match = re.search(r'(\d+)', filename)
    return match.group(1) if match else filename

# 2. App ui
st.set_page_config(page_title="Fraudulent participation detector", layout="wide")
st.title("🕵️ Fraudulent participation detector")

uploaded_files = st.file_uploader("Upload participant(s) CSVs", type="csv", accept_multiple_files=True)

if uploaded_files:
    participant_files = {}
    for f in uploaded_files:
        pid = extract_pid(f.name)
        if pid not in participant_files: participant_files[pid] = []
        participant_files[pid].append(f)

    all_summary = []
    plot_data = {}

    for pid, files in participant_files.items():
        p_result = {"ID": pid, "Status": "✅ CLEAN", "Flags": [], "Flag Count": 0}
        all_trials_for_p = []

        for file in files:
            task_type = next((t for t in TASK_INFO if t in file.name.upper()), None)
            if not task_type: continue
            
            df = pd.read_csv(file)
            df.columns = [c.strip().lower() for c in df.columns]
            info = TASK_INFO[task_type]
            
            # Data extraction 
            if info["rt_col"] and info["rt_col"] in df.columns:
                trials = df[df[info["rt_col"]].notna()].copy()
                trials['clean_rt'] = trials[info["rt_col"]] * 1000
            else:
                # Manual fallback
                start_col = f"{task_type.lower()}_trial.started"
                stop_col = f"{task_type.lower()}_trial.stopped"
                if start_col in df.columns and stop_col in df.columns:
                    trials = df[df[start_col].notna()].copy()
                    trials['clean_rt'] = (trials[stop_col] - trials[start_col]) * 1000
                    if task_type == "AFC": trials['clean_rt'] -= 500
                else: continue

            trials = trials[trials['clean_rt'] > 1] 
            trials['task_label'] = task_type

            # 3. Fraud rules
            
            # Unnaturally low variability: very low variability in RTs suggesting someone mashed or a bot completed the task
            rt_iqr = trials['clean_rt'].quantile(0.75) - trials['clean_rt'].quantile(0.25)
            if rt_iqr < 75:
                p_result["Flags"].append(f"{task_type}: Low variability (IQR {rt_iqr:.0f}ms)")
            
            # Speeding: too many trials faster than the minimum RT threshold (speed running, or computer completion)
            too_fast_rate = (trials['clean_rt'] < info['min_rt']).mean()
            if too_fast_rate > 0.15:
                p_result["Flags"].append(f"{task_type}: Speeding ({too_fast_rate:.0%})")

            # GNG: high error rates
            if task_type == "GNG":
                if "isgo" in df.columns and "responded" in df.columns:
                    # High commission error rate (always tapping on NoGo items)
                    nogo_trials = df[df['isgo'] == 0]
                    if len(nogo_trials) > 0:
                        fa_rate = nogo_trials['responded'].fillna(0).mean()
                        if fa_rate > 0.20:
                            p_result["Flags"].append(f"GNG: High false alarms ({fa_rate:.0%})")
                    
                    # High omission error rate (letting the task run and doing something else)
                    go_trials = df[df['isgo'] == 1]
                    if len(go_trials) > 0:
                        miss_rate = 1 - go_trials['responded'].fillna(0).mean()
                        if miss_rate > 0.10:
                            p_result["Flags"].append(f"GNG: High miss Rate ({miss_rate:.0%})")

            # AFC: long streaks of the same item position (always picking the item on the left, or on the right)
            if task_type == "AFC" and info["resp_col"] in trials.columns:
                streaks = trials[info["resp_col"]].ne(trials[info["resp_col"]].shift()).cumsum()
                max_streak = trials.groupby(streaks).size().max()
                if max_streak > 12:
                    p_result["Flags"].append(f"AFC: Long streak ({max_streak} trials)")

            # AAT: long streaks of the same answers and suspiciously low accuracy 
            if task_type == "AAT":
                if "aat_cond" in df.columns and "aat_responded" in df.columns:
                    # Accuracy (Cond vs Responded)
                    trials['is_correct'] = (trials['aat_cond'] == trials['aat_responded']).astype(int)
                    aat_error_rate = 1 - trials['is_correct'].mean()
                    if aat_error_rate > 0.35:
                        p_result["Flags"].append(f"AAT: High error rate ({aat_error_rate:.0%})")
                    
                    # Response Streak (Pulling/Pushing regardless of rule)
                    aat_streaks = trials['aat_responded'].ne(trials['aat_responded'].shift()).cumsum()
                    max_aat_streak = trials.groupby(aat_streaks).size().max()
                    if max_aat_streak > 12:
                        p_result["Flags"].append(f"AAT: Long streak ({max_aat_streak} trials)")

            all_trials_for_p.append(trials[['task_label', 'clean_rt']])

        # 5. Results, table, and plots
        p_result["Flag Count"] = len(p_result["Flags"])
        if p_result["Flag Count"] > 0:
            p_result["Status"] = "🚩 SUSPICIOUS"
            p_result["Reasoning"] = " | ".join(p_result["Flags"])
        else:
            p_result["Reasoning"] = "No suspicious patterns detected."
        
        display_dict = {k: v for k, v in p_result.items() if k != "Flags"}
        all_summary.append(display_dict)
        if all_trials_for_p: plot_data[pid] = pd.concat(all_trials_for_p)
    # Table
    if all_summary:
        report_df = pd.DataFrame(all_summary).sort_values(by="Flag Count", ascending=False)
        st.subheader("Batch report")
        st.dataframe(report_df, use_container_width=True, hide_index=True)
    # Plots for each participant
    if plot_data:
        st.divider()
        st.subheader("Trial distribution inspection")
        selected_pid = st.selectbox("Select participant:", list(plot_data.keys()))
        full_df = plot_data[selected_pid]
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.box(full_df, x="task_label", y="clean_rt", color="task_label", points="all"), use_container_width=True)
        with col2:
            st.plotly_chart(px.line(full_df, y="clean_rt", color="task_label"), use_container_width=True)
