import streamlit as st
import time
from datetime import datetime
import random
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# ----------- Custom Style ------------
st.markdown("""
    <style>
    body { font-family: Arial; padding: 2em; max-width: 1000px; margin: auto; font-size: 1.25em; line-height: 1.8; }
    .hidden { display: none; }
    button {
      margin: 0.3em;
      padding: 0.7em 1.5em;
      font-size: 1em;
      min-width: 160px;
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
def save_to_gsheet(data, sheet_name="raw"):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials_dict = json.loads(st.secrets["GSHEET_CREDENTIALS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        book = client.open(st.secrets["GSHEET_NAME"])

        # 열 이름 추출
        header = list(data.keys())
        row = list(data.values())

        # 시트 열기 또는 생성
        try:
            sheet = book.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            sheet = book.add_worksheet(title=sheet_name, rows="1000", cols="50")
            sheet.append_row(header)

        # 헤더 확인 및 추가
        if not sheet.row_values(1):
            sheet.append_row(header)
        elif sheet.row_values(1) != header:
            # 컬럼이 다르면 기존 시트는 두고 새 시트를 만드는게 안전
            sheet = book.add_worksheet(title=f"{sheet_name}_{datetime.now().strftime('%H%M%S')}", rows="1000", cols="50")
            sheet.append_row(header)

        sheet.append_row(row)

    except Exception as e:
        st.warning(f"저장 실패: {e}")


# ----------- Behavior Analysis ------------
def compute_behavioral_traits(trials_df):
    proposer_offers = trials_df[trials_df['role'] == 'proposer']['offer']
    responder_trials = trials_df[trials_df['role'] == 'responder']

    traits = {}
    traits['exploit_ratio'] = (proposer_offers < 20000).mean()
    traits['explore_std'] = proposer_offers.std()
    traits['risk_averse_ratio'] = (proposer_offers >= 50000).mean()

    low_offers = responder_trials[responder_trials['offer'] <= 20000]
    traits['punishment_rate'] = (low_offers['response'] == 'reject').mean() if not low_offers.empty else None

    mid_offers = responder_trials[(responder_trials['offer'] > 20000) & (responder_trials['offer'] < 50000)]
    traits['loss_aversion'] = (mid_offers['response'] == 'reject').mean() if not mid_offers.empty else None

    high_offers = responder_trials[responder_trials['offer'] >= 50000]
    traits['ignore_benefit'] = (high_offers['response'] == 'reject').mean() if not high_offers.empty else None

    return traits

# ----------- Game Initialization ------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.page = "intro"
    st.session_state.trial_num = 0
    st.session_state.data = []
    st.session_state.consent_given = False
    st.session_state.user_id = ""
    st.session_state.start_time = None
    st.session_state.roles = random.sample(["proposer"] * 14 + ["responder"] * 16, 30)
    st.session_state.rounds = []
    for role in st.session_state.roles:
        if role == "proposer":
            st.session_state.rounds.append({"role": role, "ai": random.choice(["무난이", "엄격이"]), "type": "proposer"})
        else:
            frame = random.choice(["direct", "indirect"])
            if frame == "direct":
                offer = random.choice([10000, 20000, 30000, 40000, 50000])
            else:
                proposer_pct = random.choice([60, 70, 80, 90])
                offer = 100000 - int((proposer_pct / 100) * 100000)
            st.session_state.rounds.append({"role": role, "offer": offer, "frame": frame, "type": "responder"})

# ----------- Pages ------------
def show_intro():
    st.title("10만원 나눠 갖기")
    col1, col2 = st.columns([2, 1])
    with col2:
        st.image("2000.png", width=250)
    with col1:
        st.markdown("""
        당신은 협상 거래 테이블에 앉아 총 30회의 협상을 진행하게 됩니다.

        매 거래마다 당신은 처음 보는 사람과 10만원을 나눠 가져야 하는데, 조건이 있습니다.  
        한 사람은 비율을 제시하고, 다른 사람이 반드시 수락해야 계약이 성사된다는 것입니다.

        즉, 상대가 당신에게 10만원 중 8만원을 갖고 2만원을 제안했을 때,  
        당신이 수락하면 계약은 성사되어 당신은 2만원, 상대는 8만원을 가집니다.  
        하지만 2만원이 너무 적다고 생각하여 거절한다면, 둘 다 돈을 받지 못합니다.

        당신은 제안자가 되어 비율이나 금액을 제시할 수도 있고,  
        응답자가 되어 수락할지 거절할지 선택할 수 있습니다.

        **당신은 어떤 선택을 하시겠습니까?**
        &nbsp;
        """, unsafe_allow_html=True)

    st.session_state.consent_given = st.checkbox("연구 참여에 동의합니다.")
    name = st.text_input("이름을 입력하세요")
    phone = st.text_input("전화번호 뒤 4자리를 입력하세요", max_chars=4)

    if st.button("시작하기"):
        if not st.session_state.consent_given:
            st.warning("계속하려면 동의가 필요합니다.")
        elif not name or not phone:
            st.warning("이름과 전화번호 뒤 4자리를 모두 입력하세요.")
        else:
            st.session_state.user_id = f"{name}_{phone}"
            st.session_state.page = "game"
            st.rerun()

def show_proposer():
    rounds = st.session_state.rounds[st.session_state.trial_num]
    st.write(f"### 당신은 상대에게 얼마를 제시하시겠습니까?  ({st.session_state.trial_num + 1}/30)")
    offer = st.slider("상대에게 제시할 금액 (원)", 0, 100000, 50000, 5000)
    if st.button("제시하기"):
        ai = rounds["ai"]
        accepted = offer >= 20000 if ai == "무난이" else offer >= 50000
        user_reward = 100000 - offer if accepted else 0
        ai_reward = offer if accepted else 0
        st.session_state.result = f"거래가 성사되었습니다. <br>당신: {user_reward:,}원 / 상대: {ai_reward:,}원" if accepted else "거래가 결렬되었습니다. 둘 다 돈을 받지 못합니다."
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
        st.rerun()

def handle_responder_response(trial_data, choice):
    accepted = choice == "accept"
    responder_reward = trial_data["offer"] if accepted else 0
    proposer_reward = 100000 - responder_reward if accepted else 0
    st.session_state.result = f"거래가 성사되었습니다. <br>당신: {responder_reward:,}원 / 상대: {proposer_reward:,}원" if accepted else "거래가 결렬되었습니다. 둘 다 돈을 받지 못합니다."
    st.session_state.last_result = {
        "trial": st.session_state.trial_num + 1,
        "role": "responder",
        "offer": trial_data["offer"],
        "response": choice,
        "rt": round(time.time() - st.session_state.start_time, 2),
        "responder_reward": responder_reward,
        "proposer_reward": proposer_reward,
        "frame": trial_data["frame"],
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": st.session_state.user_id
    }
    st.session_state.page = "emotion"
    st.session_state.start_time = time.time()
    st.rerun()

def show_responder():
    rounds = st.session_state.rounds[st.session_state.trial_num]
    st.write(f"### 상대의 제안에 응답해 주세요  ({st.session_state.trial_num + 1}/30)")
    if rounds["frame"] == "direct":
        st.markdown(f"상대가 당신에게 **{rounds['offer']:,}원**을 제안했습니다.")
    else:
        proposer_share = 100000 - rounds["offer"]
        st.markdown(f"상대가 자신이 **{proposer_share:,}원**을 갖겠다고 제안했습니다.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("수락"):
            handle_responder_response(rounds, "accept")
    with col2:
        if st.button("거절"):
            handle_responder_response(rounds, "reject")

def show_result():
    st.write("### 거래 결과")
    st.markdown(f"<div id='result'>{st.session_state.result}</div><br><br>", unsafe_allow_html=True)

def show_emotion():
    show_result()
    st.write("#### 지금 기분은 어떤가요?")
    emotions = ["😊 기쁨", "😌 다행스러움", "😐 무감정/잘 모르겠음", "☹️ 실망", "😠 화남"]
    for emo in emotions:
        if st.button(emo):
            result = st.session_state.last_result
            result["emotion"] = emo
            save_to_gsheet(result, sheet_name="raw")
            
            st.session_state.data.append(result)
            st.session_state.trial_num += 1
            if st.session_state.trial_num >= len(st.session_state.rounds):
                st.session_state.page = "done"
            else:
                st.session_state.page = "game"
                st.session_state.start_time = time.time()
            st.rerun()

def show_done():
    st.success("모든 라운드가 종료되었습니다. 참여해 주셔서 감사합니다!")
    st.write(f"총 참여 trial 수: {len(st.session_state.data)}")
    df = pd.DataFrame(st.session_state.data)
    traits = compute_behavioral_traits(df)
    traits["user_id"] = st.session_state.user_id
    traits["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_gsheet(traits, sheet_name="traits")

    col_name_map = {
        "risk_averse_ratio": "위험 회피 경향",
        "loss_aversion": "손실 회피 경향",
        "punishment_rate": "처벌 성향",
        "ignore_benefit": "이익 무관심",
        "explore": "탐색 성향",
        "exploit": "이용 성향",
        "user_id": "참여자 ID",
        "date": "날짜 및 시간"
    }
    translated = [{"항목": col_name_map.get(k, k), "값(0~1)": v} for k, v in traits.items()]
    traits_df = pd.DataFrame(translated)

    st.subheader("행동 특성 분석 결과")
    st.dataframe(traits_df, use_container_width=True)
    #st.json(traits)

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
