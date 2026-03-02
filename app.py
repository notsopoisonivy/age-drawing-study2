import streamlit as st
from streamlit_drawable_canvas import st_canvas
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
import time

# --- Page Config ---
st.set_page_config(page_title="Motor Control Study", layout="centered")
st.title("Age vs Motor Control Study")

# --- Connect to Google Sheets ---
# This looks for [connections.gsheets] in your .streamlit/secrets.toml
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    sheet_available = True
except Exception as e:
    sheet_available = False
    st.sidebar.error("Google Sheets not connected. Download button will be your backup.")

# --- Initialize Session State ---
if "step" not in st.session_state:
    st.session_state.step = "info"
if "task_index" not in st.session_state:
    st.session_state.task_index = 0
if "all_data" not in st.session_state:
    st.session_state.all_data = []

drawing_tasks = ["Draw a straight horizontal line", "Draw a circle", "Sign your name naturally"]

# --- Step 1: Participant Info ---
if st.session_state.step == "info":
    st.header("Step 1: Participant Information")
    p_id = st.text_input("Participant ID (please enter your name)", key="p_id_input")
    a_grp = st.selectbox("Age Group", [str(i) for i in range(1, 101)], index=25)
    
    if st.button("Start Study"):
        if p_id:
            st.session_state.participant_id = p_id
            st.session_state.age_group = a_grp
            st.session_state.step = "drawing"
            st.rerun()
        else:
            st.error("Please enter a Participant ID")

# --- Step 2: Drawing Tasks (Timing + Sync) ---
elif st.session_state.step == "drawing":
    idx = st.session_state.task_index
    current_task = drawing_tasks[idx]
    
    st.header(f"Drawing Task {idx + 1} of {len(drawing_tasks)}")
    st.info(f"**Instructions:** {current_task}")

    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 0, 0)",
        stroke_width=2,
        stroke_color="black",
        background_color="white",
        height=400,
        width=700,
        drawing_mode="freedraw",
        key=f"canvas_{idx}" 
    )

    # Capture the "First Touch" for accurate duration
    if canvas_result.json_data and canvas_result.json_data.get("objects"):
        if f"first_touch_{idx}" not in st.session_state:
            st.session_state[f"first_touch_{idx}"] = time.time()

    if st.button("Submit & Next"):
        if canvas_result.json_data and canvas_result.json_data.get("objects"):
            actual_start = st.session_state.get(f"first_touch_{idx}", time.time())
            actual_end = time.time()
            total_duration = actual_end - actual_start
            
            objects = canvas_result.json_data.get("objects", [])
            all_points = [p for obj in objects for p in obj.get("path", []) if len(p) >= 3]
            num_points = len(all_points)
            
            if num_points > 0:
                new_rows = []
                for i, p in enumerate(all_points):
                    point_ts = actual_start + (i / num_points) * total_duration
                    row = {
                        "participant_id": st.session_state.participant_id,
                        "age_group": st.session_state.age_group,
                        "task": current_task,
                        "x": p[1],
                        "y": p[2],
                        "timestamp": point_ts,
                        "point_index": i,
                        "total_task_duration": total_duration
                    }
                    st.session_state.all_data.append(row)
                    new_rows.append(row)
                
                # --- GOOGLE SHEETS SYNC ---
                if sheet_available:
                    with st.spinner("Syncing to Google Sheets..."):
                        try:
                            # Try to append to existing data
                            existing_df = conn.read(worksheet="MotorStudy")
                            updated_df = pd.concat([existing_df, pd.DataFrame(new_rows)], ignore_index=True)
                            conn.update(worksheet="MotorStudy", data=updated_df)
                        except Exception:
                            # If sheet is empty/new, just upload the new rows
                            conn.update(worksheet="MotorStudy", data=pd.DataFrame(new_rows))

                # Advance Task
                if idx + 1 < len(drawing_tasks):
                    st.session_state.task_index += 1
                else:
                    st.session_state.step = "typing"
                st.rerun()
        else:
            st.warning("Please draw the task first.")

# --- Step 3: Typing Task ---
elif st.session_state.step == "typing":
    st.header("Step 3: Typing Task")
    sentence = "The quick brown fox jumps over the lazy dog"
    st.code(sentence)
    
    with st.form("typing_form"):
        typed_text = st.text_input("Type here:")
        submit_typing = st.form_submit_button("Finish Study")
        
        if submit_typing:
            if typed_text:
                st.session_state.all_data.append({
                    "participant_id": st.session_state.participant_id,
                    "age_group": st.session_state.age_group,
                    "task": "Typing",
                    "timestamp": time.time(),
                    "content": typed_text
                })
                st.session_state.step = "download"
                st.rerun()

# --- Step 4: Download ---
elif st.session_state.step == "download":
    st.header("Study Complete!")
    st.balloons()
    
    df = pd.DataFrame(st.session_state.all_data)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="📥 Download Results CSV", data=csv, file_name="study_results.csv")
    
    if st.button("Start New Session"):
        st.session_state.clear()
        st.rerun()