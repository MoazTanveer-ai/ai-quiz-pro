import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import sqlite3
import time
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="AI Quiz Pro", page_icon="⚡", layout="wide")

API_KEY = "AQ.Ab8RN6IPKBjdyvM_3ADDwc4uHppx5ES2blFHzjcJaUZ1tLEPVA"
genai.configure(api_key=API_KEY)

# --- 100% ACCURATE BUTTONS & CONTRAST ---
st.markdown("""
<style>
    /* 1. Main Background */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #090d16 0%, #1e1b4b 50%, #090d16 100%) !important;
    }

    /* 2. Main Screen Text White */
    section[data-testid="stMain"] * {
        color: #ffffff !important;
    }

    /* Form Container Dark */
    div[data-testid="stForm"] {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
    }

    /* 3. Sidebar Pure White Background & Black Text */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
    }
    section[data-testid="stSidebar"] * {
        color: #000000 !important;
    }
    section[data-testid="stSidebar"] input, 
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] [data-baseweb="select"] * {
        background-color: #f1f5f9 !important;
        color: #000000 !important;
    }

    /* ================= BUTTON STYLES ================= */

    /* 4. MAIN SCREEN: Generate Quiz Button (Solid Black + White Text) */
    section[data-testid="stMain"] .stButton > button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 2px solid #ffffff !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 8px !important;
        padding: 8px 24px !important;
    }

    /* 5. MAIN SCREEN: Submit Quiz Button (Solid Green + Crisp White Text) */
    div[data-testid="stFormSubmitButton"] button, 
    button[kind="primaryFormSubmit"], 
    button[kind="secondaryFormSubmit"] {
        background-color: #10b981 !important;
        color: #ffffff !important;
        border: 2px solid #059669 !important;
        font-weight: bold !important;
        font-size: 18px !important;
        border-radius: 8px !important;
        width: 100% !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #059669 !important;
    }

    /* 6. SIDEBAR: Reset Everything Button (Soft Red Button) */
    section[data-testid="stSidebar"] button {
        background-color: #fee2e2 !important;
        color: #dc2626 !important;
        border: 1px solid #f87171 !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: #ef4444 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)
# --- DATABASE SETUP (SQLITE) ---
def init_db():
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT,
                    diff TEXT,
                    score TEXT,
                    xp INTEGER,
                    date TEXT
                )''')
    conn.commit()
    conn.close()

def save_quiz_record(topic, diff, score, xp):
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO quiz_history (topic, diff, score, xp, date) VALUES (?, ?, ?, ?, ?)",
              (topic, diff, score, xp, datetime.now().strftime("%d %b, %H:%M")))
    conn.commit()
    conn.close()

def get_history_and_stats():
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute("SELECT topic, diff, score, xp, date FROM quiz_history ORDER BY id DESC LIMIT 5")
    history = c.fetchall()
    c.execute("SELECT SUM(xp) FROM quiz_history")
    total_xp = c.fetchone()[0] or 0
    total_xp = max(0, total_xp)

    c.execute("SELECT score FROM quiz_history ORDER BY id ASC")
    all_scores_raw = c.fetchall()
    score_percentages = []
    for (s,) in all_scores_raw:
        try:
            num, den = map(int, s.split('/'))
            score_percentages.append(round((num / den) * 100))
        except:
            pass
            
    conn.close()
    return history, total_xp, score_percentages

def get_player_rank(xp):
    if xp < 50:
        return "🥉 Novice (Lvl 1)"
    elif xp < 150:
        return "🥈 Scholar (Lvl 2)"
    elif xp < 300:
        return "🥇 Master (Lvl 3)"
    else:
        return "👑 Grandmaster (Lvl 4)"

init_db()

# --- SESSION STATE INITIALIZATION ---
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = None
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'time_taken' not in st.session_state:
    st.session_state.time_taken = 0
if 'saved_to_db' not in st.session_state:
    st.session_state.saved_to_db = False
if 'tutor_explanations' not in st.session_state:
    st.session_state.tutor_explanations = {}

recent_history, total_xp, score_percentages = get_history_and_stats()

# --- SIDEBAR (SETTINGS & STATS) ---
with st.sidebar:
    st.header("👤 Player Profile")
    st.markdown(f"""
    <div style="background-color: #f1f5f9; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1;">
        <span style="color: #475569; font-size: 13px; font-weight: bold;">TOTAL XP EARNED</span>
        <h2 style="color: #000000 !important; margin: 4px 0 0 0; font-size: 28px;">⭐ {total_xp} XP</h2>
    </div>
    """, unsafe_allow_html=True)
    st.write(f"**Rank:** {get_player_rank(total_xp)}")
    
    if len(score_percentages) >= 2:
        st.write("📈 **Score Progress (%)**")
        st.line_chart(score_percentages)
    
    st.write("---")
    st.header("⚙️ Quiz Settings")
    topic = st.text_input("Topic:", "Python Programming")
    num_q = st.slider("Number of Questions:", 1, 10, 4)
    diff = st.selectbox("Difficulty:", ["Easy", "Medium", "Hard"])
    q_type = st.selectbox("Question Type:", ["MCQ (4 Options)", "True / False", "Mixed"])
    lang = st.selectbox("Language:", ["English", "Roman Urdu", "Urdu (اردو)", "Hindi", "Spanish"])
    timer_option = st.selectbox("Timer:", ["No Timer", "1 Minute", "2 Minutes", "5 Minutes"])
    
    if st.button("Reset Everything 🔄"):
        st.session_state.quiz_data = None
        st.session_state.submitted = False
        st.session_state.end_time = None
        st.session_state.start_time = None
        st.session_state.time_taken = 0
        st.session_state.saved_to_db = False
        st.session_state.tutor_explanations = {}
        st.rerun()

    st.write("---")
    st.header("📜 Recent Quizzes")
    if recent_history:
        for item in recent_history:
            xp_sign = f"+{item[3]}" if item[3] >= 0 else f"{item[3]}"
            st.caption(f"**{item[0]}** ({item[1]}) • {item[4]}")
            st.text(f"Score: {item[2]} | {xp_sign} XP")
    else:
        st.caption("No quiz records yet.")

# --- MAIN UI ---
st.title("🤖 AI Quiz Pro")
st.caption("⚡ Test your knowledge • Earn XP • Watch out for Negative Marking!")

# --- GENERATE QUIZ ---
if st.button("Generate Quiz 🚀"):
    st.session_state.quiz_data = None
    st.session_state.submitted = False
    st.session_state.saved_to_db = False
    st.session_state.end_time = None
    st.session_state.time_taken = 0
    st.session_state.tutor_explanations = {}
    
    with st.spinner(f"AI generating {diff} {q_type} quiz in {lang}..."):
        prompt = f"""
        You are an expert quiz generator. Return ONLY a valid JSON list of {num_q} questions.
        Topic: {topic}
        Difficulty: {diff}
        Question Type: {q_type}
        Language: {lang}. Strictly output ALL text (questions, options, answers, explanations) in {lang}.

        Rules:
        - If 'True / False', Options must be exactly 2 choices.
        - If 'MCQ', Options must contain 4 distinct choices.
        - Answer MUST exactly match one of the choices in Options.
        - Strictly NO markdown tags like ```json. Do NOT write conversational text.

        JSON Format:
        [
          {{
            "Question": "Question text here",
            "Options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "Answer": "Option 1",
            "Explanation": "Explanation text here"
          }}
        ]
        """
        
        candidate_models = ['models/gemini-3.6-flash', 'models/gemini-3.7-flash']
        raw_text = ""
        
        for m_name in candidate_models:
            try:
                active_model = genai.GenerativeModel(m_name)
                response = active_model.generate_content(prompt)
                raw_text = response.text.strip()
                if raw_text:
                    break
            except Exception as e:
                continue

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        try:
            st.session_state.quiz_data = json.loads(raw_text)
            st.session_state.current_topic = topic
            st.session_state.current_diff = diff
            st.session_state.current_lang = lang
            st.session_state.start_time = time.time()
            
            if timer_option != "No Timer":
                mins = int(timer_option.split()[0])
                st.session_state.end_time = time.time() + (mins * 60)
            else:
                st.session_state.end_time = None

            st.rerun()
        except Exception as err:
            st.error(f"Quiz generate nahi ho saka. AI Error: {err}")

# --- DISPLAY QUIZ FORM ---
if st.session_state.quiz_data and not st.session_state.submitted:
    
    if st.session_state.end_time:
        remaining_secs = int(st.session_state.end_time - time.time())
        if remaining_secs <= 0:
            st.error("⏰ Time up ho gaya hai! Neeche Submit button dabayein.")
        else:
            timer_code = f"""
            <div style="background: rgba(239, 68, 68, 0.25); border: 2px solid #ef4444; border-radius: 8px; padding: 10px; text-align: center; font-family: sans-serif;">
                <span style="font-size: 18px; font-weight: bold; color: #fca5a5;">⏳ Time Remaining: </span>
                <span id="countdown" style="font-size: 22px; font-weight: bold; color: #ffffff;"></span>
            </div>
            <script>
                var timeLeft = {remaining_secs};
                var display = document.getElementById('countdown');
                var timerInterval = setInterval(function() {{
                    var minutes = Math.floor(timeLeft / 60);
                    var seconds = timeLeft % 60;
                    display.innerText = (minutes < 10 ? '0' : '') + minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
                    if (timeLeft <= 0) {{
                        clearInterval(timerInterval);
                        display.innerText = "00:00 (Time's Up!)";
                        alert("⏰ Time khatam ho gaya! Quiz submit karein.");
                    }}
                    timeLeft--;
                }}, 1000);
            </script>
            """
            components.html(timer_code, height=65)

    with st.form("quiz_form"):
        st.write("---")
        for i, q in enumerate(st.session_state.quiz_data):
            st.subheader(f"Q{i+1}: {q['Question']}")
            st.radio("Options:", q['Options'], key=f"q_{i}", index=None)
            st.write("")
        
        submit_btn = st.form_submit_button("Submit Quiz ✅")
        if submit_btn:
            all_answered = all(st.session_state.get(f"q_{i}") is not None for i in range(len(st.session_state.quiz_data)))
            if not all_answered:
                st.warning("⚠️ Sabhi sawalon ke jawab select karein!")
            else:
                if st.session_state.start_time:
                    st.session_state.time_taken = int(time.time() - st.session_state.start_time)
                st.session_state.submitted = True
                st.rerun()

# --- RESULTS SCREEN ---
if st.session_state.submitted and st.session_state.quiz_data:
    st.write("---")
    st.header("📊 Quiz Results")
    score = 0
    total = len(st.session_state.quiz_data)
    
    for i, q in enumerate(st.session_state.quiz_data):
        user_answer = st.session_state.get(f"q_{i}", "Not Answered")
        is_correct = user_answer == q['Answer']
        
        if is_correct:
            score += 1
            st.success(f"**Q{i+1}: {q['Question']}**\n\n✅ **Your Answer:** {user_answer}\n\n💡 *{q['Explanation']}*")
        else:
            st.error(f"**Q{i+1}: {q['Question']}**\n\n❌ **Your Answer:** {user_answer}\n\n✅ **Correct Answer:** {q['Answer']}\n\n💡 *{q['Explanation']}*")
            
            with st.expander(f"🤖 Samajh nahi aaya? AI Tutor se poocho (Q{i+1})"):
                if i in st.session_state.tutor_explanations:
                    st.info(st.session_state.tutor_explanations[i])
                else:
                    if st.button(f"Deep Explanation & Code Example 💡", key=f"explain_btn_{i}"):
                        with st.spinner("AI Teacher samjha raha hai..."):
                            tutor_prompt = f"""
                            You are a friendly, encouraging teacher.
                            Question: {q['Question']}
                            User's Wrong Choice: {user_answer}
                            Actual Correct Answer: {q['Answer']}
                            
                            Explain why the user's choice was wrong and break down the correct concept simply.
                            Provide a very small, clear code or real-world example.
                            Language: {st.session_state.get('current_lang', 'English')}
                            """
                            try:
                                tutor_model = genai.GenerativeModel('models/gemini-3.6-flash')
                                t_res = tutor_model.generate_content(tutor_prompt)
                                st.session_state.tutor_explanations[i] = t_res.text
                                st.rerun()
                            except Exception as e:
                                st.error(f"AI Tutor error: {e}")
        st.write("---")
        
    accuracy = (score / total) * 100
    
    wrong_count = total - score
    base_xp = score * 10
    penalty_xp = (wrong_count // 2) * 10
    net_xp = base_xp - penalty_xp

    if not st.session_state.saved_to_db:
        save_quiz_record(
            st.session_state.get('current_topic', 'General'),
            st.session_state.get('current_diff', 'Medium'),
            f"{score}/{total}",
            net_xp
        )
        st.session_state.saved_to_db = True

    taken_secs = st.session_state.get('time_taken', 0)
    mins_taken, s_taken = divmod(taken_secs, 60)
    time_str = f"{mins_taken}m {s_taken}s" if mins_taken > 0 else f"{s_taken}s"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="Final Score", value=f"{score}/{total}", delta=f"{accuracy:.0f}%")
    col2.metric(label="Earned XP", value=f"+{base_xp} XP")
    col3.metric(label="Penalty", value=f"-{penalty_xp} XP" if penalty_xp > 0 else "0 XP")
    col4.metric(label="Time Taken ⏱️", value=time_str)
    
    if penalty_xp > 0:
        st.warning(f"⚠️ **Negative Marking:** {wrong_count} sawal galat hone par **-{penalty_xp} XP** ki katauti hui! Net XP: **{net_xp} XP**")
    else:
        st.success(f"🌟 **Zabardast!** Koi penalty nahi lagi. Net XP: **+{net_xp} XP**")

    if score == total:
        st.balloons()
        st.success("🎉 Perfect Score! Kamaal kar diya!")

    if st.button("Take Another Quiz 🔄"):
        st.session_state.quiz_data = None
        st.session_state.submitted = False
        st.session_state.end_time = None
        st.session_state.start_time = None
        st.session_state.time_taken = 0
        st.session_state.saved_to_db = False
        st.session_state.tutor_explanations = {}
        st.rerun()