import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import re 
import os
from docx import Document
from io import BytesIO
from docx.shared import Inches
from docx.shared import Pt

# ==========================================
# [설정] API 키 연동 (Streamlit Cloud Secrets 권장)
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
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
            line-height: 1.8; 
            color: #000; 
            font-size: 10.5pt;
        }
        
        h1 { text-align: center; margin-bottom: 5px; font-size: 28px; letter-spacing: -1px; }
        h2 { text-align: center; margin-top: 0; margin-bottom: 30px; font-size: 16px; color: #333; }
        
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 30px;
            padding: 10px 20px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fdfdfd; font-size: 0.95em;
        }

        h3 { 
            margin-top: 30px; 
            margin-bottom: 15px; 
            font-size: 1.4em; 
            color: #2e8b57; 
            border-bottom: 2px solid #2e8b57;
            padding-bottom: 5px;
            font-weight: bold;
        }

        /* 지문 스타일 */
        .passage { 
            font-size: 10.5pt; 
            border: 1px solid #000; 
            padding: 25px; 
            margin-bottom: 40px; 
            background-color: #fff; 
            line-height: 1.8; 
            text-align: justify;
        }
        .passage p { margin-bottom: 10px; text-indent: 0.5em; }
        
        .passage-label {
            font-weight: bold; font-size: 1.1em; color: #fff;
            display: inline-block; background-color: #000;
            padding: 2px 8px; border-radius: 4px; margin-right: 5px; margin-bottom: 10px;
        }
        
        /* 문제 박스 */
        .question-box { 
            margin-bottom: 30px; 
            page-break-inside: avoid; 
            border-bottom: 1px dashed #ddd;
            padding-bottom: 20px;
        }

        .question-title { font-weight: 900; font-size: 1.1em; margin-bottom: 15px; display: block; }
        
        .example-box { 
            border: 1px solid #333; padding: 15px; margin: 10px 0; 
            background-color: #f9f9f9; font-size: 0.95em; 
        }

        .choices { padding-left: 10px; margin-top: 10px; }
        .choices div { margin-bottom: 8px; }
        
        /* 정답지 스타일 */
        .answer-sheet { 
            background: #f4f4f4; padding: 30px; margin-top: 50px; 
            border: 1px solid #ccc; border-radius: 10px; 
            page-break-before: always; 
        }
        .answer-item { margin-bottom: 20px; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
        .answer-title { font-weight: bold; color: #333; margin-bottom: 5px; }
        
        @media print { body { padding: 0; } }
    </style>
</head>
<body>
"""

HTML_TAIL = """
</body>
</html>
"""

def get_best_model():
    """Gemma-3를 최우선으로 사용하는 모델 선택 함수"""
    if "DUMMY" in GOOGLE_API_KEY: return 'models/gemma-3-27b-it'
    
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        # 우선순위: Gemma 3 (무료량 많음) -> Gemini 2.0 -> Gemini 1.5
        priority_candidates = [
            'models/gemma-3-27b-it',
            'models/gemma-3-12b-it',
            'models/gemini-2.0-flash',
            'models/gemini-2.0-flash-lite-preview-02-05',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-001'
        ]
        
        # 목록 확인 없이 강제 지정 (목록에 없어도 되는 경우가 많음)
        return 'models/gemma-3-27b-it' 

    except Exception: 
        return 'models/gemma-3-27b-it'

# ==========================================
# [DOCX 생성 함수]
# ==========================================
def create_docx(html_content, file_name, current_topic, is_fiction=False):
    document = Document()
    
    # 간단한 텍스트 추출 로직 (HTML 태그 제거)
    def clean_text(text):
        return re.sub(r'<[^>]+>', '', text).strip()

    # 제목 추가
    document.add_heading("사계국어 AI 모의고사", level=0)
    document.add_heading(f"주제: {current_topic}", level=2)
    
    # 본문 내용 추가 (HTML 파싱 약식 구현)
    # 실제 프로덕션급에서는 BeautifulSoup 등을 사용하는 것이 좋으나, 
    # 여기서는 정규식으로 핵심 내용만 발췌하여 넣습니다.
    
    # 1. 지문
    passage_match = re.search(r'<div class="passage">(.*?)<\/div>', html_content, re.DOTALL)
    if passage_match:
        document.add_heading("I. 지문", level=1)
        p_text = clean_text(passage_match.group(1).replace("<br>", "\n").replace("</p>", "\n"))
        document.add_paragraph(p_text)

    # 2. 문제 및 정답
    # HTML 전체를 텍스트로 변환하여 저장
    # (워드 변환은 복잡도가 높아 텍스트 위주로 저장합니다)
    full_text = clean_text(html_content.replace("<br>", "\n").replace("</div>", "\n"))
    
    # 지문 이후 내용만 대략적으로 추가
    if "I. 지문" not in full_text: # 지문이 이미 위에서 처리됨
        document.add_paragraph(full_text[:500] + "\n... (상세 내용은 HTML 참조) ...")

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==========================================
# 🧩 비문학 문제 제작 함수
# ==========================================

def non_fiction_app():
    global GOOGLE_API_KEY
    
    # 사이드바 설정
    with st.sidebar:
        st.header("🛠️ 설정")
        current_d_mode = st.selectbox("지문 입력 방식", ["AI 생성", "직접 입력"], key="domain_mode_select")
        
        st.markdown("---")
        st.header("1️⃣ 지문 구성")
        
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""

        if current_d_mode == 'AI 생성':
            domain = st.selectbox("영역", ["인문", "사회", "과학", "기술", "예술"], key="domain_select")
            topic = st.text_input("주제", placeholder="예: 양자역학의 불확정성", key="topic_input")
            current_domain = domain
            current_topic = topic
            
        else: # 직접 입력
            current_domain = "사용자 지정"
            current_topic = "사용자 입력 지문"
            # 지문 입력은 메인 화면에서 받음

        st.markdown("---")
        st.header("2️⃣ 문제 유형")
        select_t1 = st.checkbox("1. 핵심 요약 (서술형)", value=True)
        select_t2 = st.checkbox("2. 내용 일치 (O/X)", value=True)
        select_t5 = st.checkbox("3. 객관식 (일치/불일치)", value=True)
        
        difficulty = st.select_slider("난이도", ["중", "상", "최상(LEET)"], value="상")

    # 메인 화면
    if current_d_mode == '직접 입력':
        st.info("지문을 아래에 입력해주세요.")
        current_manual_passage = st.text_area("지문 텍스트", height=300, key="manual_input")

    if st.button("🚀 모의고사 생성 시작", type="primary"):
        if current_d_mode == 'AI 생성' and not current_topic:
            st.warning("주제를 입력해주세요.")
            return
        if current_d_mode == '직접 입력' and not current_manual_passage:
            st.warning("지문을 입력해주세요.")
            return

        with st.spinner("AI가 지문과 문제를 출제하고 있습니다... (Gemma-3 모델)"):
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                # ----------------------------------------------------
                # [프롬프트 전략] 모드에 따라 지문 생성 여부 결정
                # ----------------------------------------------------
                
                # 1. 문제 요청 목록 생성
                reqs = []
                if select_t1: reqs.append("- [서술형] 지문의 핵심 주장을 300자 내외로 요약하시오.")
                if select_t2: reqs.append("- [O/X] 지문 내용과 일치 여부를 묻는 O/X 문제 2문항.")
                if select_t5: reqs.append("- [객관식] 윗글의 내용과 일치하지 않는 것은? (5지 선다) 2문항.")
                
                reqs_str = "\n".join(reqs)

                # 2. 프롬프트 작성
                if current_d_mode == "AI 생성":
                    # [AI 생성 모드] -> 지문도 써줘!
                    prompt = f"""
                    당신은 수능 국어 출제위원입니다.
                    주제: '{current_topic}' ({current_domain})
                    난이도: {difficulty}
                    
                    **[지시 1] 지문 작성**
                    - 해당 주제로 수능 비문학 스타일의 지문을 작성하시오. (1200자 내외, 4문단 이상)
                    - 지문은 반드시 `<div class="passage">` 태그 안에 작성하시오. 문단은 `<p>` 태그로 구분.

                    **[지시 2] 문제 출제**
                    - 작성된 지문을 바탕으로 아래 문제들을 출제하시오.
                    {reqs_str}
                    
                    **[지시 3] 형식 엄수 (HTML)**
                    - 각 문제는 `<div class="question-box">` 안에 `<span class="question-title">문제 번호. 발문</span>` 형태로 작성.
                    - 객관식 선지는 `<div class="choices">` 안에 작성.
                    
                    **[지시 4] 정답 및 해설**
                    - 문서 맨 마지막에 `<div class="answer-sheet">`를 열고 정답을 작성.
                    - 문제 순서대로 번호를 매겨서 해설 작성.
                    """
                else:
                    # [직접 입력 모드] -> 지문은 내가 줄게, 넌 읽기만 해!
                    prompt = f"""
                    당신은 수능 국어 출제위원입니다.
                    아래 지문을 읽고 문제를 출제하시오.
                    
                    [지문 시작]
                    {current_manual_passage}
                    [지문 끝]
                    
                    **[중요] 지문을 다시 출력하지 마시오.** (지문은 이미 있음)
                    
                    **[지시 1] 문제 출제**
                    - 위 지문을 바탕으로 아래 문제들을 출제하시오.
                    {reqs_str}
                    
                    **[지시 2] 형식 엄수 (HTML)**
                    - 각 문제는 `<div class="question-box">` 안에 `<span class="question-title">문제 번호. 발문</span>` 형태로 작성.
                    - 객관식 선지는 `<div class="choices">` 안에 작성.
                    
                    **[지시 3] 정답 및 해설**
                    - 문서 맨 마지막에 `<div class="answer-sheet">`를 열고 정답을 작성.
                    """

                # 3. AI 호출
                response = model.generate_content(prompt)
                ai_output = response.text.replace("```html", "").replace("```", "").strip()

                # 4. 결과 조립 (Python이 HTML 완성)
                final_html = HTML_HEAD
                
                # 헤더
                final_html += f"<h1>사계국어 비문학 모의고사</h1><h2>[{current_domain}] {current_topic}</h2>"
                final_html += "<div class='time-box'>⏱️ 목표 시간: 10분</div>"
                
                # 지문 결합
                if current_d_mode == "직접 입력":
                    # 직접 입력 모드면 파이썬이 지문을 HTML로 포장해서 넣어줌
                    formatted_passage = f'<div class="passage">{current_manual_passage.replace(chr(10), "<br>")}</div>'
                    final_html += formatted_passage
                else:
                    # AI 생성 모드면 AI가 만든 지문(<div> 포함)이 ai_output 안에 들어있음
                    pass 

                final_html += ai_output
                final_html += HTML_TAIL
                
                # 5. 결과 저장
                st.session_state.generated_result = {
                    "full_html": final_html,
                    "type": "non_fiction",
                    "domain": current_domain,
                    "topic": current_topic
                }
                
                st.rerun()

            except Exception as e:
                st.error(f"생성 중 오류가 발생했습니다: {e}")

# ==========================================
# 🚀 결과 출력 및 다운로드
# ==========================================
if 'generated_result' in st.session_state and st.session_state.generated_result:
    res = st.session_state.generated_result
    
    st.divider()
    st.subheader("✅ 생성 완료")
    
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("🔄 다시 만들기"):
            st.session_state.generated_result = None
            st.rerun()
            
    with c2:
        st.download_button(
            "📥 HTML 다운로드",
            res["full_html"],
            file_name=f"{res['topic']}_모의고사.html",
            mime="text/html"
        )
        
    # 미리보기
    st.components.v1.html(res["full_html"], height=800, scrolling=True)


# 앱 실행 로직
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "⚡ 비문학 문제 제작"

st.title("📚 사계국어 AI 모의고사")
st.markdown("---")

col1, col2 = st.columns([1, 3])
with col1:
    mode = st.radio("모드 선택", ["⚡ 비문학 문제 제작"], key="main_mode_radio")

with col2:
    non_fiction_app()
