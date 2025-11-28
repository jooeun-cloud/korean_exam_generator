import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import re 
import os

# ==========================================
# [설정] API 키 연동 (Streamlit Cloud Secrets 권장)
# ==========================================
# Streamlit Cloud 배포 시 st.secrets에서 키를 가져옵니다.
try:
    # 1. Streamlit Secrets에 GOOGLE_API_KEY = "발급받은 실제 API 키" 설정
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
    # Secrets 설정이 안 되어 있을 경우 (로컬 테스트용)
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY_FOR_LOCAL_TEST") 

st.set_page_config(page_title="사계국어 AI 모의고사 제작 시스템", page_icon="📚", layout="wide")

# ==========================================
# [공통 HTML/CSS 정의]
# ==========================================

HTML_HEAD = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <style>
        /* 기본 폰트 및 페이지 설정 */
        body { 
            font-family: 'HanyangShinMyeongjo', 'Batang', 'Times New Roman', serif; 
            padding: 40px; 
            max-width: 850px; 
            margin: 0 auto; 
            line-height: 1.6; 
            color: #000; 
            font-size: 10.5pt;
        }
        
        h1 { text-align: center; margin-bottom: 5px; font-size: 28px; letter-spacing: -1px; }
        h2 { text-align: center; margin-top: 0; margin-bottom: 30px; font-size: 16px; color: #333; }
        
        /* [비문학] 시간 박스 */
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 30px;
            padding: 10px 20px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fdfdfd; font-size: 0.95em;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        .time-blank {
            display: inline-block;
            width: 60px;
            border-bottom: 1px solid #000;
            margin: 0 5px;
            height: 1em;
            vertical-align: middle;
        }
        
        /* [비문학] 유형 구분 헤딩 (h3) */
        h3 { 
            margin-top: 5px; 
            margin-bottom: 15px; 
            font-size: 1.6em; 
            color: #2e8b57; 
            border-bottom: 2px solid #2e8b57;
            padding-bottom: 10px;
            font-weight: bold;
        }
        
        /* [문학] 유형 구분 헤딩 (h4) */
        h4 {
            margin-top: 5px; 
            margin-bottom: 10px; 
            font-size: 1.8em; 
            color: #00008b; 
            border-bottom: 3px solid #00008b; 
            padding-bottom: 8px; 
            font-weight: bold; 
        }

        /* [비문학/문학 통합] 유형 콘텐츠 전체를 감싸는 박스 */
        .type-box { 
            border: 2px solid #999; 
            padding: 20px; 
            margin-bottom: 20px; 
            border-radius: 10px; 
            background-color: #fff; 
            page-break-inside: avoid; 
        }

        /* 지문 스타일 */
        .passage { 
            font-size: 10pt; 
            border: 1px solid #000; 
            padding: 25px; 
            margin-bottom: 30px; 
            background-color: #fff; 
            line-height: 1.8; 
            text-align: justify;
        }
        .passage p { 
            text-indent: 1em; 
            margin-bottom: 10px; 
            display: block;
        }
        
        /* (가), (나) 지문 표시 */
        .passage-label {
            font-weight: bold; font-size: 1.1em; color: #fff;
            display: inline-block; background-color: #000;
            padding: 2px 8px; border-radius: 4px; margin-right: 5px; margin-bottom: 10px;
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }
        
        /* 문단 요약 칸 */
        .summary-blank { 
            display: block; margin-top: 10px; margin-bottom: 20px; padding: 0 10px; 
            height: 100px; border: 1px solid #777; border-radius: 5px;
            color: #555; font-size: 0.9em; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        .source-info { /* 문학 작품명/작가명 표시용 */
            text-align: right; font-size: 0.85em; color: #666; margin-bottom: 30px; 
            font-style: italic; font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        /* 문제/질문 스타일 */
        .question-box { 
            margin-bottom: 25px; 
            page-break-inside: avoid; 
        }

        /* 문제 발문 강조 스타일 */
        .question-box b, .question-box strong {
            font-weight: 900; 
            display: inline-block;
            margin-bottom: 5px;
        }
        
        .example-box { /* 보기 박스 */
            border: 1px solid #333; padding: 15px; margin: 10px 0; 
            background-color: #f7f7f7; 
            font-size: 0.95em; font-weight: normal;
        }

        /* 객관식 선지 목록 스타일 */
        .choices { 
            padding-left: 20px;
            text-indent: -20px; 
            margin-left: 20px;
            padding-top: 10px;
            line-height: 1.4;
        }
        .choices div { 
            margin-bottom: 5px; 
        }
        
        /* 서술 공간 (비문학: write-box, 문학: write-box) */
        .write-box { 
            margin-top: 15px; margin-bottom: 10px; height: 150px; 
            border: 1px solid #777; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; border-radius: 5px; 
        }

        /* 문학 전용 긴 밑줄 */
        .long-blank-line {
            display: block; 
            border-bottom: 1px solid #000; 
            margin: 5px 0 15px 0; 
            min-height: 1.5em; 
            width: 95%; 
        }
        .answer-line-gap { /* 문학 서술형 답안용 큰 공백 밑줄 */
            display: block;
            border-bottom: 1px solid #000;
            margin: 25px 0 25px 0;
            min-height: 1.5em;
            width: 95%;
        }

        /* 빈칸 밑줄 */
        .blank {
            display: inline-block;
            min-width: 60px;
            border-bottom: 1px solid #000;
            margin: 0 2px;
            vertical-align: bottom;
            height: 1.2em;
        }
        
        /* 테이블 스타일 (문학: 유형 4) */
        .analysis-table { 
            width: 100%; border-collapse: collapse; margin-top: 10px; 
            font-size: 0.95em; line-height: 1.4;
        }
        .analysis-table th, .analysis-table td { 
            border: 1px solid #000; padding: 8px; text-align: left;
        }
        .analysis-table th { 
            background-color: #e6e6fa; 
            text-align: center; font-weight: bold;
        }
        .analysis-table .blank-row { height: 35px; }

        /* 정답/해설 */
        .answer-sheet { 
            background: #f8f9fa; padding: 40px; margin-top: 50px; 
            border: 1px solid #ccc; border-radius: 10px; 
            page-break-before: always; line-height: 1.8; font-size: 10.5pt;
        }
        
        @media print { body { padding: 0; } }
    </style>
</head>
<body>
"""

HTML_TAIL = """
</body>
</html>
"""

# 모델 자동 선택 함수 
def get_best_model():
    """API 환경에서 유효한 최신 Gemini 모델 ID를 찾아서 반환합니다."""
    if "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY or "APIKEY" in GOOGLE_API_KEY:
          return 'gemini-2.5-flash'
          
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        models = [m.name for m in genai.list_models()]
        
        if 'gemini-2.5-flash' in models: return 'gemini-2.5-flash'
        elif 'gemini-2.5-pro' in models: return 'gemini-2.5-pro'
        elif 'gemini-1.5-flash' in models: return 'gemini-1.5-flash'
        elif 'gemini-pro' in models: return 'gemini-pro'
        else: return 'gemini-2.5-flash'
    except Exception: 
        return 'gemini-2.5-flash'


# --------------------------------------------------------------------------
# [Session State 및 콜백 함수]
# --------------------------------------------------------------------------
# 공통 세션 상태 초기화
if 'generation_requested' not in st.session_state:
    st.session_state.generation_requested = False
if 'd_mode' not in st.session_state:
    st.session_state.d_mode = 'AI 생성'
if 'manual_passage_input' not in st.session_state:
    st.session_state.manual_passage_input = ""
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "비문학 문제 제작" # 기본값

def request_generation():
    # 모든 요청 시, 세션 상태를 True로 설정
    st.session_state.generation_requested = True

# 비문학 전용 콜백
def non_fiction_update_mode():
    st.session_state.d_mode = st.session_state.domain_mode_select
    # 모드 변경 시, 기존 AI 생성 입력 필드를 초기화 (필요하다면)
    if st.session_state.d_mode == '직접 입력':
        if 'topic_input' in st.session_state: st.session_state.topic_input = ""
        if 'topic_a_input' in st.session_state: st.session_state.topic_a_input = ""
        if 'topic_b_input' in st.session_state: st.session_state.topic_b_input = ""
    else:
        st.session_state.manual_passage_input = ""

# Streamlit UI 스타일 설정
st.markdown("""
<style>
    /* 기본 버튼 스타일 통일 */
    .stButton>button { width: 100%; background-color: #2e8b57; color: white; height: 3em; font-size: 20px; border-radius: 10px; }
    .stNumberInput input { text-align: center; }
    /* 앱 모드 선택 라디오 버튼 스타일 */
    div[role="radiogroup"] > label {
        padding: 5px 10px; 
        border: 1px solid #ccc; 
        border-radius: 5px; 
        margin-right: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 🧩 비문학 문제 제작 함수
# ==========================================

def non_fiction_app():
    
    # --------------------------------------------------------------------------
    # [설정값 정의]
    # --------------------------------------------------------------------------
    current_d_mode = st.session_state.get('domain_mode_select', st.session_state.d_mode)
    
    # Sidebar UI 렌더링
    with st.sidebar:
        st.header("🛠️ 지문 입력 방식 선택")
        st.selectbox("지문 입력 방식", ["AI 생성", "직접 입력"], key="domain_mode_select", on_change=non_fiction_update_mode)
        st.markdown("---")

        st.header("1️⃣ 지문 구성 및 주제 설정")
        
        # AI 생성 모드
        if current_d_mode == 'AI 생성':
            mode = st.radio("지문 구성 방식", ["단일 지문 (기본)", "주제 통합 (가) + (나)"], index=0, key="ai_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술"]
            
            if st.session_state.ai_mode == "단일 지문 (기본)":
                domain = st.selectbox("문제 영역", domains, key="domain_select")
                topic = st.text_input("주제 입력", placeholder="예: 금리 인하 효과", key="topic_input")
            else:
                st.markdown("#### 🅰️ (가) 글 설정")
                domain_a = st.selectbox("[(가) 영역]", domains, key="dom_a")
                topic_a = st.text_input("[(가) 주제]", placeholder="예: 칸트의 미학", key="topic_a_input")
                
                st.markdown("#### 🅱️ (나) 글 설정")
                domain_b = st.selectbox("[(나) 영역]", domains, key="dom_b", index=7)
                topic_b = st.text_input("[(나) 주제]", placeholder="예: 현대 미술의 추상성", key="topic_b_input")
                
                domain = f"{domain_a} + {domain_b}"
                topic = f"(가) {topic_a} / (나) {topic_b}"
            
            difficulty = st.select_slider("난이도", ["하", "중", "상", "최상(LEET급)"], value="최상(LEET급)", key="difficulty_select")
            current_topic = topic
            current_mode = st.session_state.ai_mode
            current_domain = domain

        # 직접 입력 모드
        else:
            mode = st.radio("지문 구성 방식", ["단일 지문", "주제 통합 (가) + (나)"], index=0, key="manual_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술", "사용자 지정"]
            domain = st.selectbox("문제 영역", domains, key="manual_domain_select")
            topic = "사용자 입력 지문"
            difficulty = "사용자 지정"
            current_topic = topic
            current_mode = st.session_state.manual_mode
            current_domain = domain

        st.markdown("---")
        
        st.header("2️⃣ 문제 유형 및 개수 선택")
        
        label_type1 = "1. 핵심 주장 요약 (서술형)" if current_mode == "단일 지문 (기본)" or current_mode == "단일 지문" else "1. (가),(나) 요약 및 연관성 서술"
        
        type1 = st.checkbox(label_type1, value=True, key="select_t1")
        type2 = st.checkbox("2. 내용 일치 O/X", key="select_t2")
        type2_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t2") if type2 else 0
        type3 = st.checkbox("3. 빈칸 채우기", key="select_t3")
        type3_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t3") if type3 else 0
        
        type4_original = st.checkbox("4. 변형 문장 정오판단", key="select_t4")
        type4_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t4") if type4_original else 0
        
        type5 = st.checkbox("5. 객관식 (일치/불일치)", key="select_t5")
        type5_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t5") if type5 else 0
        type6 = st.checkbox("6. 객관식 (추론)", key="select_t6")
        type6_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t6") if type6 else 0
        type7 = st.checkbox("7. 객관식 (보기 적용 3점)", key="select_t7")
        type7_cnt = st.number_input(" - 문항 수", 1, 10, 1, key="t7") if type7 else 0
        
        use_summary = st.checkbox("📌 지문 문단별 요약 훈련", value=False, key="select_summary")
        use_recommendation = st.checkbox(f"🌟 영역 맞춤 추천 문제 추가", value=False, key="select_recommendation")

    # 2. 텍스트 입력 (메인 화면)
    if current_d_mode == '직접 입력':
        st.subheader("📝 직접 입력 지문")
        manual_passage = st.text_area("분석할 지문 텍스트", height=400, key="manual_passage_input",
                                     placeholder="여기에 비문학 지문을 직접 붙여넣어 주세요. (최소 5문단 권장)")
    else:
        st.subheader(f"AI 생성 지문 (선택 영역: {current_domain})")
        st.caption("출제하기 버튼을 누르면 AI가 지문을 생성합니다.")
        manual_passage = "" 

    # 3. 메인 실행 버튼
    if st.button("🚀 모의평가 출제하기 (클릭)", key="non_fiction_run_btn"):
        request_generation()


    # --------------------------------------------------------------------------
    # [AI 생성 및 출력 메인 로직]
    # --------------------------------------------------------------------------

    if st.session_state.generation_requested and st.session_state.app_mode == "비문학 문제 제작":
        
        # 입력 값들을 Session State에서 다시 가져옵니다
        current_d_mode = st.session_state.domain_mode_select
        current_mode = st.session_state.get("ai_mode", st.session_state.get("manual_mode", "단일 지문 (기본)"))
        current_manual_passage = st.session_state.get("manual_passage_input", "")

        current_topic = st.session_state.get("topic_input", "사용자 입력 지문")
        current_difficulty = st.session_state.get("difficulty_select", "사용자 지정")
        
        # AI/직접 입력 모드에 따른 domain/topic 재설정
        if current_d_mode == 'AI 생성':
            if current_mode == "단일 지문 (기본)":
                current_domain = st.session_state.get("domain_select", "사용자 지정")
            else:
                dom_a = st.session_state.get('dom_a', '인문')
                dom_b = st.session_state.get('dom_b', '철학')
                topic_a = st.session_state.get('topic_a_input', '')
                topic_b = st.session_state.get('topic_b_input', '')
                current_domain = f"{dom_a} + {dom_b}"
                current_topic = f"(가) {topic_a} / (나) {topic_b}"
        else:
            current_domain = st.session_state.get('manual_domain_select', '사용자 지정')
            current_topic = "사용자 입력 지문"
            current_difficulty = "사용자 지정"
            
        # 문제 개수 및 체크박스 상태 로드
        count_t2 = st.session_state.get("t2", 0)
        count_t3 = st.session_state.get("t3", 0)
        count_t4 = st.session_state.get("t4", 0)
        count_t5 = st.session_state.get("t5", 0)
        count_t6 = st.session_state.get("t6", 0)
        count_t7 = st.session_state.get("t7", 0)
        
        select_t1 = st.session_state.get("select_t1", False)
        select_t2 = st.session_state.get("select_t2", False)
        select_t3 = st.session_state.get("select_t3", False)
        select_t4 = st.session_state.get("select_t4", False)
        select_t5 = st.session_state.get("select_t5", False)
        select_t6 = st.session_state.get("select_t6", False)
        select_t7 = st.session_state.get("select_t7", False)
        use_summary = st.session_state.get("select_summary", False)
        use_recommendation = st.session_state.get("select_recommendation", False)
        
        
        # 2. 유효성 검사 (API 키, 필수 입력값)
        if current_d_mode == 'AI 생성' and (current_mode == "단일 지문 (기본)" and not current_topic):
            st.warning("⚠️ AI 생성 모드에서는 주제를 입력해주세요!")
            st.session_state.generation_requested = False
        elif current_d_mode == '직접 입력' and not current_manual_passage:
            st.warning("⚠️ 직접 입력 모드에서는 지문을 입력해주세요!")
            st.session_state.generation_requested = False
        elif "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY:
            st.error("⚠️ Streamlit Secrets에 API 키를 설정해주세요!")
            st.session_state.generation_requested = False
        elif not any([select_t1, select_t2, select_t3, select_t4, select_t5, select_t6, select_t7]) and not use_recommendation:
            st.warning("⚠️ 유형을 최소 하나 이상 선택해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡ [{current_domain}] 영역의 특성을 반영하여 출제 중입니다... (약 20~40초)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                generation_config = genai.types.GenerationConfig(
                    temperature=0.1, top_p=0.8, top_k=40, max_output_tokens=40000,
                )
                
                # 3. 지문 생성 및 구성 로직 분기 (프롬프트 구성)
                passage_instruction = ""
                summary_passage_inst = "" 
                summary_answer_inst = "" 
                manual_passage_content = current_manual_passage
                
                if current_d_mode == '직접 입력':
                    
                    # --- 직접 입력 지문 포맷팅 ---
                    if use_summary:
                        re_prompt_summary = f"""
                        사용자 입력 지문을 분석하여 문단별로 <p> 태그와 </p> 태그를 정확히 사용하고, 각 </p> 태그 바로 다음에 <div class='summary-blank'>📝 문단 요약 : </div> 태그를 삽입하시오. **결과는 오직 HTML 태그와 지문 내용으로만 출력해야 합니다.**
                        [텍스트]: {current_manual_passage}
                        """
                        summary_response = model.generate_content(re_prompt_summary, generation_config=GenerationConfig(temperature=0.0, max_output_tokens=4000))
                        manual_passage_content = summary_response.text.replace("```html", "").replace("```", "").strip()
                        
                        summary_answer_inst = """
                        - 정답지 맨 앞부분에 **[지문 문단별 핵심 요약 정답]** 섹션을 만드시오.
                        - 각 문단의 요약 정답을 <div class='summary-answer'> 태그 안에 작성하시오.
                        """
                    else:
                        re_prompt_p_tag = f"""
                        사용자 입력 지문을 분석하여 문단별로 <p> 태그와 </p> 태그를 정확히 사용하여 HTML 형식으로 출력하시오. **결과는 오직 HTML 태그와 지문 내용으로만 출력해야 합니다.**
                        [텍스트]: {current_manual_passage}
                        """
                        p_tag_response = model.generate_content(re_prompt_p_tag, generation_config=GenerationConfig(temperature=0.0, max_output_tokens=4000))
                        manual_passage_content = p_tag_response.text.replace("```html", "").replace("```", "").strip()


                    passage_instruction = f"""
                        2. [사용자 입력 지문]:
                        - **[지시]**: 아래에 출력될 사용자 입력 지문을 분석하여 문제를 생성하시오. 지문을 다시 출력하지 마시오.
                        """
                    
                else: # AI 생성 모드
                    difficulty_guide = f"""
                    - **[난이도]**: {current_difficulty} 난이도
                    - **[문체]**: 학술 논문이나 전문 서적의 건조하고 현학적인 문체 사용.
                    - **[요구사항]**: 정보 밀도를 극한으로 높이고, 다층적 논리 구조(반박, 절충 등)를 포함할 것. 각 문단은 잡다한 설명 없이 핵심 정보로만 꽉 채워 **4~6문장 내외로 밀도 있게 압축**하시오.
                    """
                    
                    if use_summary:
                        summary_passage_inst = "<p> 태그로 문단이 끝날 때마다 <div class='summary-blank'>📝 문단 요약 : </div> 태그를 삽입하시오."
                        summary_answer_inst = """
                        - 정답지 맨 앞부분에 **[지문 문단별 핵심 요약 정답]** 섹션을 만드시오.
                        - 각 문단의 요약 정답을 <div class='summary-answer'> 태그 안에 작성하시오.
                        """
                    
                    if current_mode == "단일 지문 (기본)":
                        passage_instruction = f"""
                        2. [단일 지문 작성]:
                        - 분량: **2000자 내외의 장문**. <div class="passage"> 사용.
                        - **반드시 5개 이상의 문단으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                        {summary_passage_inst}
                        - 주제: {current_topic} ({current_domain})
                        {difficulty_guide}
                        """
                    else:
                        passage_instruction = f"""
                        2. [주제 통합 지문 작성 ((가) + (나))]:
                        - 수능 국어 융합 지문 스타일로 작성.
                        - **[독립성 필수] (가)와 (나)는 서로 독립된 글이어야 함. (나) 글에서 '(가)에 따르면' 등의 표현으로 앞 글을 직접 언급하지 말 것.**
                        
                        - **(가) 글**:
                            <div class="passage">
                            <span class="passage-label">(가)</span><br>
                            {st.session_state.topic_a_input} ({st.session_state.dom_a}) 심층 지문 (1200자 내외).
                            **반드시 4문단 이상으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                            {summary_passage_inst}
                            </div>
                        
                        - **(나) 글**:
                            <div class="passage">
                            <span class="passage-label">(나)</span><br>
                            {st.session_state.topic_b_input} ({st.session_state.dom_b}) 심층 지문 (1200자 내외).
                            **반드시 4문단 이상으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                            {summary_passage_inst}
                            </div>
                        
                        {difficulty_guide}
                        """

                # 4. 문제 요청 리스트 구성
                reqs = []
                
                label_type1 = "1. 핵심 주장 요약 (서술형)" if current_mode == "단일 지문 (기본)" or current_mode == "단일 지문" else "1. (가),(나) 요약 및 연관성 서술"
                if select_t1:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>{label_type1}</h3>
                        <div class="question-box">
                            <b>1. 이 글의 핵심 주장과 내용을 요약하고, 논리적 흐름을 서술하시오. (300자 내외)</b>
                            <div class="write-box"></div>
                        </div>
                    </div>
                    """)

                if select_t2 and count_t2 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>내용 일치 O/X ({count_t2}문항)</h3>
                        - [유형2] 내용 일치 O/X {count_t2}문제 (문장 끝에 (O/X) 표시 필수, 매력적인 오답 유도). 
                        **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t3 and count_t3 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>핵심 빈칸 채우기 ({count_t3}문항)</h3>
                        - [유형3] 핵심 빈칸 채우기 {count_t3}문제. **각 문항은 문장 안에 <span class='blank'></span> 태그를 삽입하여 출제할 것.** **모든 문제는 <div class="question-box"> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t4 and count_t4 > 0: 
                        reqs.append(f"""
                    <div class="type-box">
                        <h3>변형 문장 정오판단 ({count_t4}문항)</h3>
                        - [유형4] 변형 문장 정오판단 {count_t4}문제 (문장 끝에 (O/X) 표시 필수, 함정 선지). 
                        **모든 문제는 <div class="question-box"> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)

                if select_t5 and count_t5 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (일치/불일치) ({count_t5}문항)</h3>
                        - [유형5] 객관식 일치/불일치 {count_t5}문제 (지문 재구성 필요). 
                        **선지 항목은 <div>태그로 감싸서 출력하고 <br> 태그를 사용하지 말 것.**
                        **모든 문제는 <div class="question-box"> 안에 번호. <b>문제 발문</b>과 선지 목록(<div class='choices'>)을 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t6 and count_t6 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (추론) ({count_t6}문항)</h3>
                        - [유형6] 객관식 추론 {count_t6}문제 (비판적 사고 요구). 
                        **선지 항목은 <div>태그로 감싸서 출력하고 <br> 태그를 사용하지 말 것.**
                        **모든 문제는 <div class="question-box"> 안에 번호. <b>문제 발문</b>과 선지 목록(<div class='choices'>)을 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t7 and count_t7 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (보기 적용 3점) ({count_t7}문항)</h3>
                        - [유형7] 보기 적용 고난도 {count_t7}문제 (3점, 킬러 문항). 
                        **<보기> 내용은 반드시 <div class='example-box'> 태그 안에 삽입하고, 선지는 <div class='choices'>를 사용하며 <div>로 항목을 감쌀 것.** **모든 문제는 <div class="question-box"> 안에 번호. <b>문제 발문</b>을 사용하여 출제할 것.**
                    </div>
                    """)


                if use_recommendation:
                    rec_prompt = f"""
                    <div class="type-box bonus-box">
                        <h3>[보너스] {current_domain} 심화 탐구</h3>
                        <div class="question-box">
                            <b>다음은 {current_domain} 심화 문제입니다. 알맞은 답을 고르시오. (3점)</b><br><br>
                            <div class="choices">
                                <div>① 보기1</div>
                                <div>② 보기2</div>
                                <div>③ 보기3</div>
                                <div>④ 보기4</div>
                                <div>⑤ 보기5</div>
                            </div>
                        </div>
                    </div>
                    """
                    reqs.append(rec_prompt)
                
                # --- 객관식 해설 규칙 텍스트 (비문학용) ---
                # **[긴급 수정: 오류 블록을 빈 문자열로 대체]**
                objective_rule_text_nonfiction = ''
                # ------------------------------------------------------------------------------------------------
                
                # 5. 최종 프롬프트 구성 및 AI 호출
                
                # 1. 프롬프트 시작 부분 (정답지 시작 태그까지)
                prompt_start = f"""
                당신은 대한민국 최고의 수능 국어 출제 위원(평가원장급)입니다.
                난이도: {current_difficulty} (최상위권 변별력 필수)
                
                **[지시사항: HTML <body> 내용만 작성. <html>, <head> 금지]**
                
                1. 제목: <h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>
                
                [지시사항: 시간 기록 박스 추가]
                - 제목(h2) 바로 아래에 반드시 <div class="time-box"> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div> 태그를 넣으시오.
                
                {passage_instruction}
                {summary_passage_inst}
                
                3. 문제 출제 (유형별 묶음):
                - **[핵심]** 문제 유형을 **<div class="type-box">**로 묶고, 그 안에 **'유형 제목(<h3>)'**과 **'해당 유형의 모든 문제들'**을 넣으시오.
                - 전체 문제 번호는 1번부터 연속되게 매기시오.
                {"\n".join(reqs)}
                
                [태그 및 레이아웃 규칙 (엄수)]
                - **문제의 발문(질문) 부분만 <b> 태그로 굵게.** (선지는 굵게 X)
                - **[중요] 객관식 문제의 발문(질문) 바로 뒤에는 <br><br> 태그를 사용하여 선지와의 간격을 넓히시오.**
                - **[중요] 모든 문제는 각각 <div class="question-box"> 태그로 감싸시오.**
                - 선지 부분은 반드시 <div class="choices">로 감쌀 것.
                - **선지 항목은 반드시 <div>로 감싸서 출력하고 <br> 태그는 사용하지 마시오.**
                - [유형1] 밑 <div class="write-box"></div>.
                - [유형3] 빈칸은 반드시 <span class='blank'></span> 태그를 사용.
                - [유형7] 및 보기는 <div class="example-box">.
                
                [지시사항 5: 정답 및 해설]
                - **문서의 맨 마지막에 딱 한 번만 <div class="answer-sheet"> 태그를 사용하여 정답지를 작성하시오.**
                {summary_answer_inst}
                - **[필수] O/X 문제 정답 표기:** 반드시 **'O', 'X'** 기호 사용 (정/오 금지).
                
                """
                
                # 2. 객관식 해설 부분 (조건부 연결)
                prompt_answer_obj = ""
                total_objective_count = count_t5 + count_t6 + count_t7
                
                if total_objective_count > 0:
                    # **오류 방지 위해 rule_text를 빈 문자열로 사용**
                    rule_text = objective_rule_text_nonfiction
                    count_text = f"<h4>객관식 정답 및 해설 ({total_objective_count}문항)</h4><br>[지시]: {total_objective_count}문항의 정답(번호) 및 상세 해설(정답 풀이, 오답 풀이)을 작성. 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 충분히 간격을 확보할 것. (해설 양식 규칙 텍스트는 서버 오류 회피를 위해 생략됨)<br><br>"
                    prompt_answer_obj = rule_text + count_text
                
                # 3. 프롬프트 최종 마침 부분
                prompt_end = """
                </div>
                """
                
                # 최종 prompt 결합
                prompt = prompt_start + prompt_answer_obj + prompt_end
                
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                # 6. 결과 처리 및 출력
                clean_content = response.text.replace("```html", "").replace("```", "")\
                                             .replace("***", "").replace("**", "")\
                                             .replace("##", "").strip()
                
                full_html = HTML_HEAD
                
                # AI 생성 모드일 경우: AI가 생성한 제목/시간 박스/지문 부분을 추출하여 본문 상단에 먼저 추가
                if current_d_mode == 'AI 생성':
                    
                    header_and_passage_match = re.search(r'(<h1>.*?<\/div>.*?<div class="passage">.*?<\/div>)', clean_content, re.DOTALL)
                    
                    if header_and_passage_match:
                        extracted_content = header_and_passage_match.group(0)
                        full_html += extracted_content
                        clean_content = clean_content.replace(extracted_content, "", 1)
                        
                    else:
                        st.warning("⚠️ AI가 지문을 생성하지 못했습니다. 다시 시도해 주세요.")
                        full_html += clean_content
                        
                # 직접 입력 모드일 경우: Python이 제목/시간 박스 및 포맷팅된 지문을 수동으로 추가
                elif current_d_mode == '직접 입력' and current_manual_passage:
                    
                    # 1. 제목/시간 박스를 수동으로 추가 (단 한 번 출력)
                    full_html += f"<h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>"
                    full_html += f"<div class='time-box'> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div>"
                    
                    # 2. 지문 본문 (<div class="passage"> 태그로 감싸서 출력)
                    full_html += f"""
                    <div class="passage">
                    {manual_passage_content}
                    </div>
                    """
                    
                    # AI가 생성한 문제 내용 중 혹시라도 포함되었을 수 있는 제목/시간 박스 및 지문 관련 지시 부분을 제거
                    clean_content = re.sub(r'<h1>.*?<\/div>.*?<div class="time-box">.*?<\/div>|2\. \[.*?지문\]:.*?지시\]:.*?지문은 다시 출력하지 마시오\.', '', clean_content, 1, re.DOTALL)
                
                # 지문 아래에 나머지 문제 내용 및 정답지 추가
                full_html += clean_content
                full_html += HTML_TAIL

                
                if len(clean_content) < 100 and not current_manual_passage:
                    st.error("⚠️ 생성 오류: AI가 내용을 충분히 생성하지 못했습니다. **다시 생성하기** 버튼을 눌러주세요.")
                    st.session_state.generation_requested = False
                else:
                    status.success(f"✅ 생성 완료! (사용 모델: {model_name})")
                    
                    # --- [재생성 버튼 및 다운로드 추가] ---
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.button("🔄 다시 생성하기 (같은 내용으로 재요청)", on_click=request_generation)
                    with col2:
                        st.download_button("📥 시험지 다운로드 (HTML)", full_html, f"사계국어_모의고사.html", "text/html")

                    st.components.v1.html(full_html, height=800, scrolling=True)

                st.session_state.generation_requested = False


            except Exception as e:
                status.error(f"오류 발생: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 📖 문학 문제 제작 함수
# ==========================================

def fiction_app():
    
    # --------------------------------------------------------------------------
    # [메인 UI 및 실행 로직]
    # --------------------------------------------------------------------------
    st.subheader("📚 문학 심층 분석 콘텐츠 생성 시스템")

    # 1. 입력 설정 (사이드바)
    with st.sidebar:
        st.header("1️⃣ 분석 정보 입력")
        # key 충돌 방지를 위해 fiction_ 접두사를 사용합니다.
        work_name = st.text_input("작품명", placeholder="예: 호질(虎叱) 또는 홍길동전", key="fiction_work_name_input")
        author_name = st.text_input("작가명", placeholder="예: 박지원 또는 허균", key="fiction_author_name_input")
        st.markdown("---")
        
        st.header("2️⃣ 출제 유형 및 개수 선택")
        
        # 유형 1: 어휘 문제 (단답형)
        st.subheader("📝 유형 1. 어휘 문제 (단답형)")
        count_t1 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t1")
        
        # 유형 2: 서술형 심화 문제 (개수 선택)
        st.subheader("✍️ 유형 2. 서술형 심화 문제")
        count_t2 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t2")
        
        # 유형 3: 객관식 문제 (개수 선택)
        st.subheader("🔢 유형 3. 객관식 문제")
        count_t3 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=5, key="fiction_c_t3")

        st.markdown("---")
        st.caption("✅ **단일 분석 콘텐츠 (출제 여부 선택)**")

        # 유형 4: 주요 등장인물 정리 (출제 여부)
        select_t4 = st.checkbox("유형 4. 주요 등장인물 정리 (표)", key="fiction_select_t4")
        
        # 유형 5: 소설 속 상황 요약 (출제 여부)
        select_t5 = st.checkbox("유형 5. 소설 속 상황 요약", key="fiction_select_t5")
        
        # 유형 6: 인물 관계도 및 갈등 작성 (출제 여부)
        select_t6 = st.checkbox("유형 6. 인물 관계도 및 갈등", key="fiction_select_t6")
        
        # 유형 7: 핵심 갈등 구조 및 심리 정리 (출제 여부)
        select_t7 = st.checkbox("유형 7. 핵심 갈등 구조 및 심리", key="fiction_select_t7")
        
        st.markdown("---")
        st.header("3️⃣ 유형 8. 사용자 지정 문제")
        
        # 유형 8: 사용자 지정 문제 (제목 및 개수 입력)
        count_t8 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=0, key="fiction_c_t8")
        if count_t8 > 0:
            custom_title_t8 = st.text_input("유형 8 제목 및 문제 형식", 
                                            placeholder="예: 비평 관점 적용 문제 (객관식 5개 선지)", 
                                            key="fiction_title_t8")
        else:
            custom_title_t8 = ""
        
        
        # 메인 생성 버튼
        if st.button("🚀 문학 분석 자료 생성 요청", key="fiction_run_btn"):
            if count_t1 + count_t2 + count_t3 + count_t8 <= 0 and not any([select_t4, select_t5, select_t6, select_t7]):
                st.warning("⚠️ 최소 하나 이상의 문제 유형을 선택하고 문항 수를 1 이상으로 설정해야 합니다.")
            elif count_t8 > 0 and not custom_title_t8:
                st.warning("⚠️ 유형 8 문항 수가 1 이상이면 제목 및 문제 형식을 입력해야 합니다.")
            else:
                request_generation()


    # 2. 텍스트 입력 (메인 화면)
    st.subheader("📖 분석할 소설 텍스트 입력")
    # key 충돌 방지를 위해 fiction_ 접두사를 사용합니다.
    novel_text_input = st.text_area("소설 텍스트 (발췌분도 가능)", height=400, 
                                     placeholder="여기에 소설 텍스트 전체(또는 발췌분)를 붙여넣어 주세요.", 
                                     key="fiction_novel_text_input_area")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # [AI 생성 및 출력 메인 로직]
    # --------------------------------------------------------------------------

    if st.session_state.generation_requested and st.session_state.app_mode == "문학 문제 제작":
        
        # Session state에서 값들을 가져올 때, fiction_ 접두사를 사용합니다.
        current_work_name = st.session_state.fiction_work_name_input
        current_author_name = st.session_state.fiction_author_name_input
        current_novel_text = st.session_state.fiction_novel_text_input_area
        
        current_count_t1 = st.session_state.fiction_c_t1
        current_count_t2 = st.session_state.fiction_c_t2
        current_count_t3 = st.session_state.fiction_c_t3
        current_count_t8 = st.session_state.fiction_c_t8
        current_title_t8 = st.session_state.get("fiction_title_t8", "")
        
        select_t4 = st.session_state.get("fiction_select_t4", False)
        select_t5 = st.session_state.get("fiction_select_t5", False)
        select_t6 = st.session_state.get("fiction_select_t6", False)
        select_t7 = st.session_state.get("fiction_select_t7", False)
        
        if not current_novel_text or not current_work_name:
            st.warning("⚠️ 작품명과 소설 텍스트를 모두 입력해주세요!")
            st.session_state.generation_requested = False
        elif "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY:
            st.error("⚠️ Streamlit Secrets에 API 키를 설정해주세요!")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡문학 분석 콘텐츠를 생성 중입니다... (약 30초 소요)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                generation_config = genai.types.GenerationConfig(
                    temperature=0.2, top_p=0.8, max_output_tokens=40000,
                )
                
                # --------------------------------------------------
                # [핵심 프롬프트 구성]
                # --------------------------------------------------
                reqs = []
                current_question_number = 1 # 문제 번호 카운터

                # 1. 유형 1: 어휘 문제 (단답형)
                if current_count_t1 > 0:
                    req_type1 = f"""
                    <div class='type-box'>
                    <h4>유형 1. 어휘 문제 (단답형 {current_count_t1}문항)</h4>
                    [지시]: 소설 내 고난도 한자어 및 고어 {current_count_t1}개를 선정하여 **'번호. 어휘(한자)의 뜻은 무엇인가?' 형식으로 한 줄에 출력**하도록 문제 발문을 작성할 것. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b> <div class='long-blank-line'></div>** 태그를 사용하여 각 문제를 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type1)
                
                # 2. 유형 2: 서술형 심화 문제
                if current_count_t2 > 0:
                    req_type2 = f"""
                    <div class='type-box'>
                    <h4>유형 2. 서술형 심화 문제 (총 {current_count_t2}문항)</h4>
                    [지시]: 작가의 의도, 상징적 의미, 인물의 모순적 행위, **등장인물의 내면 심리 변화**를 묻는 서술형 문제 {current_count_t2}개를 작성. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b><br><br> <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>** 태그를 사용하여 두 줄 밑줄을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type2)

                # 3. 유형 3: 객관식 문제
                if current_count_t3 > 0:
                    req_type3 = f"""
                    <div class='type-box'>
                    <h4>유형 3. 객관식 문제 (총 {current_count_t3}문항)</h4>
                    [지시]: 주제, 서술상 특징, 인물 이해 등 종합 이해도를 묻는 객관식 {current_count_t3}문항을 작성. **문제 발문에는 유형 정보를 포함하지 말 것.** **선지 항목은 반드시 <div>태그로 감싸서 출력**하고, **각 선지 항목 뒤에 <br> 태그를 사용하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>** 후 문제와 5개의 선지(①~⑤)를 **<div class='choices'>** 태그를 사용하여 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type3)

                # 4. 유형 4: 주요 등장인물 정리
                if select_t4:
                    req_type4 = """
                    <div class='type-box'>
                    <h4>유형 4. 주요 등장인물 정리</h4>
                    [지시]: 주요 인물 5명을 분석하여 다음 4개 컬럼으로 구성된 **빈칸 표**를 작성하시오.
                    [출력]: **<div class='question-box'>** 안에 <b>주요 등장인물 정리 (학생 작성)</b><br> 다음 형식의 HTML 표(class="analysis-table")를 작성할 것. **내용은 모두 비워두고 헤딩과 5개의 빈 행(class="blank-row")만 남길 것.** (컬럼: 인물명, 지문 내 호칭/역할, 작중 역할 (기능), 심리 및 비판 의도)
                    </div>
                    """
                    reqs.append(req_type4)

                # 5. 유형 5: 소설 속 상황 요약
                if select_t5:
                    req_type5 = f"""
                    <div class='type-box'>
                    <h4>유형 5. 소설 속 상황 요약</h4>
                    <b>분석 텍스트의 배경, 핵심 사건, 주요 갈등의 표면적 계기를 4문장 이내로 간결하게 요약하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type5)

                # 6. 유형 6: 인물 관계도 및 갈등 작성
                if select_t6:
                    req_type6 = f"""
                    <div class='type-box'>
                    <h4>유형 6. 인물 관계도 및 갈등 작성</h4>
                    <b>주요 인물을 중심으로, 인물 간의 관계와 갈등 요소를 화살표와 용어를 사용하여 구조적으로 설명하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type6)

                # 7. 유형 7: 핵심 갈등 구조 및 심리 정리
                if select_t7:
                    req_type7 = f"""
                    <div class='type-box'>
                    <h4>유형 7. 핵심 갈등 구조 및 심리 정리</h4>
                    <b>1) 갈등 양상(성격)과 2) 작가가 궁극적으로 풍자하려는 대상 및 주제 의식을 명확히 서술하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type7)

                # 8. 유형 8: 사용자 지정 문제
                if current_count_t8 > 0:
                    req_type8 = f"""
                    <div class='type-box'>
                    <h4>유형 8. {current_title_t8} (총 {current_count_t8}문항)</h4>
                    [지시]: **유형 8 제목({current_title_t8})에 명시된 형식과 목표**에 따라 {current_count_t8}문항을 생성하시오. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>**을 출력하고, 유형 제목에 객관식(5개 선지)이 명시되었다면 **<div class='choices'>**를 사용하여 선지를 구성할 것. 객관식이 아니라면 **<div class='write-box'></div>**를 사용하여 답안 공간을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type8)
                
                req_all = "\n".join(reqs)

                # --- 객관식 해설 규칙 텍스트 (비문학용) ---
                # **[긴급 수정: 오류 블록을 빈 문자열로 대체]**
                objective_rule_text_nonfiction = ''
                # ------------------------------------------------------------------------------------------------
                
                # 5. 최종 프롬프트 구성 및 AI 호출
                
                # 1. 프롬프트 시작 부분 (정답지 시작 태그까지)
                prompt_start = f"""
                당신은 대한민국 최고의 수능 국어 출제 위원(평가원장급)입니다.
                난이도: {current_difficulty} (최상위권 변별력 필수)
                
                **[지시사항: HTML <body> 내용만 작성. <html>, <head> 금지]**
                
                1. 제목: <h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>
                
                [지시사항: 시간 기록 박스 추가]
                - 제목(h2) 바로 아래에 반드시 <div class="time-box"> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div> 태그를 넣으시오.
                
                {passage_instruction}
                {summary_passage_inst}
                
                3. 문제 출제 (유형별 묶음):
                - **[핵심]** 문제 유형을 **<div class="type-box">**로 묶고, 그 안에 **'유형 제목(<h3>)'**과 **'해당 유형의 모든 문제들'**을 넣으시오.
                - 전체 문제 번호는 1번부터 연속되게 매기시오.
                {"\n".join(reqs)}
                
                [태그 및 레이아웃 규칙 (엄수)]
                - **문제의 발문(질문) 부분만 <b> 태그로 굵게.** (선지는 굵게 X)
                - **[중요] 객관식 문제의 발문(질문) 바로 뒤에는 <br><br> 태그를 사용하여 선지와의 간격을 넓히시오.**
                - **[중요] 모든 문제는 각각 <div class="question-box"> 태그로 감싸시오.**
                - 선지 부분은 반드시 <div class="choices">로 감쌀 것.
                - **선지 항목은 반드시 <div>로 감싸서 출력하고 <br> 태그는 사용하지 마시오.**
                - [유형1] 밑 <div class="write-box"></div>.
                - [유형3] 빈칸은 반드시 <span class='blank'></span> 태그를 사용.
                - [유형7] 및 보기는 <div class="example-box">.
                
                [지시사항 5: 정답 및 해설]
                - **문서의 맨 마지막에 딱 한 번만 <div class="answer-sheet"> 태그를 사용하여 정답지를 작성하시오.**
                {summary_answer_inst}
                - **[필수] O/X 문제 정답 표기:** 반드시 **'O', 'X'** 기호 사용 (정/오 금지).
                
                """
                
                # 2. 객관식 해설 부분 (조건부 연결)
                prompt_answer_obj = ""
                total_objective_count = count_t5 + count_t6 + count_t7
                
                if total_objective_count > 0:
                    # **오류 방지 위해 rule_text를 빈 문자열로 사용**
                    rule_text = objective_rule_text_nonfiction
                    count_text = f"<h4>객관식 정답 및 해설 ({total_objective_count}문항)</h4><br>[지시]: {total_objective_count}문항의 정답(번호) 및 상세 해설(정답 풀이, 오답 풀이)을 작성. 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 충분히 간격을 확보할 것. (해설 양식 규칙 텍스트는 서버 오류 회피를 위해 생략됨)<br><br>"
                    prompt_answer_obj = rule_text + count_text
                
                # 3. 프롬프트 최종 마침 부분
                prompt_end = """
                </div>
                """
                
                # 최종 prompt 결합
                prompt = prompt_start + prompt_answer_obj + prompt_end
                
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                # 6. 결과 처리 및 출력
                clean_content = response.text.replace("```html", "").replace("```", "")\
                                             .replace("***", "").replace("**", "")\
                                             .replace("##", "").strip()
                
                full_html = HTML_HEAD
                
                # AI 생성 모드일 경우: AI가 생성한 제목/시간 박스/지문 부분을 추출하여 본문 상단에 먼저 추가
                if current_d_mode == 'AI 생성':
                    
                    header_and_passage_match = re.search(r'(<h1>.*?<\/div>.*?<div class="passage">.*?<\/div>)', clean_content, re.DOTALL)
                    
                    if header_and_passage_match:
                        extracted_content = header_and_passage_match.group(0)
                        full_html += extracted_content
                        clean_content = clean_content.replace(extracted_content, "", 1)
                        
                    else:
                        st.warning("⚠️ AI가 지문을 생성하지 못했습니다. 다시 시도해 주세요.")
                        full_html += clean_content
                        
                # 직접 입력 모드일 경우: Python이 제목/시간 박스 및 포맷팅된 지문을 수동으로 추가
                elif current_d_mode == '직접 입력' and current_manual_passage:
                    
                    # 1. 제목/시간 박스를 수동으로 추가 (단 한 번 출력)
                    full_html += f"<h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>"
                    full_html += f"<div class='time-box'> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div>"
                    
                    # 2. 지문 본문 (<div class="passage"> 태그로 감싸서 출력)
                    full_html += f"""
                    <div class="passage">
                    {manual_passage_content}
                    </div>
                    """
                    
                    # AI가 생성한 문제 내용 중 혹시라도 포함되었을 수 있는 제목/시간 박스 및 지문 관련 지시 부분을 제거
                    clean_content = re.sub(r'<h1>.*?<\/div>.*?<div class="time-box">.*?<\/div>|2\. \[.*?지문\]:.*?지시\]:.*?지문은 다시 출력하지 마시오\.', '', clean_content, 1, re.DOTALL)
                
                # 지문 아래에 나머지 문제 내용 및 정답지 추가
                full_html += clean_content
                full_html += HTML_TAIL

                
                if len(clean_content) < 100 and not current_manual_passage:
                    st.error("⚠️ 생성 오류: AI가 내용을 충분히 생성하지 못했습니다. **다시 생성하기** 버튼을 눌러주세요.")
                    st.session_state.generation_requested = False
                else:
                    status.success(f"✅ 생성 완료! (사용 모델: {model_name})")
                    
                    # --- [재생성 버튼 및 다운로드 추가] ---
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.button("🔄 다시 생성하기 (같은 내용으로 재요청)", on_click=request_generation)
                    with col2:
                        st.download_button("📥 시험지 다운로드 (HTML)", full_html, f"사계국어_모의고사.html", "text/html")

                    st.components.v1.html(full_html, height=800, scrolling=True)

                st.session_state.generation_requested = False


            except Exception as e:
                status.error(f"오류 발생: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 📖 문학 문제 제작 함수
# ==========================================

def fiction_app():
    
    # --------------------------------------------------------------------------
    # [메인 UI 및 실행 로직]
    # --------------------------------------------------------------------------
    st.subheader("📚 문학 심층 분석 콘텐츠 생성 시스템")

    # 1. 입력 설정 (사이드바)
    with st.sidebar:
        st.header("1️⃣ 분석 정보 입력")
        # key 충돌 방지를 위해 fiction_ 접두사를 사용합니다.
        work_name = st.text_input("작품명", placeholder="예: 호질(虎叱) 또는 홍길동전", key="fiction_work_name_input")
        author_name = st.text_input("작가명", placeholder="예: 박지원 또는 허균", key="fiction_author_name_input")
        st.markdown("---")
        
        st.header("2️⃣ 출제 유형 및 개수 선택")
        
        # 유형 1: 어휘 문제 (단답형)
        st.subheader("📝 유형 1. 어휘 문제 (단답형)")
        count_t1 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t1")
        
        # 유형 2: 서술형 심화 문제 (개수 선택)
        st.subheader("✍️ 유형 2. 서술형 심화 문제")
        count_t2 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t2")
        
        # 유형 3: 객관식 문제 (개수 선택)
        st.subheader("🔢 유형 3. 객관식 문제")
        count_t3 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=5, key="fiction_c_t3")

        st.markdown("---")
        st.caption("✅ **단일 분석 콘텐츠 (출제 여부 선택)**")

        # 유형 4: 주요 등장인물 정리 (출제 여부)
        select_t4 = st.checkbox("유형 4. 주요 등장인물 정리 (표)", key="fiction_select_t4")
        
        # 유형 5: 소설 속 상황 요약 (출제 여부)
        select_t5 = st.checkbox("유형 5. 소설 속 상황 요약", key="fiction_select_t5")
        
        # 유형 6: 인물 관계도 및 갈등 작성 (출제 여부)
        select_t6 = st.checkbox("유형 6. 인물 관계도 및 갈등", key="fiction_select_t6")
        
        # 유형 7: 핵심 갈등 구조 및 심리 정리 (출제 여부)
        select_t7 = st.checkbox("유형 7. 핵심 갈등 구조 및 심리", key="fiction_select_t7")
        
        st.markdown("---")
        st.header("3️⃣ 유형 8. 사용자 지정 문제")
        
        # 유형 8: 사용자 지정 문제 (제목 및 개수 입력)
        count_t8 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=0, key="fiction_c_t8")
        if count_t8 > 0:
            custom_title_t8 = st.text_input("유형 8 제목 및 문제 형식", 
                                            placeholder="예: 비평 관점 적용 문제 (객관식 5개 선지)", 
                                            key="fiction_title_t8")
        else:
            custom_title_t8 = ""
        
        
        # 메인 생성 버튼
        if st.button("🚀 문학 분석 자료 생성 요청", key="fiction_run_btn"):
            if count_t1 + count_t2 + count_t3 + count_t8 <= 0 and not any([select_t4, select_t5, select_t6, select_t7]):
                st.warning("⚠️ 최소 하나 이상의 문제 유형을 선택하고 문항 수를 1 이상으로 설정해야 합니다.")
            elif count_t8 > 0 and not custom_title_t8:
                st.warning("⚠️ 유형 8 문항 수가 1 이상이면 제목 및 문제 형식을 입력해야 합니다.")
            else:
                request_generation()


    # 2. 텍스트 입력 (메인 화면)
    st.subheader("📖 분석할 소설 텍스트 입력")
    # key 충돌 방지를 위해 fiction_ 접두사를 사용합니다.
    novel_text_input = st.text_area("소설 텍스트 (발췌분도 가능)", height=400, 
                                     placeholder="여기에 소설 텍스트 전체(또는 발췌분)를 붙여넣어 주세요.", 
                                     key="fiction_novel_text_input_area")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # [AI 생성 및 출력 메인 로직]
    # --------------------------------------------------------------------------

    if st.session_state.generation_requested and st.session_state.app_mode == "문학 문제 제작":
        
        # Session state에서 값들을 가져올 때, fiction_ 접두사를 사용합니다.
        current_work_name = st.session_state.fiction_work_name_input
        current_author_name = st.session_state.fiction_author_name_input
        current_novel_text = st.session_state.fiction_novel_text_input_area
        
        current_count_t1 = st.session_state.fiction_c_t1
        current_count_t2 = st.session_state.fiction_c_t2
        current_count_t3 = st.session_state.fiction_c_t3
        current_count_t8 = st.session_state.fiction_c_t8
        current_title_t8 = st.session_state.get("fiction_title_t8", "")
        
        select_t4 = st.session_state.get("fiction_select_t4", False)
        select_t5 = st.session_state.get("fiction_select_t5", False)
        select_t6 = st.session_state.get("fiction_select_t6", False)
        select_t7 = st.session_state.get("fiction_select_t7", False)
        
        if not current_novel_text or not current_work_name:
            st.warning("⚠️ 작품명과 소설 텍스트를 모두 입력해주세요!")
            st.session_state.generation_requested = False
        elif "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY:
            st.error("⚠️ Streamlit Secrets에 API 키를 설정해주세요!")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡문학 분석 콘텐츠를 생성 중입니다... (약 30초 소요)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                generation_config = genai.types.GenerationConfig(
                    temperature=0.2, top_p=0.8, max_output_tokens=40000,
                )
                
                # --------------------------------------------------
                # [핵심 프롬프트 구성]
                # --------------------------------------------------
                reqs = []
                current_question_number = 1 # 문제 번호 카운터

                # 1. 유형 1: 어휘 문제 (단답형)
                if current_count_t1 > 0:
                    req_type1 = f"""
                    <div class='type-box'>
                    <h4>유형 1. 어휘 문제 (단답형 {current_count_t1}문항)</h4>
                    [지시]: 소설 내 고난도 한자어 및 고어 {current_count_t1}개를 선정하여 **'번호. 어휘(한자)의 뜻은 무엇인가?' 형식으로 한 줄에 출력**하도록 문제 발문을 작성할 것. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b> <div class='long-blank-line'></div>** 태그를 사용하여 각 문제를 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type1)
                
                # 2. 유형 2: 서술형 심화 문제
                if current_count_t2 > 0:
                    req_type2 = f"""
                    <div class='type-box'>
                    <h4>유형 2. 서술형 심화 문제 (총 {current_count_t2}문항)</h4>
                    [지시]: 작가의 의도, 상징적 의미, 인물의 모순적 행위, **등장인물의 내면 심리 변화**를 묻는 서술형 문제 {current_count_t2}개를 작성. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b><br><br> <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>** 태그를 사용하여 두 줄 밑줄을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type2)

                # 3. 유형 3: 객관식 문제
                if current_count_t3 > 0:
                    req_type3 = f"""
                    <div class='type-box'>
                    <h4>유형 3. 객관식 문제 (총 {current_count_t3}문항)</h4>
                    [지시]: 주제, 서술상 특징, 인물 이해 등 종합 이해도를 묻는 객관식 {current_count_t3}문항을 작성. **문제 발문에는 유형 정보를 포함하지 말 것.** **선지 항목은 반드시 <div>태그로 감싸서 출력**하고, **각 선지 항목 뒤에 <br> 태그를 사용하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>** 후 문제와 5개의 선지(①~⑤)를 **<div class='choices'>** 태그를 사용하여 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type3)

                # 4. 유형 4: 주요 등장인물 정리
                if select_t4:
                    req_type4 = """
                    <div class='type-box'>
                    <h4>유형 4. 주요 등장인물 정리</h4>
                    [지시]: 주요 인물 5명을 분석하여 다음 4개 컬럼으로 구성된 **빈칸 표**를 작성하시오.
                    [출력]: **<div class='question-box'>** 안에 <b>주요 등장인물 정리 (학생 작성)</b><br> 다음 형식의 HTML 표(class="analysis-table")를 작성할 것. **내용은 모두 비워두고 헤딩과 5개의 빈 행(class="blank-row")만 남길 것.** (컬럼: 인물명, 지문 내 호칭/역할, 작중 역할 (기능), 심리 및 비판 의도)
                    </div>
                    """
                    reqs.append(req_type4)

                # 5. 유형 5: 소설 속 상황 요약
                if select_t5:
                    req_type5 = f"""
                    <div class='type-box'>
                    <h4>유형 5. 소설 속 상황 요약</h4>
                    <b>분석 텍스트의 배경, 핵심 사건, 주요 갈등의 표면적 계기를 4문장 이내로 간결하게 요약하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type5)

                # 6. 유형 6: 인물 관계도 및 갈등 작성
                if select_t6:
                    req_type6 = f"""
                    <div class='type-box'>
                    <h4>유형 6. 인물 관계도 및 갈등 작성</h4>
                    <b>주요 인물을 중심으로, 인물 간의 관계와 갈등 요소를 화살표와 용어를 사용하여 구조적으로 설명하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type6)

                # 7. 유형 7: 핵심 갈등 구조 및 심리 정리
                if select_t7:
                    req_type7 = f"""
                    <div class='type-box'>
                    <h4>유형 7. 핵심 갈등 구조 및 심리 정리</h4>
                    <b>1) 갈등 양상(성격)과 2) 작가가 궁극적으로 풍자하려는 대상 및 주제 의식을 명확히 서술하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type7)

                # 8. 유형 8: 사용자 지정 문제
                if current_count_t8 > 0:
                    req_type8 = f"""
                    <div class='type-box'>
                    <h4>유형 8. {current_title_t8} (총 {current_count_t8}문항)</h4>
                    [지시]: **유형 8 제목({current_title_t8})에 명시된 형식과 목표**에 따라 {current_count_t8}문항을 생성하시오. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>**을 출력하고, 유형 제목에 객관식(5개 선지)이 명시되었다면 **<div class='choices'>**를 사용하여 선지를 구성할 것. 객관식이 아니라면 **<div class='write-box'></div>**를 사용하여 답안 공간을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type8)
                
                req_all = "\n".join(reqs)

                # 지문 및 작품 정보 구성
                passage_instruction = f"""
                <div class="passage">
                    <b>[분석 텍스트]</b><br>
                    {current_novel_text}
                </div>
                <div class="source-info">
                    {current_work_name} - {current_author_name}
                </div>
                """
                
                # --- 객관식 해설 규칙 텍스트 (문학용) ---
                # **[긴급 수정: 오류 블록을 빈 문자열로 대체]**
                objective_rule_text_fiction = ''
                # ------------------------------------------------------------------------------------------------

                # 1. 프롬프트 시작 부분 (정답지 시작 태그까지)
                prompt_start = f"""
                당신은 수능/LEET급의 최상위권 변별력을 목표로 하는 국어 문학 평가원 출제 위원입니다.
                [출제 목표] 단순 암기나 사실 확인을 배제하고, 고도의 추론, 비판적 분석, 관점 비교를 요구하는 킬러 문항을 출제해야 합니다. 모든 문제는 최상위권 변별에 초점을 맞추어 논리적 함정을 포함하십시오.

                입력된 [소설 텍스트]를 분석하여 아래 지시된 유형들을 **선택된 순서와 개수**에 따라 정확한 태그로 생성하세요.

                작품명: {current_work_name} / 작가: {current_author_name}
                
                **[지시사항: HTML <body> 내용만 작성. <html>, <head> 및 불필요한 마크다운 기호(```)는 사용하지 마세요]**
                
                1. 제목: <h1>사계국어 문학 분석 스펙트럼</h1>
                
                2. 지문 제시:
                {passage_instruction}
                
                3. 분석 콘텐츠 생성 (선택된 유형만 순서 및 태그 엄수):
                {req_all}
                
                ---
                
                4. 정답 및 해설 작성 (문서의 맨 마지막):
                <div class="answer-sheet">
                    <h3>✅ 정답 및 해설</h3>
                    
                    """

                # 2. 정답 및 해설 콘텐츠 (조건부 연결 - f-string 오류 해결)
                prompt_answer_content = ""
                
                if current_count_t1 > 0:
                    prompt_answer_content += f"<h4>유형 1. 어휘 문제 정답 및 풀이 ({current_count_t1}문항)</h4><br>[지시]: {current_count_t1}문항의 정답과 뜻풀이를 모두 작성. 각 문제의 해설은 줄 바꿈(<br>)하여 구분할 것.<br><br>"
                
                if current_count_t2 > 0:
                    prompt_answer_content += f"<h4>유형 2. 서술형 심화 문제 모범 답안 ({current_count_t2}문항)</h4><br>[지시]: {current_count_t2}문항의 모범 답안을 상세하게 작성하되, **각 문제의 모범 답안이 끝날 때마다 <br><br><br> 태그를 사용하여 충분히 간격을 확보하여 분리할 것.**<br><br>"

                if current_count_t3 > 0:
                    # **오류 방지 위해 rule_text를 빈 문자열로 사용**
                    rule_text = objective_rule_text_fiction
                    count_text = f"<h4>유형 3. 객관식 문제 정답 및 해설 ({current_count_t3}문항)</h4><br>[지시]: {current_count_t3}문항의 정답(번호) 및 상세 해설(정답 풀이, 오답 풀이)을 작성. 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 충분히 간격을 확보할 것. (해설 양식 규칙 텍스트는 서버 오류 회피를 위해 생략됨)<br><br>"
                    
                    rule_block = rule_text + count_text
                    
                    prompt_answer_content += f"<h4>유형 3. 객관식 문제 정답 및 해설 ({current_count_t3}문항)</h4><br>[지시]: {rule_block}"
                
                if select_t4:
                    prompt_answer_content += "<h4>유형 4. 주요 등장인물 정리 모범 답안</h4><br>[지시]: 유형 4에서 요구한 표 형식에 맞춰 모범 답안을 작성하여 제시.<br><br>"
                
                if select_t5:
                    prompt_answer_content += "<h4>유형 5. 소설 속 상황 요약 모범 답안</h4><br>[지시]: 유형 5의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if select_t6:
                    prompt_answer_content += "<h4>유형 6. 인물 관계도 및 갈등 모범 답안</h4><br>[지시]: 유형 6의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if select_t7:
                    prompt_answer_content += "<h4>유형 7. 핵심 갈등 구조 및 심리 모범 답안</h4><br>[지시]: 유형 7의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if current_count_t8 > 0:
                    prompt_answer_content += f"<h4>유형 8. {current_title_t8} 모범 답안 ({current_count_t8}문항)</h4><br>[지시]: 유형 8({current_title_t8})의 모범 답안을 상세하게 작성. 각 문제의 모범 답안이 끝날 때마다 **<br><br><br> 태그를 사용하여 충분히 간격을 확보하여 분리할 것.**<br><br>"
                
                # 3. 프롬프트 최종 마침 부분
                prompt_end = """
                </div>
                """
                
                # 최종 prompt 결합
                prompt = prompt_start + prompt_answer_content + prompt_end
                
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                clean_content = response.text.replace("```html", "").replace("```", "")\
                                             .replace("***", "").replace("**", "")\
                                             .replace("##", "").strip()
                
                if len(clean_content) < 1000 and (current_count_t1 + current_count_t2 + current_count_t3 + current_count_t8 > 0 or any([select_t4, select_t5, select_t6, select_t7])):
                    st.error(f"⚠️ 생성 오류: AI가 내용을 충분히 생성하지 못했습니다. (생성 길이: {len(clean_content)}). **다시 생성하기** 버튼을 눌러주세요.")
                else:
                    full_html = HTML_HEAD + clean_content + HTML_TAIL
                    status.success(f"✅ 분석 학습지 생성 완료! (사용 모델: {model_name})")
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.button("🔄 다시 생성하기 (같은 내용으로 재요청)", on_click=request_generation)
                    with col2:
                        st.download_button("📥 학습지 다운로드 (HTML)", full_html, f"{current_work_name}_분석_학습지.html", "text/html")

                    st.components.v1.html(full_html, height=800, scrolling=True)

                st.session_state.generation_requested = False


            except Exception as e:
                status.error(f"오류 발생: {e}. API 키와 입력값을 확인해주세요.")
                st.session_state.generation_requested = False


# ==========================================
# 🚀 메인 애플리케이션 실행
# ==========================================

# 메인 제목
st.title("📚 사계국어 AI 모의고사 제작 시스템")
st.markdown("---")

# 1. 문제 유형 선택
problem_type = st.radio(
    "출제할 문제 유형을 선택해주세요:",
    ["비문학 문제 제작", "문학 문제 제작"],
    key="app_mode",
    index=0 
)

# 2. 선택에 따른 화면 분기 (세션 상태 초기화 추가로 키 충돌 방지)
if problem_type == "비문학 문제 제작":
    st.header("⚡ 비문학 모의평가 출제")
    if st.session_state.app_mode != "비문학 문제 제작":
        st.session_state.app_mode = "비문학 문제 제작"
        st.session_state.generation_requested = False
    non_fiction_app()
elif problem_type == "문학 문제 제작":
    st.header("📖 문학 심층 분석 콘텐츠 제작")
    if st.session_state.app_mode != "문학 문제 제작":
        st.session_state.app_mode = "문학 문제 제작"
        st.session_state.generation_requested = False
    fiction_app()
