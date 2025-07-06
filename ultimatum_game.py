import streamlit as st
import time
import random
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Ultimatum Game", layout="centered")

st.title("10만원 나눠 갖기")

# Constants
total_amount = 100000
num_trials = 30

# Google Sheets 연결 함수
def connect_to_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GSHEET_CREDENTIALS"]), scope)
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["GSHEET_NAME"]).sheet1
    return sheet

# 역할 생성 (proposer 12, responder 18)
def generate_trials():
    roles = ["proposer"] * 12 + ["responder"] * 18
    random.shuffle(roles)
    trials = []
    for role in roles:
        if role == "proposer":
            ai_type = random.choice(["무난이", "엄격이"])
            trials.append({"role": "proposer", "ai_type": ai_type})
        else:
            frame_type = random.choice(["direct", "indirect"])
            if frame_type == "direct":
                share = random.choice([10000, 20000, 30000, 40000, 50000])
                trials.append({"role": "responder", "frame_type": frame_type, "offer": share})
            else:
                proposer_pct = random.choice([60, 70, 80, 90])
                proposer_share = int(proposer_pct / 100 * total_amount)
                responder_share = total_amount - proposer_share
                trials.append({"role": "responder", "frame_type": frame_type, "offer": responder_share, "proposer_share": proposer_share})
    return trials

# 상태 초기화
if "trials" not in st.session_state:
    st.session_state.trials = generate_trials()
    st.session_state.trial_index = 0
    st.session_state.data = []
    st.session_state.ai_memory = {}
    st.session_state.start_time = time.time()

# 현재 시점의 trial 가져오기
if st.session_state.trial_index < len(st.session_state.trials):
    trial = st.session_state.trials[st.session_state.trial_index]
else:
    trial = None

# 제안자 화면
def show_proposer(trial):
    st.subheader("당신이 제안합니다")
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

        st.session_state.result = f"상대({ai})가 {'수락' if accepted else '거절'}했습니다. 당신: {proposer_reward:,}원 / 상대: {reward:,}원"
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

# 응답자 화면
def show_responder(trial):
    st.subheader("상대의 제안")
    if trial["frame_type"] == "direct":
        st.write(f"상대가 당신에게 **{trial['offer']:,}원**을 제시했습니다.")
    else:
        st.write(f"상대가 자신이 **{trial['proposer_share']:,}원**을 갖겠다고 제시했습니다.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("수락"):
            proposer_reward = total_amount - trial["offer"]
            st.session_state.result = f"거래가 성사되었습니다. 당신: {trial['offer']:,}원 / 상대: {proposer_reward:,}원"
            st.session_state.last_trial = {
                "trial": st.session_state.trial_index + 1,
                "role": "responder",
                "offer": trial["offer"],
                "response": "accept",
                "responder_reward": trial["offer"],
                "proposer_reward": proposer_reward,
                "frame_type": trial["frame_type"],
                "rt": round(time.time() - st.session_state.start_time, 2)
            }
            st.session_state.start_time = time.time()
            st.session_state.show_emotion = True
    with col2:
        if st.button("거절"):
            st.session_state.result = "거래가 결렬되었습니다. 둘 다 돈을 받지 못합니다."
            st.session_state.last_trial = {
                "trial": st.session_state.trial_index + 1,
                "role": "responder",
                "offer": trial["offer"],
                "response": "reject",
                "responder_reward": 0,
                "proposer_reward": 0,
                "frame_type": trial["frame_type"],
                "rt": round(time.time() - st.session_state.start_time, 2)
            }
            st.session_state.start_time = time.time()
            st.session_state.show_emotion = True

# 감정 선택 화면
def show_emotion():
    st.markdown(f"### 결과: {st.session_state.result}")
    st.write("지금 기분은 어땠나요?")
    emotions = ["😊 기쁨", "😌 다행스러움", "😐 무감정/잘 모르겠음", "☹️ 실망", "😠 화남"]
    for emo in emotions:
        if st.button(emo):
            st.session_state.last_trial["emotion"] = emo
            st.session_state.data.append(st.session_state.last_trial)
            st.session_state.last_trial = {}
            st.session_state.trial_index += 1
            st.session_state.show_emotion = False

            # Google Sheet 저장
            try:
                sheet = connect_to_gsheet()
                sheet.append_row([str(v) for v in st.session_state.data[-1].values()])
            except:
                st.warning("⚠️ Google Sheet에 저장하지 못했습니다. secrets 설정을 확인하세요.")

# 메인 실행 흐름
if trial:
    if st.session_state.get("show_emotion"):
        show_emotion()
    elif trial["role"] == "proposer":
        show_proposer(trial)
    else:
        show_responder(trial)
else:
    st.success("🎉 모든 라운드가 끝났습니다. 참여해 주셔서 감사합니다!")
    st.download_button("결과 다운로드 (JSON)", json.dumps(st.session_state.data, indent=2), file_name="ultimatum_results.json")
