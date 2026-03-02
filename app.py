# import sys
# st.write(sys.executable)
import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_drawable_canvas import st_canvas
import pandas as pd
import numpy as np
import time

# --- Page Config ---
st.set_page_config(page_title="Motor Control Study", layout="centered")
st.title("Age vs Motor Control Study")

# This manually pulls the secrets to prove they exist
try:
    # We check if the keys exist first to debug
    if "connections" in st.secrets and "supabase" in st.secrets["connections"]:
        s_url = st.secrets["connections"]["supabase"]["url"]
        s_key = st.secrets["connections"]["supabase"]["key"]
        
        conn = st.connection(
            "supabase",
            type=SupabaseConnection,
            url=s_url,
            key=s_key
        )
        db_available = True
    else:
        db_available = False
        st.sidebar.error("Secrets found, but [connections.supabase] section is missing.")
except Exception as e:
    db_available = False
    st.sidebar.error(f"Connection Failed: {e}")
    
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

# --- Step 2: Drawing Tasks ---
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
                        "participant_id": str(st.session_state.participant_id),
                        "age_group": int(st.session_state.age_group),
                        "task": current_task,
                        "x": float(p[1]),
                        "y": float(p[2]),
                        "timestamp": float(point_ts),
                        "point_index": int(i),
                        "total_task_duration": float(total_duration)
                    }
                    st.session_state.all_data.append(row)
                    new_rows.append(row)
                
                # --- SUPABASE SYNC ---
                if db_available:
                    with st.spinner("Syncing to Database..."):
                        try:
                            # In Supabase, we just insert the list of dictionaries
                            conn.table("motor_data").insert(new_rows).execute()
                        except Exception as e:
                            st.error(f"Database sync failed: {e}")

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
                typing_row = {
                    "participant_id": str(st.session_state.participant_id),
                    "age_group": int(st.session_state.age_group),
                    "task": "Typing",
                    "x": 0.0, # Placeholder for DB schema consistency
                    "y": 0.0,
                    "timestamp": float(time.time()),
                    "point_index": 0,
                    "total_task_duration": 0.0
                }
                st.session_state.all_data.append(typing_row)
                
                if db_available:
                    conn.table("motor_data").insert([typing_row]).execute()
                
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