import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
import json
import sqlite3
import time
import re
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="AI Quiz Pro", page_icon="⚡", layout="wide")

# --- SECURE API KEY CONFIGURATION ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = "AIzaSy_YOUR_API_KEY_HERE"

genai.configure(api_key=API_KEY)

# --- 100% ACCURATE BUTTONS & CONTRAST ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #090d16 0%, #1e1b4b 50%, #090d16 100%) !important;
    }
    section[data-testid="stMain"] * {
        color: #ffffff !important;
    }
    div[data-testid="stForm"] {
        background-color: #1e293b !important;
        border: 1px solid #475569 !important;
    }
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
    section[data-testid="stMain"] .stButton > button {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: 2px solid #ffffff !important;
        font-weight: bold !important;
        font-size: 16px !important;
        border-radius: 8px !important;
        padding: 8px 24px !important;
    }
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

# --- DATABASE SETUP (SQLITE WITH MULTI-PLAYER SUPPORT) ---
def init_db():
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    topic TEXT,
                    diff TEXT,
                    score TEXT,
                    xp INTEGER,
                    date TEXT
                )''')
    c.execute("PRAGMA table_info(quiz_history)")
    cols = [info[1] for info in c.fetchall()]
    if "player_name" not in cols:
        c.execute("ALTER TABLE quiz_history ADD COLUMN player_name TEXT DEFAULT 'Player'")
    conn.commit()
    conn.close()

def save_quiz_record(player, topic, diff, score, xp):
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO quiz_history (player_name, topic, diff, score, xp, date) VALUES (?, ?, ?, ?, ?, ?)",
              (player, topic, diff, score, xp, datetime.now().strftime("%d %b, %H:%M")))
    conn.commit()
    conn.close()

def get_player_stats(player):
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute("SELECT topic, diff, score, xp, date FROM quiz_history WHERE player_name = ? ORDER BY id DESC LIMIT 5", (player,))
    history = c.fetchall()
    c.execute("SELECT SUM(xp) FROM quiz_history WHERE player_name = ?", (player,))
    total_xp = c.fetchone()[0] or 0
    total_xp = max(0, total_xp)

    c.execute("SELECT score FROM quiz_history WHERE player_name = ? ORDER BY id ASC", (player,))
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

def get_leaderboard():
    conn = sqlite3.connect("quiz_data.db")
    c = conn.cursor()
    c.execute("SELECT player_name, SUM(xp) as total_xp FROM quiz_history GROUP BY player_name ORDER BY total_xp DESC LIMIT 3")
    top_players = c.fetchall()
    conn.close()
    return top_players

def get_player_rank(xp):
    if xp < 50:
        return "🥉 Novice (Level 1)"
    elif xp < 150:
        return "🥈 Scholar (Level 2)"
    elif xp < 300:
        return "🥇 Master (Level 3)"
    else:
        return "👑 Grandmaster (Level 4)"

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

# --- SIDEBAR (SETTINGS & PERSONAL PLAYER PROFILE) ---
with st.sidebar:
    st.header("👤 Player Profile")
    
    player_name = st.text_input("Enter Your Name:", value="Moaz", help="Change name to create your unique profile!").strip()
    if not player_name:
        player_name = "Player"
        
    recent_history, total_xp, score_percentages = get_player_stats(player_name)
    
    st.markdown(f"""
    <div style="background-color: #f1f5f9; padding: 12px; border-radius: 8px; border: 1px solid #cbd5e1; margin-top: 10px;">
        <span style="color: #475569; font-size: 13px; font-weight: bold;">{player_name.upper()}'S TOTAL XP</span>
        <h2 style="color: #000000 !important; margin: 4px 0 0 0; font-size: 26px;">⭐ {total_xp} XP</h2>
    </div>
    """, unsafe_allow_html=True)
    st.write(f"**Rank:** {get_player_rank(total_xp)}")
    
    if len(score_percentages) >= 2:
        st.write("📈 **Score Progress (%)**")
        st.line_chart(score_percentages)

    leaders = get_leaderboard()
    if leaders and len(leaders) > 0:
        st.write("---")
        st.header("🏆 Top Players")
        for rank, (name, xp) in enumerate(leaders, 1):
            badge = "🥇" if rank == 1 else ("🥈" if rank == 2 else "🥉")
            st.caption(f"{badge} **{name}**: {xp or 0} XP")
            
    st.write("---")
    st.header("⚙️ Quiz Settings")
    
    topic = st.text_input("Topic:", placeholder="e.g. World History, Space, Cricket, AI...")
    
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
    st.header(f"📜 {player_name}'s Recent Quizzes")
    if recent_history:
        for item in recent_history:
            xp_sign = f"+{item[3]}" if item[3] >= 0 else f"{item[3]}"
            st.caption(f"**{item[0]}** ({item[1]}) • {item[4]}")
            st.text(f"Score: {item[2]} | {xp_sign} XP")
    else:
        st.caption("No quiz records yet for this profile.")

# --- MAIN UI ---
st.title("🤖 AI Quiz Pro")
st.caption(f"⚡ Welcome {player_name}! Test your knowledge • Compete on the Leaderboard • Watch out for Negative Marking!")

# --- HIGH SPEED 3.8 FLASH QUIZ GENERATOR FUNCTION ---
def generate_quiz_bulletproof(topic, diff, q_type, lang, num_q):
    prompt = f"""
    Return ONLY a valid JSON list of {num_q} questions.
    Topic: {topic}
    Difficulty: {diff}
    Question Type: {q_type}
    Language: {lang}. All text must be generated in {lang}.

    Rules:
    - If 'True / False', Options must be exactly 2 choices.
    - If 'MCQ', Options must contain 4 distinct choices.
    - "Answer" must strictly match one of the choices in "Options".
    - No markdown formatting, pure JSON list only.

    Format:
    [
      {{
        "Question": "Question text here",
        "Options": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "Answer": "Option 1",
        "Explanation": "Explanation text here"
      }}
    ]
    """
    
    # Priority on Gemini 3.8 Flash (your verified active model)
    models_to_try = [
        'models/gemini-3.8-flash',
        'models/gemini-3.7-flash',
        'models/gemini-3.6-flash',
        'gemini-1.5-flash'
    ]
    last_err = ""
    
    for m_name in models_to_try:
        try:
            model = genai.GenerativeModel(m_name)
            response = model.generate_content(prompt)
            if not response or not response.text:
                continue

            raw = response.text.strip()
            if "```" in raw:
                raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
                
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
                
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed, None
        except Exception as e:
            last_err = str(e)
            continue
            
    return None, last_err if last_err else "AI service is currently busy. Please try again in a few seconds."

# --- GENERATE QUIZ BUTTON ---
if st.button("Generate Quiz 🚀"):
    if not topic.strip():
        st.warning("⚠️ Please enter a quiz topic in the sidebar first!")
    else:
        st.session_state.quiz_data = None
        st.session_state.submitted = False
        st.session_state.saved_to_db = False
        st.session_state.end_time = None
        st.session_state.time_taken = 0
        st.session_state.tutor_explanations = {}
        
        with st.spinner(f"⚡ High-speed AI generating {diff} {q_type} quiz in {lang}..."):
            data, err = generate_quiz_bulletproof(topic, diff, q_type, lang, num_q)
            
            if data:
                st.session_state.quiz_data = data
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
            else:
                st.error(f"⚠️ {err}")

# --- DISPLAY QUIZ FORM ---
if st.session_state.quiz_data and not st.session_state.submitted:
    
    # Live JavaScript Countdown Timer
    if st.session_state.end_time:
        remaining_secs = int(st.session_state.end_time - time.time())
        if remaining_secs <= 0:
            st.error("⏰ Time has expired! Please submit your quiz below.")
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
                        alert("⏰ Time's up! Please submit your quiz.");
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
                st.warning("⚠️ Please select answers for all questions before submitting!")
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
            
            with st.expander(f"🤖 Need Help? Ask AI Tutor (Q{i+1})"):
                if i in st.session_state.tutor_explanations:
                    st.info(st.session_state.tutor_explanations[i])
                else:
                    if st.button(f"Deep Explanation & Code Example 💡", key=f"explain_btn_{i}"):
                        with st.spinner("AI Tutor is preparing explanation..."):
                            tutor_prompt = f"""
                            You are a friendly computer science teacher.
                            Question: {q['Question']}
                            User Choice: {user_answer}
                            Correct Answer: {q['Answer']}
                            
                            Explain why the user's choice was incorrect and teach the right concept simply. Provide a short code snippet.
                            Language: {st.session_state.get('current_lang', 'English')}
                            """
                            try:
                                tutor_model = genai.GenerativeModel('models/gemini-3.8-flash')
                                t_res = tutor_model.generate_content(tutor_prompt)
                                st.session_state.tutor_explanations[i] = t_res.text
                                st.rerun()
                            except Exception as e:
                                st.error(f"AI Tutor is busy: {e}")
        st.write("---")
        
    accuracy = (score / total) * 100
    wrong_count = total - score
    base_xp = score * 10
    penalty_xp = (wrong_count // 2) * 10
    net_xp = base_xp - penalty_xp

    if not st.session_state.saved_to_db:
        save_quiz_record(
            player_name,
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
        st.warning(f"⚠️ **Penalty Applied:** -{penalty_xp} XP deducted for {wrong_count} incorrect answers. Net XP: **{net_xp} XP**")
    else:
        st.success(f"🌟 **Well Done!** No penalties applied. Net XP: **+{net_xp} XP**")

    if score == total:
        st.balloons()
        st.success("🎉 Perfect Score! Outstanding Performance!")

    if st.button("Take Another Quiz 🔄"):
        st.session_state.quiz_data = None
        st.session_state.submitted = False
        st.session_state.end_time = None
        st.session_state.start_time = None
        st.session_state.time_taken = 0
        st.session_state.saved_to_db = False
        st.session_state.tutor_explanations = {}
        st.rerun()
