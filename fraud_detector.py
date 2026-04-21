### Fraudulent participation detector for behavioral tasks (GNG, 2AFC, AAT)
### Author: Marie Pittet
### Date: March 2026

import streamlit as st
import pandas as pd
import plotly.express as px

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
        "min_rt": 200, 
        "rt_col": "afc_rt", 
        "resp_col": "afc_chosen_side", 
        "pretty": "2-AFC"
    },
    "AAT": {
        "min_rt": 250, 
        "rt_col": "aat_rt", 
        "resp_col": "aat_response", 
        "cond_col": "aat_congruency", # Updated to match CSV
        "pretty": "Approach-Avoidance"
    }
}

def extract_pid(filename):
    return filename.split('_')[0]

# 2. App UI
st.set_page_config(page_title="Fraudulent participation detector", layout="wide")
st.title("🕵️ Fraudulent participation detector")

uploaded_files = st.file_uploader("Upload participant(s) CSVs", type="csv", accept_multiple_files=True)

if uploaded_files:
    participant_files = {}
    for f in uploaded_files:
        pid = extract_pid(f.name)
        if pid not in participant_files: 
            participant_files[pid] = []
        participant_files[pid].append(f)

    all_summary = []
    plot_data = {}

    for pid, files in participant_files.items():
        p_result = {"ID": pid, "Status": "✅ CLEAN", "Flags": [], "Flag Count": 0}
        all_trials_for_p = []

        for file in files:
            task_type = next((t for t in TASK_INFO if t in file.name.upper()), None)
            if not task_type: 
                continue
            
            df = pd.read_csv(file)
            # Normalize columns to lowercase for easier matching
            df.columns = [c.strip().lower() for c in df.columns]
            info = TASK_INFO[task_type]
            
            # --- Data Extraction ---
            rt_col_found = None
            # Check if RT column exists (case-insensitive check already done by df.columns normalization)
            if info["rt_col"] and info["rt_col"] in df.columns:
                trials = df[df[info["rt_col"]].notna()].copy()
                trials['clean_rt'] = trials[info["rt_col"]] * 1000
            else:
                # Manual fallback for PsychoPy times
                start_col = f"{task_type.lower()}_trial.started"
                stop_col = f"{task_type.lower()}_trial.stopped"
                if start_col in df.columns and stop_col in df.columns:
                    trials = df[df[start_col].notna()].copy()
                    trials['clean_rt'] = (trials[stop_col] - trials[start_col]) * 1000
                    if task_type == "AFC": 
                        trials['clean_rt'] -= 500
                else: 
                    # Cannot find timing data, skip this file
                    continue

            trials = trials[trials['clean_rt'] > 1] 
            trials['task_label'] = task_type

            # --- Fraud Rules ---
            
            # 1. Speeding
            too_fast_rate = (trials['clean_rt'] < info['min_rt']).mean()
            if too_fast_rate > 0.15:
                p_result["Flags"].append(f"{task_type}: Speeding ({too_fast_rate:.0%})")

            # 2. GNG Specifics
            if task_type == "GNG":
                if "isgo" in df.columns and "responded" in df.columns:
                    nogo_trials = df[df['isgo'] == 0]
                    if len(nogo_trials) > 0:
                        fa_rate = nogo_trials['responded'].fillna(0).mean()
                        if fa_rate > 0.30:
                            p_result["Flags"].append(f"GNG: High false alarms ({fa_rate:.0%})")
                    
                    go_trials = df[df['isgo'] == 1]
                    if len(go_trials) > 0:
                        miss_rate = 1 - go_trials['responded'].fillna(0).mean()
                        if miss_rate > 0.10:
                            p_result["Flags"].append(f"GNG: High miss Rate ({miss_rate:.0%})")

            # 3. AFC Specifics
            if task_type == "AFC" and info["resp_col"] in trials.columns:
                streaks = trials[info["resp_col"]].ne(trials[info["resp_col"]].shift()).cumsum()
                max_streak = trials.groupby(streaks).size().max()
                if max_streak > 10:
                    p_result["Flags"].append(f"AFC: Long streak ({max_streak} trials)")

            # 4. AAT Specifics (CORRECTED LOGIC)
            if task_type == "AAT":
                # Check for the actual column names in your CSV (normalized to lowercase)
                # Your CSV has: 'aat_congruency' (compatible/incompatible) and 'aat_response' (approach/avoid)
                if "aat_congruency" in trials.columns and "aat_response" in trials.columns:
                    
                    # Define correctness based on AAT rules:
                    # Compatible + Approach = Correct
                    # Incompatible + Avoid = Correct
                    
                    def check_aat_correct(row):
                        rule = str(row['aat_congruency']).lower()
                        action = str(row['aat_response']).lower()
                        
                        if rule == 'compatible' and action == 'approach':
                            return 1
                        elif rule == 'incompatible' and action == 'avoid':
                            return 1
                        else:
                            return 0

                    trials['is_correct'] = trials.apply(check_aat_correct, axis=1)
                    
                    # Calculate error rate
                    # Avoid division by zero if no trials
                    if len(trials) > 0:
                        aat_error_rate = 1 - trials['is_correct'].mean()
                        
                        if aat_error_rate > 0.25:
                            p_result["Flags"].append(f"AAT: High error rate ({aat_error_rate:.0%})")
                        
                        # Check for response streaks (ignoring the rule, just looking at motor repetition)
                        aat_streaks = trials['aat_response'].ne(trials['aat_response'].shift()).cumsum()
                        max_aat_streak = trials.groupby(aat_streaks).size().max()
                        if max_aat_streak > 12:
                            p_result["Flags"].append(f"AAT: Long streak ({max_aat_streak} trials)")
                    else:
                        p_result["Flags"].append("AAT: No valid trials found")
                else:
                    # Debug info if columns are missing
                    available_cols = [c for c in trials.columns if 'aat' in c]
                    p_result["Flags"].append(f"AAT: Missing columns. Found: {available_cols}")

            all_trials_for_p.append(trials[['task_label', 'clean_rt']])

        # --- Finalize Participant Result ---
        p_result["Flag Count"] = len(p_result["Flags"])
        if p_result["Flag Count"] > 0:
            p_result["Status"] = "🚩 SUSPICIOUS"
            p_result["Reasoning"] = " | ".join(p_result["Flags"])
        else:
            p_result["Reasoning"] = "No suspicious patterns detected."
        
        display_dict = {k: v for k, v in p_result.items() if k != "Flags"}
        all_summary.append(display_dict)
        
        if all_trials_for_p: 
            plot_data[pid] = pd.concat(all_trials_for_p, ignore_index=True)

    # --- Display Results ---
    if all_summary:
        report_df = pd.DataFrame(all_summary).sort_values(by="Flag Count", ascending=False)
        st.subheader("Batch report")
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        
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
