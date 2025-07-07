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
        st.warning("저장 실패")

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
    st.image("2000.png", width = 300, use_container_width=True)
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


    
    """)

	
	
    st.session_state.consent_given = st.checkbox("연구 참여에 동의합니다.")

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


def show_proposer(trial):
    st.markdown("<h3 style='font-size:1.4em;'>당신이 제안합니다</h3>", unsafe_allow_html=True)

    st.markdown("""
        <style>
        .stNumberInput input {
            font-size: 1.3em !important;
            padding: 1em !important;
            width: 130px !important;
        }
        .stButton button {
            margin: 0.3em;
            padding: 0.7em 1.5em;
            font-size: 1em;
            min-width: 130px;
        }
        </style>
    """, unsafe_allow_html=True)

    offer = st.number_input("상대에게 제시할 금액 (0~100,000원)", min_value=0, max_value=100000, step=5000, value=50000)

    if st.button("제안하기"):
        ai = trial["ai_type"]
        memory = st.session_state.ai_memory.setdefault(ai, [])
        prev_offer = memory[-1] if memory else None
        strategy = "첫 제안" if prev_offer is None else ("탐색" if abs(offer - prev_offer) >= 10000 else "활용")
        risk = "매우 낮음" if offer >= 50000 else "낮음" if offer >= 40000 else "중간" if offer >= 20000 else "높음"

        accept_prob = (
            1.0 if (ai == "무난이" and offer >= 40000) or (ai == "엄격이" and offer >= 50000)
            else 0.6 if ai == "무난이" and offer >= 20000
            else 0.5 if ai == "엄격이" and offer >= 30000
            else 0.2 if ai == "무난이"
            else 0.1
        )
        accepted = random.random() < accept_prob

        memory.append(offer)
        reward = offer if accepted else 0
        proposer_reward = total_amount - reward if accepted else 0

        st.session_state.result = f"상대가 {'수락' if accepted else '거절'}했습니다. 당신: {proposer_reward:,}원 / 상대: {reward:,}원"
        st.session_state.last_trial = {
            "trial": st.session_state.trial_index + 1,
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

        st.session_state.start_time = time.time()
        st.session_state.show_emotion = True


def show_responder(trial_data):
    offer = trial_data["offer"]
    frame_type = trial_data["frame_type"]

    # 스타일 반영
    st.markdown("""
        <style>
        .stButton button {
            margin: 0.3em;
            padding: 0.7em 1.5em;
            font-size: 1em;
            min-width: 130px;
        }
        </style>
    """, unsafe_allow_html=True)

    # 직접/간접 제안 메시지
    if frame_type == "direct":
        st.markdown(f"<p id='offerText' style='font-size:1.4em;'>상대가 당신에게 {offer:,}원을 제시했습니다.</p>", unsafe_allow_html=True)
    else:
        proposer_share = total_amount - offer
        st.markdown(f"<p id='offerText' style='font-size:1.4em;'>상대가 자신이 {proposer_share:,}원을 갖겠다고 제시했습니다.</p>", unsafe_allow_html=True)

    # 수락/거절 버튼
    col1, col2 = st.columns(2)
    if col1.button("수락"):
        handle_responder_response(trial_data, "accept")
    if col2.button("거절"):
        handle_responder_response(trial_data, "reject")


def handle_responder_response(trial_data, choice):
    accepted = choice == "accept"
    responder_reward = trial_data["offer"] if accepted else 0
    proposer_reward = total_amount - responder_reward if accepted else 0

    st.session_state.result = (
        f"거래가 성사되었습니다. 당신: {responder_reward:,}원 / 상대: {proposer_reward:,}원"
        if accepted else
        "거래가 결렬되었습니다. 둘 다 돈을 받지 못합니다."
    )

    st.session_state.last_trial = {
        "trial": st.session_state.trial_index + 1,
        "role": "responder",
        "offer": trial_data["offer"],
        "response": choice,
        "rt": round(time.time() - st.session_state.start_time, 2),
        "responder_reward": responder_reward,
        "proposer_reward": proposer_reward,
        "frame_type": trial_data["frame_type"]
    }

    st.session_state.show_emotion = True
    st.session_state.start_time = time.time()



def show_emotion_buttons():
    st.markdown("<p style='margin-top:1em;'>지금 기분은 어땠나요?</p>", unsafe_allow_html=True)

    st.markdown("""
        <style>
        .emotion-button button {
            font-size: 1em;
            padding: 0.7em 1.2em;
            margin: 0.2em;
            min-width: 150px;
        }
        </style>
    """, unsafe_allow_html=True)

    emotions = {
        "😊 기쁨": "기쁨",
        "😌 다행스러움": "다행스러움",
        "😐 무감정/잘 모르겠음": "무감정/잘 모르겠음",
        "☹️ 실망": "실망",
        "😠 화남": "화남"
    }

    for label, value in emotions.items():
        if st.button(label, key=value, help="클릭하여 감정 선택", use_container_width=True):
            st.session_state.last_trial["emotion"] = value
            st.session_state.results.append(st.session_state.last_trial)
            st.session_state.last_trial = {}
            st.session_state.trial_index += 1
            st.session_state.show_emotion = False



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



