# Streamlit Ultimatum Game with framing, AI responders, and emotion tagging
import streamlit as st
import json
import random
import time
from oauth2client.service_account import ServiceAccountCredentials
import gspread

# --- CONFIGURATION ---
st.set_page_config(page_title="Ultimatum Game", layout="centered")
st.title("10만원 나눠 갖기 실험")

# --- Google Sheets 연결 ---
@st.cache_resource
def get_gsheet():
    creds_dict = json.loads(st.secrets["GSHEET_CREDENTIALS"])
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["GSHEET_NAME"]).sheet1
    return sheet

def save_to_sheets(entries):
    sheet = get_gsheet()
    for e in entries:
        row = [
            e.get("trial"), e.get("role"), e.get("offer"),
            e.get("accepted", e.get("response")),
            e.get("emotion"), e.get("proposer_reward"),
            e.get("responder_reward"), e.get("rt"),
            e.get("aiType", ""), e.get("frameType", ""),
            e.get("riskAversion", ""), e.get("strategy", "")
        ]
        sheet.append_row(row)

# --- 초기 상태 설정 ---
total = 100000
if 'current' not in st.session_state:
    st.session_state.data = []
    st.session_state.rounds = []
    st.session_state.current = 0
    st.session_state.step = 'intro'
    st.session_state.ai_memory = {}

# --- 실험 라운드 구성 ---
if not st.session_state.rounds:
    roles = ['proposer'] * 12 + ['responder'] * 18
    random.shuffle(roles)
    for r in roles:
        if r == 'proposer':
            st.session_state.rounds.append({"role": "proposer", "aiType": random.choice(['무난이','엄격이'])})
        else:
            frame = random.choice(['direct', 'indirect'])
            if frame == 'direct':
                share = random.choice([10000, 20000, 30000, 40000, 50000])
                st.session_state.rounds.append({"role": "responder", "frameType": frame, "type": "direct", "share": share})
            else:
                pct = random.choice([60, 70, 80, 90])
                st.session_state.rounds.append({"role": "responder", "frameType": frame, "type": "indirect", "proposerPct": pct})

# --- 함수 정의 ---
def show_intro():
    st.image("2000.png", width=300)
    st.markdown("""
    당신은 총 30회의 거래를 진행하며, 각 거래에서 10만원을 나눠 갖습니다.\
    제안자는 금액을 제시하고, 상대는 수락하거나 거절할 수 있습니다.\
    제안이 거절되면 둘 다 돈을 받지 못합니다.
    """)
    if st.button("시작하기"):
        st.session_state.step = 'trial'

def show_proposer(round):
    st.subheader("제안자 역할")
    offer = st.number_input("상대에게 제안할 금액", min_value=0, max_value=total, step=5000, value=50000)
    if st.button("제안하기"):
        ai = round["aiType"]
        if ai not in st.session_state.ai_memory:
            st.session_state.ai_memory[ai] = []
        st.session_state.ai_memory[ai].append(offer)

        prev = st.session_state.ai_memory[ai][-2] if len(st.session_state.ai_memory[ai]) > 1 else None
        strategy = "첫 제안"
        if prev is not None:
            strategy = "탐색" if abs(offer - prev) >= 10000 else "활용"

        risk = "매우 낮음" if offer >= 50000 else "낮음" if offer >= 40000 else "중간" if offer >= 20000 else "높음"
        accept_prob = 1 if offer >= 50000 else 0.6 if offer >= 30000 else 0.1 if ai == '엄격이' else (1 if offer >= 40000 else 0.6 if offer >= 20000 else 0.2)
        accepted = random.random() < accept_prob

        result = {
            "trial": st.session_state.current + 1,
            "role": "proposer",
            "offer": offer,
            "aiType": ai,
            "accepted": accepted,
            "proposer_reward": total - offer if accepted else 0,
            "responder_reward": offer if accepted else 0,
            "rt": round(time.time() - st.session_state.start_time, 2),
            "strategy": strategy,
            "riskAversion": risk
        }
        st.session_state.last_result = result
        st.session_state.step = 'emotion'

def show_responder(round):
    st.subheader("응답자 역할")
    if round['type'] == 'direct':
        offer = round['share']
        st.markdown(f"상대가 당신에게 **{offer:,}원**을 제시했습니다.")
    else:
        proposer_share = round['proposerPct'] * total // 100
        offer = total - proposer_share
        st.markdown(f"상대가 자신이 **{proposer_share:,}원**을 갖겠다고 제시했습니다.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("수락"):
            accepted = True
    with col2:
        if st.button("거절"):
            accepted = False

    if 'accepted' in locals():
        result = {
            "trial": st.session_state.current + 1,
            "role": "responder",
            "offer": offer,
            "response": 'accept' if accepted else 'reject',
            "responder_reward": offer if accepted else 0,
            "proposer_reward": total - offer if accepted else 0,
            "rt": round(time.time() - st.session_state.start_time, 2),
            "frameType": round['frameType']
        }
        st.session_state.last_result = result
        st.session_state.step = 'emotion'

def show_emotion():
    result = st.session_state.last_result
    accepted = result.get("accepted", result.get("response") == 'accept')
    if accepted:
        st.success(f"거래 성사! 당신: {result['responder_reward']:,}원 / 상대: {result['proposer_reward']:,}원")
    else:
        st.error("거래 결렬. 아무도 돈을 받지 못했습니다.")
    st.write("지금 기분은 어땠나요?")
    emotion = st.radio("감정 선택", ["😊 기쁨", "😌 다행스러움", "😐 무감정/잘 모르겠음", "☹️ 실망", "😠 화남"])
    if st.button("다음 라운드"):
        st.session_state.last_result["emotion"] = emotion
        st.session_state.data.append(st.session_state.last_result)
        st.session_state.current += 1
        if st.session_state.current >= len(st.session_state.rounds):
            st.session_state.step = 'end'
        else:
            st.session_state.step = 'trial'

def show_end():
    st.success("실험이 완료되었습니다. 감사합니다!")
    if st.button("Google Sheet에 저장 및 다운로드"):
        save_to_sheets(st.session_state.data)
        json_str = json.dumps(st.session_state.data, indent=2, ensure_ascii=False)
        st.download_button("결과 다운로드", json_str, file_name="ultimatum_game_framing_results.json")

# --- 메인 루프 ---
if st.session_state.step == 'intro':
    show_intro()
elif st.session_state.step == 'trial':
    st.session_state.start_time = time.time()
    round = st.session_state.rounds[st.session_state.current]
    if round['role'] == 'proposer':
        show_proposer(round)
    else:
        show_responder(round)
elif st.session_state.step == 'emotion':
    show_emotion()
elif st.session_state.step == 'end':
    show_end()
