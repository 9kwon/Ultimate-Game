import streamlit as st
import time
import random
from datetime import datetime
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------- Google Sheet Setup ----------
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GSHEET_NAME = st.secrets["GSHEET_NAME"]
GSHEET_CREDENTIALS = st.secrets["GSHEET_CREDENTIALS"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(GSHEET_CREDENTIALS, SCOPE)
client = gspread.authorize(credentials)
sheet = client.open(GSHEET_NAME).sheet1

# ---------- Session State Init ----------
if "page" not in st.session_state:
    st.session_state.page = "intro"
    st.session_state.trial_num = 0
    st.session_state.data = []
    st.session_state.ai_memory = {}
    st.session_state.user_id = ""
    st.session_state.start_time = 0
    st.session_state.show_emotion = False
    st.session_state.result = ""

# ---------- Constants ----------
total_amount = 100000
roles = ["proposer"] * 14 + ["responder"] * 16
random.shuffle(roles)

def generate_rounds():
    rounds = []
    for role in roles:
        if role == "proposer":
            rounds.append({"role": role, "ai_type": random.choice(["무난이", "엄격이"])}).
        else:
            frame_type = random.choice(["direct", "indirect"])
            if frame_type == "direct":
                share = random.choice([10000, 20000, 30000, 40000, 50000])
                rounds.append({"role": role, "frame_type": frame_type, "offer": share})
            else:
                proposer_pct = random.choice([60, 70, 80, 90])
                responder_share = total_amount - int(total_amount * proposer_pct / 100)
                rounds.append({"role": role, "frame_type": frame_type, "offer": responder_share})
    return rounds

if "rounds" not in st.session_state:
    st.session_state.rounds = generate_rounds()

# ---------- UI: Intro ----------
def show_intro():
    st.image("2000.png", use_container_width=False, width=300)
    st.markdown("""
    <style>
        .stNumberInput input {font-size: 1.3em !important; padding: 0.8em; width: 120px;}
        button[kind="primary"] {font-size: 1.1em; padding: 0.7em 1.5em;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    당신은 협상 거래 테이블에 앉아 총 30회의 협상을 진행하게 됩니다.  
    매 거래마다 당신은 처음 보는 사람과 10만원을 나눠 가져야 하는데, 조건이 있습니다.  
    한 사람은 비율을 제시하고, 다른 사람이 반드시 수락해야 계약이 성사된다는 것입니다.  

    즉, 상대가 당신에게 10만원 중 8만원을 갖고 2만원을 제시했을 때,  
    당신이 수락하면 계약은 성사되어 당신은 2만원, 상대는 8만원을 가집니다.  
    하지만 2만원이 너무 적다고 생각하여 거절한다면, 둘 다 돈을 받지 못합니다.  

    당신은 제안자가 되어 비율이나 금액을 제시할 수도 있고,  
    응답자가 되어 수락할지 거절할지 선택할 수 있습니다.  

    **당신은 어떤 선택을 하시겠습니까?**

    &nbsp;  
    &nbsp;  
    """, unsafe_allow_html=True)

    with st.form("consent_form"):
        name = st.text_input("이름")
        phone = st.text_input("전화번호 (뒤 4자리 포함)")
        agree = st.checkbox("연구 참여에 동의합니다.")
        submitted = st.form_submit_button("시작하기")

        if submitted:
            if not name or not phone or not agree:
                st.warning("모든 항목을 입력하고 동의해 주세요.")
            else:
                st.session_state.user_id = f"{name}_{phone[-4:]}"
                st.session_state.page = "game"
                st.rerun()

# ---------- UI: Proposer ----------
def show_proposer(trial):
    st.markdown("<h3 style='font-size:1.4em;'>당신이 제안합니다</h3>", unsafe_allow_html=True)
    offer = st.number_input("상대에게 제시할 금액 (0~100,000원)", min_value=0, max_value=100000, step=5000, value=50000)

    if st.button("제안하기"):
        ai = trial["ai_type"]
        memory = st.session_state.ai_memory.setdefault(ai, [])
        prev_offer = memory[-1] if memory else None
        strategy = "첫 제안" if prev_offer is None else ("탐색" if abs(offer - prev_offer) >= 10000 else "활용")
        risk = "매우 낮음" if offer >= 50000 else "낮음" if offer >= 40000 else "중간" if offer >= 20000 else "높음"

        accept_prob = 1.0 if (ai == "무난이" and offer >= 40000) or (ai == "엄격이" and offer >= 50000) \
            else 0.6 if ai == "무난이" and offer >= 20000 else 0.5 if ai == "엄격이" and offer >= 30000 else 0.2 if ai == "무난이" else 0.1

        accepted = random.random() < accept_prob

        memory.append(offer)
        reward = offer if accepted else 0
        proposer_reward = total_amount - reward if accepted else 0

        st.session_state.result = f"상대가 {'수락' if accepted else '거절'}했습니다. 당신: {proposer_reward:,}원 / 상대: {reward:,}원"
        st.session_state.last_trial = {
            "user_id": st.session_state.user_id,
            "trial": st.session_state.trial_num + 1,
            "role": "proposer",
            "offer": offer,
            "ai_type": ai,
            "accepted": accepted,
            "responder_reward": reward,
            "proposer_reward": proposer_reward,
            "rt": round(time.time() - st.session_state.start_time, 2),
            "strategy": strategy,
            "risk_aversion": risk
        }
        st.session_state.page = "emotion"
        st.rerun()

# ---------- UI: Responder ----------
def show_responder(trial):
    offer = trial["offer"]
    frame = trial["frame_type"]
    st.markdown("<h3 style='font-size:1.4em;'>상대의 제안</h3>", unsafe_allow_html=True)

    if frame == "direct":
        st.write(f"상대가 당신에게 {offer:,}원을 제시했습니다.")
    else:
        proposer_share = total_amount - offer
        st.write(f"상대가 자신이 {proposer_share:,}원을 갖겠다고 제시했습니다.")

    col1, col2 = st.columns(2)
    accept_clicked = col1.button("수락")
    reject_clicked = col2.button("거절")

    if accept_clicked or reject_clicked:
        choice = "accept" if accept_clicked else "reject"
        accepted = choice == "accept"
        responder_reward = offer if accepted else 0
        proposer_reward = total_amount - offer if accepted else 0

        st.session_state.result = "거래가 성사되었습니다." if accepted else "거래가 결렬되었습니다."
        st.session_state.last_trial = {
            "user_id": st.session_state.user_id,
            "trial": st.session_state.trial_num + 1,
            "role": "responder",
            "offer": offer,
            "response": choice,
            "responder_reward": responder_reward,
            "proposer_reward": proposer_reward,
            "rt": round(time.time() - st.session_state.start_time, 2),
            "frame_type": frame
        }
        st.session_state.page = "emotion"
        st.rerun()

# ---------- UI: Emotion ----------
def show_emotion():
    st.markdown(f"**{st.session_state.result}**")
    st.write("지금 기분은 어땠나요?")
    emotions = ["😊 기쁨", "😌 다행스러움", "😐 무감정/잘 모르겠음", "☹️ 실망", "😠 화남"]
    for emo in emotions:
        if st.button(emo):
            st.session_state.last_trial["emotion"] = emo
            st.session_state.data.append(st.session_state.last_trial)
            st.session_state.trial_num += 1
            if st.session_state.trial_num >= len(st.session_state.rounds):
                st.session_state.page = "end"
            else:
                st.session_state.page = "game"
            st.rerun()

# ---------- UI: End ----------
def show_end():
    st.markdown("### 참여해 주셔서 감사합니다!")
    try:
        df = pd.DataFrame(st.session_state.data)
        sheet.append_rows(df.values.tolist())
    except Exception as e:
        st.warning("⚠️ Google Sheet에 저장하지 못했습니다. secrets 설정을 확인하세요.")
        st.exception(e)
    st.dataframe(st.session_state.data)

# ---------- Main Renderer ----------
if st.session_state.page == "intro":
    show_intro()
elif st.session_state.page == "game":
    trial = st.session_state.rounds[st.session_state.trial_num]
    st.session_state.start_time = time.time()
    if trial["role"] == "proposer":
        show_proposer(trial)
    else:
        show_responder(trial)
elif st.session_state.page == "emotion":
    show_emotion()
elif st.session_state.page == "end":
    show_end()
