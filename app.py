import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import re 
import os
from docx import Document
from io import BytesIO
from docx.shared import Inches, Pt
import time

# ==========================================
# [설정] 페이지 기본 설정 (반드시 가장 먼저 실행)
# ==========================================
st.set_page_config(page_title="사계국어 모의고사 시스템", page_icon="📚", layout="wide")

# ==========================================
# [설정] API 키 연동
# ==========================================
try:
    # 스트림릿 클라우드 배포 시 secrets 사용
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
    # 로컬 환경 변수 등 Fallback
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "") 

# ==========================================
# [초기화] Session State 설정
# ==========================================
if 'generation_requested' not in st.session_state:
    st.session_state.generation_requested = False

if 'generated_result' not in st.session_state:
    st.session_state.generated_result = None

if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "⚡ 비문학 문제 제작"

# ==========================================
# [공통 HTML/CSS 정의]
# ==========================================

HTML_HEAD = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <style>
        body { 
            font-family: 'Malgun Gothic', 'Batang', serif; 
            padding: 40px; 
            max-width: 850px; 
            margin: 0 auto; 
            line-height: 1.8; 
            color: #000; 
            font-size: 10.5pt;
        }
        
        h1 { text-align: center; margin-bottom: 10px; font-size: 24px; font-weight: bold; letter-spacing: -1px; }
        h2 { text-align: center; margin-top: 0; margin-bottom: 40px; font-size: 16px; color: #555; }
        
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 30px;
            padding: 8px 25px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fff; font-size: 0.95em;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        .time-blank {
            display: inline-block;
            width: 60px;
            border-bottom: 1px solid #000;
            margin-left: 5px;
            vertical-align: bottom;
        }

        /* 지문 스타일 */
        .passage { 
            font-size: 10.5pt; border: 1px solid #444; padding: 30px; 
            margin-bottom: 40px; background-color: #fff; 
            line-height: 1.9; text-align: justify;
        }
        .passage p { text-indent: 0.7em; margin-bottom: 15px; }
        
        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        h3 { font-size: 1.2em; color: #000; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px; font-weight: bold; }

        /* 문제 박스 */
        .question-box { margin-bottom: 40px; page-break-inside: avoid; }
        .question-text { font-weight: bold; margin-bottom: 15px; display: block; font-size: 1.1em; word-break: keep-all;}

        /* 보기 박스 */
        .example-box { 
            border: 1px solid #444; 
            padding: 15px; 
            margin: 15px 0 20px 0; 
            background-color: #fff; 
            font-size: 0.95em; 
            position: relative;
        }
        .example-box::before {
            content: "< 보 기 >";
            display: block;
            text-align: center;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }

        /* 선지 스타일 */
        .choices { 
            margin-top: 15px; 
            font-size: 1em; 
            margin-left: 15px; 
        }
        .choices div { 
            margin-bottom: 8px; 
            padding-left: 15px; 
            text-indent: -15px; 
            cursor: pointer;
        }
        .choices div:hover { background-color: #f8f9fa; }

        /* 서술형/요약 칸 */
        .write-box { 
            margin-top: 15px; height: 120px; 
            border: 1px solid #ccc; border-radius: 4px;
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
        }

        /* 문단 요약 빈칸 스타일 (높이 확장) */
        .summary-blank {
            border: 1px dashed #aaa; padding: 15px; margin: 15px 0 25px 0;
            min-height: 100px;
            color: #666; font-size: 0.9em; background-color: #fcfcfc;
            font-weight: bold; display: flex; align-items: flex-start;
        }

        /* 빈칸 채우기 스타일 */
        .blank {
            display: inline-block;
            min-width: 80px; 
            border-bottom: 1.5px solid #000;
            margin: 0 5px;
            height: 1.2em;
            vertical-align: middle;
        }

        /* 정답 및 해설 */
        .answer-sheet { 
            background: #f8f9fa; padding: 40px; margin-top: 60px; 
            border-top: 4px double #333; 
            page-break-before: always; 
        }
        .ans-main-title {
            font-size: 1.6em; font-weight: bold; text-align: center; 
            margin-bottom: 40px; padding-bottom: 15px; 
            border-bottom: 3px double #999; color: #333;
        }
        .ans-item { 
            margin-bottom: 50px; 
            border-bottom: 1px dashed #ccc; 
            padding-bottom: 30px; 
        }
        
        .ans-type-badge { 
            display: inline-block; 
            background-color: #555; 
            color: #fff; 
            padding: 4px 12px; 
            border-radius: 15px; 
            font-size: 0.85em; 
            font-weight: bold; 
            margin-bottom: 12px; 
        }
        
        .ans-num { 
            font-weight: bold; 
            color: #d63384; 
            font-size: 1.3em; 
            display: block; 
            margin-bottom: 15px; 
        }
        
        .ans-content-title {
            font-weight: bold;
            color: #2c3e50;
            margin-top: 20px;
            margin-bottom: 8px;
            font-size: 1.05em;
            display: block;
            border-left: 4px solid #2c3e50;
            padding-left: 10px;
        }
        
        .ans-text { 
            display: block; 
            margin-left: 5px; 
            color: #333; 
            line-height: 1.8; 
        }
        
        .ans-wrong-box {
            background-color: #fff;
            border: 1px solid #ddd;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            color: #555;
        }

        .summary-ans-box { 
            background-color: #e3f2fd; 
            padding: 25px; 
            margin-bottom: 50px; 
            border-radius: 10px; 
            border: 1px solid #90caf9; 
        }
        .summary-ans-title {
            font-weight: bold; color: #1565c0; font-size: 1.2em; 
            margin-bottom: 15px; display: block; text-align: center;
            border-bottom: 1px solid #90caf9; padding-bottom: 10px;
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

def get_best_model():
    """사용자가 요청한 Gemma-3 27B IT 모델을 최우선으로 사용"""
    return 'models/gemma-3-27b-it'

# ==========================================
# [DOCX 생성 함수]
# ==========================================
def create_docx(html_content, file_name, current_topic):
    document = Document()
    style = document.styles['Normal']
    style.font.name = 'Batang'
    style.font.size = Pt(10)

    # HTML 태그 제거 및 텍스트 추출 (간소화)
    clean_text = re.sub(r'<[^>]+>', '\n', html_content)
    clean_text = re.sub(r'\n+', '\n', clean_text).strip()
    
    document.add_heading("사계국어 모의고사", 0)
    document.add_heading(current_topic, 1)
    document.add_paragraph(clean_text)

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==========================================
# 🧩 비문학 문제 제작 함수
# ==========================================

def non_fiction_app():
    global GOOGLE_API_KEY
    
    current_d_mode = st.session_state.get('domain_mode_select', 'AI 생성')
    
    with st.sidebar:
        st.header("🛠️ 지문 입력 방식")
        st.selectbox("방식 선택", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.markdown("---")

        st.header("1️⃣ 지문 및 주제 설정")
        
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""
        # 기본값 초기화 (오류 방지)
        current_mode = "단일 지문"
        
        if current_d_mode == 'AI 생성':
            mode = st.radio("구성", ["단일 지문", "주제 통합"], key="ai_mode")
            domains = ["인문", "사회", "과학", "기술", "예술"]
            
            if mode == "단일 지문":
                domain = st.selectbox("영역", domains, key="domain_select")
                topic = st.text_input("주제", placeholder="예: 금리 인하", key="topic_input")
                current_domain = domain
                current_topic = topic
            else:
                current_domain = "주제 통합"
                current_topic = st.text_input("주제", placeholder="예: (가) 공리주의 / (나) 의무론", key="topic_input_mix")
            
            difficulty = st.select_slider("난이도", ["중", "상", "최상"], value="최상")
            current_difficulty = difficulty
            current_mode = mode

        else: # 직접 입력
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합"], key="manual_mode")
            current_mode = mode
            current_domain = "사용자 입력"
            current_topic = "사용자 지문"
            current_difficulty = "사용자 지정"

        st.markdown("---")
        st.header("2️⃣ 문제 유형 및 개수 선택")
        
        if current_mode.startswith("단일"):
            label_type1 = "1. 핵심 주장 요약 (서술형)"
        else:
            label_type1 = "1. (가),(나) 요약 및 연관성 서술"
        
        select_t1 = st.checkbox(label_type1, value=True, key="select_t1")
        
        select_t2 = st.checkbox("2. 내용 일치 O/X", key="select_t2")
        count_t2 = st.number_input(" - 문항 수", 1, 10, 2, key="t2") if select_t2 else 0
        
        select_t3 = st.checkbox("3. 빈칸 채우기", key="select_t3")
        count_t3 = st.number_input(" - 문항 수", 1, 10, 2, key="t3") if select_t3 else 0
        
        select_t4 = st.checkbox("4. 변형 문장 정오판단", key="select_t4")
        count_t4 = st.number_input(" - 문항 수", 1, 10, 2, key="t4") if select_t4 else 0
        
        select_t5 = st.checkbox("5. 객관식 (일치/불일치)", value=True, key="select_t5")
        count_t5 = st.number_input(" - 문항 수", 1, 10, 2, key="t5") if select_t5 else 0
        
        select_t6 = st.checkbox("6. 객관식 (추론)", value=True, key="select_t6")
        count_t6 = st.number_input(" - 문항 수", 1, 10, 2, key="t6") if select_t6 else 0
        
        select_t7 = st.checkbox("7. 객관식 (보기 적용 3점)", value=True, key="select_t7")
        count_t7 = st.number_input(" - 문항 수", 1, 10, 1, key="t7") if select_t7 else 0
        
        use_summary = st.checkbox("📌 문단별 요약 훈련 칸 생성", value=True, key="select_summary")

    # --- 메인 실행 로직 ---
    if st.session_state.generation_requested:
        
        # 직접 입력 지문 가져오기
        if current_d_mode == '직접 입력':
            if current_mode == '단일 지문':
                current_manual_passage = st.session_state.get("manual_passage_input_col_main", "")
            else:
                p_a = st.session_state.get("manual_passage_input_a", "")
                p_b = st.session_state.get("manual_passage_input_b", "")
                current_manual_passage = f"[가] 지문:\n{p_a}\n\n[나] 지문:\n{p_b}"

        # 유효성 검사
        if current_d_mode == 'AI 생성' and not current_topic:
            st.warning("주제를 입력해주세요.")
            st.session_state.generation_requested = False
        elif current_d_mode == '직접 입력' and not current_manual_passage.strip():
            st.warning("지문을 입력해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡ [{current_domain}] 출제 중입니다... (Gemma-3 모델 구동 중)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                # --- 프롬프트 구성 ---
                reqs = []
                
                # 1. 요약 문제
                if select_t1: 
                    reqs.append(f"""
                    <div class="question-box">
                        <span class="question-text">1. {label_type1}</span>
                        - (주의: 반드시 위 지문의 내용을 바탕으로 요약하시오.)
                        - **[필수]**: 답변을 미리 적지 말고, 학생이 직접 쓸 수 있도록 빈 칸(`<div class="write-box"></div>`)만 남겨두시오.
                        <div class="write-box"></div>
                    </div>
                    """)

                # 2. OX 문제
                if select_t2: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>내용 일치 O/X ({count_t2}문항)</h3>
                        - 위 지문의 세부 내용과 일치 여부를 묻는 O/X 문제를 {count_t2}개 출제하시오.
                        - 문항 끝에 ( O / X ) 표시를 포함하되, 정답은 표시하지 마시오.
                    </div>""")

                # 3. 빈칸 채우기
                if select_t3:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>빈칸 채우기 ({count_t3}문항)</h3>
                        - 위 지문의 핵심 어휘나 구절을 빈칸으로 만든 문제를 {count_t3}개 출제하시오.
                        - **[중요]**: 빈칸에는 정답을 절대 넣지 마시오. `<span class='blank'>&nbsp;&nbsp;&nbsp;&nbsp;</span>` 태그를 사용하여 **반드시 공백 밑줄**로 표시하시오. 학생이 풀어야 합니다.
                    </div>""")

                # 4. 변형 문장 정오판단
                if select_t4:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>변형 문장 정오판단 ({count_t4}문항)</h3>
                        - 위 지문의 문장을 살짝 변형하여 맞는지 틀리는지 판단하는 문제를 {count_t4}개 출제하시오.
                        - 문항 끝에 ( O / X ) 표시를 포함하시오.
                    </div>""")

                # 객관식 공통 템플릿
                mcq_template = """
                <div class="question-box">
                     <span class="question-text">[문제번호] [발문]</span>
                     <div class="choices">
                        <div>① [선지]</div>
                        <div>② [선지]</div>
                        <div>③ [선지]</div>
                        <div>④ [선지]</div>
                        <div>⑤ [선지]</div>
                     </div>
                </div>
                """

                # 5. 객관식 (일치)
                if select_t5: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: 세부 내용 파악 ({count_t5}문항)</h3>
                        - [지시] 위 지문의 내용과 일치/불일치를 묻는 5지 선다형 문제를 {count_t5}개 작성하시오.
                        - [형식] {mcq_template}
                    </div>""")

                # 6. 객관식 (추론)
                if select_t6: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: 추론 및 비판 ({count_t6}문항)</h3>
                        - [지시] 위 지문을 바탕으로 논리적으로 추론하거나 비판하는 5지 선다형 문제를 {count_t6}개 작성하시오.
                        - [형식] {mcq_template}
                    </div>""")

                # 7. 보기 적용
                if select_t7: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: [보기] 적용 문제 ({count_t7}문항) [3점]</h3>
                        - **[절대 금지]**: "다음 그림은...", "그래프는..." 등 시각 자료를 언급하거나 암시하지 마시오. AI는 이미지를 생성할 수 없습니다.
                        - **[필수]**: `<div class="example-box">` 태그 안에 **[보 기]**를 작성하시오.
                        - [보 기] 내용은 반드시 **구체적 사례(Case Study), 실험 과정의 줄글 묘사, 관련 신문 기사, 다른 학자의 견해(텍스트)** 등 텍스트로 된 자료여야 합니다.
                        - 위 지문의 원리를 이 [보기]의 텍스트 상황에 적용하는 3점짜리 고난도 문제를 {count_t7}개 작성하시오.
                        - [형식]
                        <div class="question-box">
                             <span class="question-text">[문제번호] 윗글을 바탕으로 [보기]를 이해한 내용으로 적절하지 않은 것은? [3점]</span>
                             <div class="example-box">
                                 (여기에 지문과 연관된 구체적 사례나 다른 관점의 텍스트를 작성)
                             </div>
                             <div class="choices">
                                <div>① ...</div>
                                <div>② ...</div>
                                <div>③ ...</div>
                                <div>④ ...</div>
                                <div>⑤ ...</div>
                             </div>
                        </div>
                    </div>""")
                
                reqs_content = "\n".join(reqs)
                
                # 요약 지시 설정
                summary_inst_passage = ""
                if use_summary:
                    summary_inst_passage = """
                    - 문단이 끝날 때마다 `<div class='summary-blank'>📝 문단 요약 연습: (이곳에 핵심 내용을 요약해보세요)</div>`를 삽입하시오.
                    - **중요**: 이 부분은 학생이 직접 푸는 공간이므로 내용은 비워두시오. 절대 요약 내용을 미리 적지 마시오.
                    """

                # 지문 처리 지시 (강화됨)
                passage_inst = ""
                user_passage_block = ""
                if current_d_mode == 'AI 생성':
                    passage_inst = f"""
                    **[Step 1] 지문 작성**
                    - 주제: {current_topic} ({current_domain})
                    - 난이도: {current_difficulty} (수능 비문학 스타일)
                    - 길이: 1800자 내외의 수능형 비문학 지문
                    - 형식: `<div class="passage">` 태그 안에 `<p>` 태그로 문단을 구분하여 작성.
                    {summary_inst_passage}
                    """
                else:
                    passage_inst = """
                    **[Step 1] 지문 인식 (매우 중요)**
                    - 아래 제공된 [사용자 입력 지문]을 끝까지 정독하고 분석하시오.
                    - **경고**: 문제 출제 시 절대 지문에 없는 내용을 상상하거나 외부 지식을 가져오지 마시오. 오직 아래 입력된 지문의 내용만을 근거로 출제해야 합니다.
                    - 지문 텍스트 자체는 결과물에 다시 출력하지 마시오.
                    """
                    user_passage_block = f"\n[사용자 입력 지문 시작]\n{current_manual_passage}\n[사용자 입력 지문 끝]\n"

                # 1단계: 문제 생성 프롬프트
                prompt_p1 = f"""
                당신은 대한민국 수능 국어 출제 위원장입니다. 
                아래 지시사항에 맞춰 완벽한 HTML 포맷의 모의고사 문제지를 생성하시오.

                **[전체 출력 형식]**
                - `<html>`, `<head>` 등은 생략하고 `<body>` 태그 내부의 내용만 출력하시오.
                - **중요**: 이 부분은 "학생용 문제지"입니다. **정답 및 해설은 아직 작성하지 마시오.** - **중요**: 빈칸 채우기, 요약하기 문제 등에 정답을 미리 채워넣지 마시오. 학생이 풀 수 있도록 빈칸으로 남겨두시오.

                {passage_inst}
                {user_passage_block}

                **[Step 2] 문제 출제**
                다음 유형에 맞춰 문제를 순서대로 출제하시오. 문항 번호를 매기시오.
                {reqs_content}
                """
                
                generation_config = GenerationConfig(max_output_tokens=8192, temperature=0.7)
                response_problems = model.generate_content(prompt_p1, generation_config=generation_config)
                html_problems = response_problems.text.replace("```html", "").replace("```", "").strip()

                # [중복 방지 1차] 직접 입력 모드인데 AI가 지문을 또 생성한 경우 제거
                if current_d_mode == '직접 입력':
                     html_problems = re.sub(r'<div class="passage">.*?</div>', '', html_problems, flags=re.DOTALL).strip()

                # ----------------------------------------------------------------
                # [2단계] 정답 및 해설 생성 (분리 호출)
                # ----------------------------------------------------------------
                summary_inst_answer = ""
                extra_passage_context = ""
                
                if use_summary:
                    if current_d_mode == '직접 입력':
                        # 문단 수 계산 (사용자 입력과 일치시키기 위함)
                        user_paras = [p for p in re.split(r'\n\s*\n', current_manual_passage.strip()) if p.strip()]
                        para_count = len(user_paras)
                        summary_prompt_add = f"""
                        - **[필수 - 최우선 작성]**: 정답표 맨 위에 `<div class="summary-ans-box">`를 만들고, **[문단별 요약 예시 답안]**을 작성하시오.
                        - **[매우 중요]**: 사용자가 입력한 지문은 정확히 **{para_count}개의 문단**으로 나누어져 있습니다. AI 마음대로 문단을 합치거나 나누지 말고, 입력된 {para_count}개 덩어리에 대해 각각 하나씩, 총 {para_count}개의 요약문을 작성하시오.
                        """
                        extra_passage_context = f"\n**[참고: 사용자 입력 지문 원문(문단 구분 중요)]**\n{current_manual_passage}\n"
                    else:
                        summary_prompt_add = """
                        - **[필수 - 최우선 작성]**: 정답표 맨 위에 `<div class="summary-ans-box">`를 만들고, **[문단별 요약 예시 답안]**을 작성하시오. 지문의 각 문단별 핵심 내용을 요약하여 리스트로 제시하시오.
                        """

                prompt_answers = f"""
                당신은 대한민국 수능 국어 출제 위원장입니다.
                
                아래는 방금 출제된 지문과 문제들입니다. 
                이 내용을 바탕으로 **정답 및 해설 섹션**(`<div class="answer-sheet">`...)만 완벽하게 작성하시오.

                {extra_passage_context}

                **[입력된 지문 및 문제]**
                {html_problems}

                **[지시사항]**
                - 문서 맨 마지막에 반드시 `<div class="answer-sheet">`를 생성하시오.
                - `<div class="answer-sheet">` 태그 바로 직후에 `<h2 class='ans-main-title'>정답 및 해설</h2>`를 출력하시오.
                {summary_prompt_add}
                - **[매우 중요 - 중복 방지]**: 위에서 입력받은 **지문과 문제(발문, 보기, 선지 등)를 결과에 절대 다시 적지 마시오.** 오직 정답과 해설 내용만 작성하시오.
                - **[주의] 해설 작성 시 토큰 낭비를 막기 위해 문제의 발문이나 보기를 절대 다시 적지 마시오. 문제 번호, 정답, 해설만 작성하시오.**
                - 절대 중간에 끊지 말고, 위에서 출제한 모든 문제(서술형, O/X, 객관식 포함)에 대한 정답과 상세 해설을 끝까지 작성하시오.
                - 해설이 짤리면 안 됩니다. 마지막 문제까지 완벽하게 작성하십시오.
                - **[형식 준수]**: 각 문제마다 아래 포맷을 따르시오.
                - **[시작 태그 필수]**: 답변은 반드시 `<div class="answer-sheet">` 태그로 시작해야 합니다. 다른 서론이나 텍스트를 붙이지 마시오.
                
                - **[해설 작성 규칙 (유형별 - 매우 중요)]**:
                  1. **객관식 문제 (추론, 비판, 보기 적용, 일치 등 5지선다형 전체)**:
                     - 반드시 `[객관식 추론]`, `[객관식 보기적용]` 등과 같이 문제 유형을 배지 형태로 명시하시오.
                     - **[중요] 보기 적용 문제도 반드시 오답 분석을 작성해야 합니다.**
                     - **1. 정답 상세 해설**: 정답인 이유를 지문의 근거를 들어 설명하시오.
                     - **2. 오답 상세 분석 (필수 - 생략 금지)**:
                       - "보기에 명시되어 있다", "지문과 일치한다"와 같은 단순한 서술은 **절대 금지**합니다.
                       - 각 오답 선지(①~⑤)별로 왜 답이 될 수 없는지 **"지문의 [몇 문단]에서 [어떤 내용]을 다루고 있으므로..."**와 같이 구체적인 근거를 들어 줄바꿈(`<br>`)하여 상세히 작성하시오.
                  2. **O/X 및 빈칸 채우기 문제**:
                     - 유형을 명시하고, **[오답 상세 분석] 항목을 아예 작성하지 마시오.** 오직 **[정답 상세 해설]**만 작성하시오.
                
                <div class="ans-item">
                    <div class="ans-type-badge">[문제유형 예: 객관식 보기적용]</div>
                    <span class="ans-num">[번호] 정답: ④</span>
                    <span class="ans-content-title">1. 정답 상세 해설</span>
                    <span class="ans-text">지문의 3문단에서 "~"라고 언급했으므로, 보기의 상황에 적용하면 ...가 된다. 따라서 적절하다.</span>
                    <!-- 객관식일 경우에만 아래 오답 상세 분석 작성 -->
                    <span class="ans-content-title">2. 오답 상세 분석</span>
                    <div class="ans-wrong-box">
                        <span class="ans-text">① (X): 1문단에서 ...라고 했으므로 틀린 진술이다.<br>
                        ② (X): 인과관계가 반대로 서술되었다.<br>
                        ③ (X): 지문에 언급되지 않은 내용이다.</span>
                    </div>
                </div>
                """
                
                # 해설 생성 시 temperature 낮춤 (간결하고 정확하게)
                generation_config_ans = GenerationConfig(max_output_tokens=8192, temperature=0.3)
                response_answers = model.generate_content(prompt_answers, generation_config=generation_config_ans)
                html_answers = response_answers.text.replace("```html", "").replace("```", "").strip()
                
                # [중복 방지 2차 - 강력 삭제] 정답 섹션 시작 전의 모든 내용 삭제
                if '<div class="answer-sheet">' in html_answers:
                    html_answers = html_answers[html_answers.find('<div class="answer-sheet">'):]
                else:
                    # 태그가 없으면 강제로 래핑 (비상시)
                    html_answers = '<div class="answer-sheet">' + html_answers + '</div>'

                # HTML 조립
                full_html = HTML_HEAD
                full_html += f"<h1>사계국어 모의고사</h1><h2>[{current_domain}] {current_topic}</h2>"
                full_html += "<div class='time-box'>⏱️ 소요 시간: <span class='time-blank'></span></div>"
                
                # 직접 입력 모드일 경우 지문을 Python에서 삽입
                if current_d_mode == '직접 입력':
                    def make_p_with_summary(text):
                        box = f"<p>{text}</p>"
                        if use_summary:
                            box += "<div class='summary-blank'>📝 문단 요약 연습: </div>"
                        return box

                    # 문단 나누기 (엔터 두번 기준 - 정규식 강화)
                    raw_paras = [p.strip() for p in re.split(r'\n\s*\n', current_manual_passage.strip()) if p.strip()]
                    formatted_paras = "".join([make_p_with_summary(p) for p in raw_paras])
                    
                    if current_mode == '단일 지문':
                        full_html += f'<div class="passage">{formatted_paras}</div>'
                    else:
                        full_html += f'<div class="passage">{formatted_paras}</div>'
                
                full_html += html_problems
                full_html += html_answers
                full_html += HTML_TAIL
                
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "domain": current_domain,
                    "topic": current_topic
                }
                status.success("✅ 생성 완료!")
                st.session_state.generation_requested = False

            except Exception as e:
                status.error(f"오류 발생: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 📖 문학 문제 제작 함수 (업데이트)
# ==========================================
def fiction_app():
    global GOOGLE_API_KEY
    with st.sidebar:
        st.header("1️⃣ 작품 정보")
        work_name = st.text_input("작품명", key="fic_name")
        author_name = st.text_input("작가명", key="fic_auth")
        st.markdown("---")
        st.header("2️⃣ 문제 유형")
        count_q = st.number_input("객관식 문제 수", 1, 10, 3, key="fic_q_count")
        select_bogey = st.checkbox("보기(외적 준거) 적용", value=True, key="fic_bogey")
        select_desc = st.checkbox("서술형(감상)", key="fic_desc")

    if st.session_state.generation_requested:
        text_input = st.session_state.fiction_novel_text_input_area
        if not text_input:
            st.warning("작품 내용을 입력하세요.")
            st.session_state.generation_requested = False
            return

        status = st.empty()
        status.info("⚡ 문학 문제 생성 중...")
        
        try:
            model = genai.GenerativeModel(get_best_model())
            
            # 문제 생성 (문학)
            prompt_1 = f"""
            당신은 수능 문학 출제위원입니다.
            작품: {work_name} ({author_name})
            본문: {text_input}
            
            다음 조건에 맞춰 HTML 포맷으로 문제만 출제하시오 (해설 제외).
            1. 5지 선다형 문제 {count_q}개.
            2. { '`<div class="example-box">`를 활용한 보기 적용 3점 문제 포함. 단, **그림이나 도표 언급 금지**. 대신 **비평문, 시대적 배경, 작가의 말 등 텍스트 자료**를 보기로 제시할 것.' if select_bogey else '' }
            3. { '서술형 감상 문제 1개 포함' if select_desc else '' }
            
            **[중요]**: 문제에 정답을 표시하지 마시오. 학생용 문제지입니다.
            형식: `<div class="question-box">...</div>`
            """
            res_1 = model.generate_content(prompt_1)
            html_q = res_1.text.replace("```html","").replace("```","").strip()
            
            # 해설 생성 (문학)
            prompt_2 = f"""
            위에서 출제한 문학 문제의 **정답 및 해설**을 작성하시오.
            입력된 문제: {html_q}
            작품 본문: {text_input}
            
            규칙:
            1. `<div class="answer-sheet">` 내부에 작성.
            2. **객관식 해설 필수**: 
               - [정답 상세 해설]: 지문의 근거를 들어 설명.
               - [오답 상세 분석]: 각 선지별로 왜 답이 아닌지 구체적 근거를 들어 줄바꿈하여 작성. "보기에 있다" 식의 단순 서술 금지.
            3. 서술형은 예시 답안 제시.
            """
            res_2 = model.generate_content(prompt_2)
            html_a = res_2.text.replace("```html","").replace("```","").strip()
            
            # 문학도 중복 방지 처리
            if '<div class="answer-sheet">' in html_a:
                html_a = html_a[html_a.find('<div class="answer-sheet">'):]
            else:
                html_a = '<div class="answer-sheet">' + html_a + '</div>'
            
            full_html = HTML_HEAD
            full_html += f"<h1>{work_name}</h1><h2>{author_name}</h2>"
            full_html += f'<div class="passage">{text_input.replace(chr(10), "<br>")}</div>'
            full_html += html_q + html_a + HTML_TAIL
            
            st.session_state.generated_result = {"full_html": full_html, "domain": "문학", "topic": work_name}
            status.success("완료")
            st.session_state.generation_requested = False
            
        except Exception as e:
            status.error(f"Error: {e}")
            st.session_state.generation_requested = False

# ==========================================
# 🚀 메인 실행 로직
# ==========================================
def display_results():
    if st.session_state.generated_result:
        res = st.session_state.generated_result
        st.markdown("---")
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("🔄 다시 생성"):
                st.session_state.generated_result = None
                st.session_state.generation_requested = True
                st.rerun()
        with c2:
            st.download_button("📥 HTML 저장", res["full_html"], "exam.html", "text/html")
        with c3:
            docx = create_docx(res["full_html"], "exam.docx", res["topic"])
            st.download_button("📄 Word 저장", docx, "exam.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
        st.components.v1.html(res["full_html"], height=800, scrolling=True)

# 앱 레이아웃
st.title("📚 사계국어 모의고사 제작 시스템")
st.markdown("---")

col_L, col_R = st.columns([1.5, 3])

with col_L:
    st.radio("모드 선택", ["⚡ 비문학 문제 제작", "📖 문학 문제 제작"], key="app_mode")

with col_R:
    if st.session_state.app_mode == "⚡ 비문학 문제 제작":
        st.header("⚡ 비문학 모의평가")
        if st.session_state.get("domain_mode_select") == "직접 입력":
            current_manual_mode = st.session_state.get("manual_mode", "단일 지문")
            if current_manual_mode == "단일 지문":
                st.text_area("지문 입력 (엔터 두번으로 문단 구분)", height=300, key="manual_passage_input_col_main")
            else:
                c1, c2 = st.columns(2)
                with c1: st.text_area("(가) 지문", height=300, key="manual_passage_input_a")
                with c2: st.text_area("(나) 지문", height=300, key="manual_passage_input_b")
        
        if st.button("🚀 모의고사 생성", key="run_non_fiction"):
            st.session_state.generation_requested = True
        
        non_fiction_app()

    else:
        st.header("📖 문학 심층 분석")
        st.text_area("작품 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 분석 생성", key="run_fiction"):
            st.session_state.generation_requested = True
        fiction_app()

display_results()
