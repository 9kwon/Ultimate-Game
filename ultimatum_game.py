import streamlit as st
import time
from datetime import datetime
import random
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------- Custom Style ------------
st.markdown("""
    <style>
    body { font-family: Arial; padding: 2em; max-width: 1000px; margin: auto; font-size: 1.25em; line-height: 1.8; }
    .hidden { display: none; }
    button {
      margin: 0.3em;
      padding: 0.7em 1.5em;
      font-size: 1em;
      min-width: 130px;
    }
    #offerText { font-size: 1.4em; }
    #result { margin-top: 2em; font-weight: bold; font-size: 1.3em; }
    input[type=number] {
      width: 120px;
      font-size: 1.3em;
      padding: 1em;
    }
    </style>
""", unsafe_allow_html=True)

# ----------- Google Sheets Setup ------------
def save_to_gsheet(data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(st.secrets["GSHEET_CREDENTIALS"]), scope
        )
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["GSHEET_NAME"]).sheet1
        sheet.append_row(list(data.values()))
    except Exception as e:
        st.warning("⚠️ Google Sheet에 저장하지 못했습니다. secrets 설정을 확인하세요.")

# ----------- Game Initialization ------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.page = "intro"
    st.session_state.trial_num = 0
    st.session_state.data = []
    st.session_state.consent_given = False
    st.session_state.user_id = ""
    st.session_state.start_time = None
    st.session_state.roles = random.sample(
        ["proposer"] * 12 + ["responder"] * 18, 30
    )
    st.session_state.rounds = []
    for role in st.session_state.roles:
        if role == "proposer":
            st.session_state.rounds.append({"role": role, "ai": random.choice(["무난이", "엄격이"]), "type": "proposer"})
        else:
            frame = random.choice(["direct", "indirect"])
            if frame == "direct":
                offer = random.choice([10000, 20000, 30000, 40000, 50000])
                st.session_state.rounds.append({"role": role, "offer": offer, "frame": frame, "type": "responder"})
            else:
                proposer_pct = random.choice([60, 70, 80, 90])
                offer = 100000 - int((proposer_pct / 100) * 100000)
                st.session_state.rounds.append({"role": role, "offer": offer, "frame": frame, "type": "responder"})

# ----------- Pages ------------
def show_intro():
    st.title("10만원 나눠 갖기 게임")
    st.image("2000.png", use_column_width=True)
    st.markdown("""
    이 게임은 총 30회의 협상을 포함합니다. 매 거래마다 당신은 처음 보는 사람과 10만원을 나눠 가져야 합니다. 
    당신은 제안자 또는 응답자가 될 수 있습니다.
    """)
    st.session_state.consent_given = st.checkbox("🔒 연구 참여에 동의합니다.")

    name = st.text_input("이름을 입력하세요")
    phone = st.text_input("전화번호 뒤 4자리를 입력하세요", max_chars=4)

    if st.button("게임 시작"):
        if not st.session_state.consent_given:
            st.warning("계속하려면 동의가 필요합니다.")
        elif not name or not phone:
            st.warning("이름과 전화번호 뒤 4자리를 모두 입력하세요.")
        else:
            st.session_state.user_id = f"{name}_{phone}"
            st.session_state.page = "game"
            st.experimental_rerun()

def show_proposer():
    round = st.session_state.rounds[st.session_state.trial_num]
    st.write(f"### 제안자 역할 - 라운드 {st.session_state.trial_num + 1}/30")
    offer = st.slider("상대에게 제안할 금액 (원)", 0, 100000, 50000, 5000)
    if st.button("제안하기"):
        ai = round["ai"]
        accepted = False
        if ai == "무난이":
            accepted = offer >= 20000
        elif ai == "엄격이":
            accepted = offer >= 50000
        user_reward = 100000 - offer if accepted else 0
        ai_reward = offer if accepted else 0
        st.session_state.page = "emotion"
        st.session_state.last_result = {
            "trial": st.session_state.trial_num + 1,
            "role": "proposer",
            "offer": offer,
            "accepted": accepted,
            "user_reward": user_reward,
            "ai_reward": ai_reward,
            "ai": ai,
            "rt": round(time.time() - st.session_state.start_time, 2),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": st.session_state.user_id
        }
        st.experimental_rerun()

def show_responder():
    round = st.session_state.rounds[st.session_state.trial_num]
    st.write(f"### 응답자 역할 - 라운드 {st.session_state.trial_num + 1}/30")
    if round["frame"] == "direct":
        st.markdown(f"상대가 당신에게 **{round['offer']:,}원**을 제안했습니다.")
    else:
        proposer_share = 100000 - round["offer"]
        st.markdown(f"상대가 자신이 **{proposer_share:,}원**을 갖겠다고 제안했습니다.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("수락"):
            accepted = True
    with col2:
        if st.button("거절"):
            accepted = False
    if "accepted" in locals():
        user_reward = round["offer"] if accepted else 0
        proposer_reward = 100000 - round["offer"] if accepted else 0
        st.session_state.page = "emotion"
        st.session_state.last_result = {
            "trial": st.session_state.trial_num + 1,
            "role": "responder",
            "offer": round["offer"],
            "accepted": accepted,
            "user_reward": user_reward,
            "proposer_reward": proposer_reward,
            "frame": round["frame"],
            "rt": round(time.time() - st.session_state.start_time, 2),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": st.session_state.user_id
        }
        st.experimental_rerun()

def show_emotion():
    st.write("#### 지금 기분은 어땠나요?")
    emotions = ["😊 기쁨", "😌 다행스러움", "😐 무감정/잘 모르겠음", "☹️ 실망", "😠 화남"]
    for emo in emotions:
        if st.button(emo):
            result = st.session_state.last_result
            result["emotion"] = emo
            st.session_state.data.append(result)
            save_to_gsheet(result)
            st.session_state.trial_num += 1
            if st.session_state.trial_num >= len(st.session_state.rounds):
                st.session_state.page = "done"
            else:
                st.session_state.page = "game"
                st.session_state.start_time = time.time()
            st.experimental_rerun()

def show_done():
    st.success("모든 라운드가 종료되었습니다. 참여해 주셔서 감사합니다!")
    st.write(f"총 참여 trial 수: {len(st.session_state.data)}")
    st.download_button("내 결과 다운로드 (JSON)", json.dumps(st.session_state.data, indent=2), file_name="ultimatum_results.json")

# ----------- Main Renderer ------------
if st.session_state.page == "intro":
    show_intro()

elif st.session_state.page == "game":
    trial = st.session_state.rounds[st.session_state.trial_num]
    st.session_state.start_time = time.time()
    if trial["role"] == "proposer":
        show_proposer()
    else:
        show_responder()

elif st.session_state.page == "emotion":
    show_emotion()

elif st.session_state.page == "done":
    show_done()
