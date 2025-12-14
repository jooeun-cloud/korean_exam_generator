import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import re 
import os
from docx import Document
from io import BytesIO
from docx.shared import Inches
from docx.shared import Pt
import time

# ==========================================
# [설정] API 키 연동
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "DUMMY_API_KEY_FOR_LOCAL_TEST") 

st.set_page_config(page_title="사계국어 AI 모의고사 제작 시스템", page_icon="📚", layout="wide")

# ==========================================
# [초기화] Session State 설정 (AttributeError 방지)
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
        
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 30px;
            padding: 10px 20px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fdfdfd; font-size: 0.95em;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }

        .time-blank {
            display: inline-block; width: 60px; border-bottom: 1px solid #000;
            margin: 0 5px; height: 1em; vertical-align: middle;
        }
        
        h3 { 
            margin-top: 5px; margin-bottom: 15px; font-size: 1.6em; 
            color: #2e8b57; border-bottom: 2px solid #2e8b57;
            padding-bottom: 10px; font-weight: bold;
        }
        
        h4 {
            margin-top: 5px; margin-bottom: 10px; font-size: 1.8em; 
            color: #00008b; border-bottom: 3px solid #00008b; 
            padding-bottom: 8px; font-weight: bold; 
        }

        .type-box { 
            border: 2px solid #999; padding: 20px; margin-bottom: 20px; 
            border-radius: 10px; page-break-inside: avoid; 
        }

        .passage { 
            font-size: 10pt; border: 1px solid #000; padding: 25px; 
            margin-bottom: 30px; background-color: #fff; 
            line-height: 1.8; text-align: justify;
        }
        .passage p { text-indent: 1em; margin-bottom: 10px; display: block; }
        
        .passage-label {
            font-weight: bold; font-size: 1.1em; color: #fff;
            display: inline-block; background-color: #000;
            padding: 2px 8px; border-radius: 4px; margin-right: 5px; margin-bottom: 10px;
        }
        
        .summary-blank { 
            display: block; margin-top: 10px; margin-bottom: 20px; padding: 0 10px; 
            height: 100px; border: 1px solid #777; border-radius: 5px;
            color: #555; font-size: 0.9em; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
        }

        .source-info { 
            text-align: right; font-size: 0.85em; color: #666; margin-bottom: 30px; 
            font-style: italic; 
        }

        .question-box { margin-bottom: 25px; page-break-inside: avoid; }

        .question-box b, .question-box strong {
            font-weight: 900; display: inline-block; margin-bottom: 5px;
        }
        
        .example-box { 
            border: 1px solid #333; padding: 15px; margin: 10px 0; 
            background-color: #f7f7f7; font-size: 0.95em; font-weight: normal;
        }

        .choices { 
            padding-left: 20px; text-indent: -20px; margin-left: 20px;
            padding-top: 10px; line-height: 1.4;
        }
        .choices div { margin-bottom: 5px; }
        
        .write-box { 
            margin-top: 15px; margin-bottom: 10px; height: 150px; 
            border: 1px solid #777; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; border-radius: 5px; 
        }

        .long-blank-line {
            display: block; border-bottom: 1px solid #000; 
            margin: 5px 0 15px 0; min-height: 1.5em; width: 95%; 
        }
        .answer-line-gap { 
            display: block; border-bottom: 1px solid #000;
            margin: 25px 0 25px 0; min-height: 1.5em; width: 95%;
        }

        .blank {
            display: inline-block; min-width: 60px; border-bottom: 1px solid #000;
            margin: 0 2px; vertical-align: bottom; height: 1.2em;
        }
        
        .analysis-table { 
            width: 100%; border-collapse: collapse; margin-top: 10px; 
            font-size: 0.95em; line-height: 1.4;
        }
        .analysis-table th, .analysis-table td { 
            border: 1px solid #000; padding: 8px; text-align: left;
        }
        .analysis-table th { 
            background-color: #e6e6fa; text-align: center; font-weight: bold;
        }
        .analysis-table .blank-row { height: 35px; }

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

def get_best_model():
    """Gemma-3를 최우선으로 사용하는 모델 선택 함수"""
    if "DUMMY" in GOOGLE_API_KEY: return 'models/gemma-3-27b-it'
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        priority_candidates = [
            'models/gemma-3-27b-it',
            'models/gemma-3-12b-it',
            'models/gemini-2.0-flash',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-001'
        ]
        return 'models/gemma-3-27b-it' # 강제 지정 (목록에 없어도 작동 확률 높음)
    except Exception: 
        return 'models/gemma-3-27b-it'

# ==========================================
# [DOCX 생성 함수]
# ==========================================
def set_table_borders(table):
    try:
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                for border_name in ('top', 'left', 'bottom', 'right'):
                    borders = OxmlElement(qn('w:tcBorders'))
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'single')
                    border.set(qn('w:sz'), '4')
                    border.set(qn('w:color'), 'auto')
                    borders.append(border)
                    tcPr.append(borders)
    except Exception:
        pass

def create_docx(html_content, file_name, current_topic, is_fiction=False):
    document = Document()
    clean_html_body = re.sub(r'.*?<body[^>]*>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_html_body = re.sub(r'<\/body>.*?<\/html>', '', clean_html_body, flags=re.DOTALL | re.IGNORECASE)
    
    # 제목 처리
    h1_match = re.search(r'<h1>(.*?)<\/h1>', clean_html_body, re.DOTALL)
    if h1_match:
        document.add_heading(re.sub(r'<[^>]+>', '', h1_match.group(1)).strip(), level=0)
    
    h2_match = re.search(r'<h2>(.*?)<\/h2>', clean_html_body, re.DOTALL)
    if h2_match:
        document.add_heading(re.sub(r'<[^>]+>', '', h2_match.group(1)).strip(), level=2)
        
    time_box_match = re.search(r'<div class="time-box">(.*?)<\/div>', clean_html_body, re.DOTALL)
    if time_box_match:
        document.add_paragraph(f"--- {re.sub(r'<[^>]+>', '', time_box_match.group(1)).strip()} ---")

    # 지문 처리
    passage_match = re.search(r'<div class="passage">(.*?)<\/div>', clean_html_body, re.DOTALL)
    passage_end_index = passage_match.end() if passage_match else -1
    
    if passage_match:
        document.add_heading("I. 지문", level=1)
        table = document.add_table(rows=1, cols=1)
        table.width = Inches(6.5)
        set_table_borders(table)
        cell = table.cell(0, 0)
        passage_html = passage_match.group(1).strip()
        
        # 지문 텍스트 간소화 처리
        clean_p_text = re.sub(r'<br\s*\/?>', '\n', passage_html)
        clean_p_text = re.sub(r'<[^>]+>', '', clean_p_text)
        cell.add_paragraph(clean_p_text)

    # 문제 및 해설 처리
    answer_sheet_match = re.search(r'<div class="answer-sheet">(.*?)<\/div>', clean_html_body, re.DOTALL)
    problem_block_end = answer_sheet_match.start() if answer_sheet_match else len(clean_html_body)
    
    problem_block_start = 0
    if passage_match:
        passage_div_end = clean_html_body.find('</div>', passage_match.end())
        if passage_div_end != -1 and passage_div_end < problem_block_end:
            problem_block_start = passage_div_end + len('</div>')
        else:
            problem_block_start = passage_match.end()
    elif time_box_match:
        problem_block_start = time_box_match.end()

    problem_block = clean_html_body[problem_block_start:problem_block_end].strip()
    
    if problem_block:
        document.add_heading("II. 문제", level=1)
        # HTML 태그 제거하고 텍스트만 추출 (간소화)
        clean_prob = re.sub(r'<[^>]+>', '\n', problem_block)
        clean_prob = re.sub(r'\n+', '\n', clean_prob).strip()
        document.add_paragraph(clean_prob)

    if answer_sheet_match:
        document.add_heading("III. 정답 및 해설", level=1)
        answer_text = re.sub(r'<[^>]+>', '\n', answer_sheet_match.group(1))
        answer_text = re.sub(r'\n+', '\n', answer_text).strip()
        document.add_paragraph(answer_text)

    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==========================================
# 🧩 비문학 문제 제작 함수
# ==========================================

def non_fiction_app():
    global GOOGLE_API_KEY
    
    # --- 사이드바 설정 ---
    current_d_mode = st.session_state.get('domain_mode_select', 'AI 생성')
    
    with st.sidebar:
        st.header("🛠️ 지문 입력 방식 선택")
        st.selectbox("지문 입력 방식", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.markdown("---")

        st.header("1️⃣ 지문 구성 및 주제 설정")
        
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""
        
        if current_d_mode == 'AI 생성':
            mode = st.radio("지문 구성 방식", ["단일 지문 (기본)", "주제 통합 (가) + (나)"], index=0, key="ai_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술"]
            
            if mode == "단일 지문 (기본)":
                domain = st.selectbox("문제 영역", domains, key="domain_select")
                topic = st.text_input("주제 입력", placeholder="예: 금리 인하 효과", key="topic_input")
                current_domain = domain
                current_topic = topic
            else:
                st.markdown("#### 🅰️ (가) 글 설정")
                domain_a = st.selectbox("[(가) 영역]", domains, key="dom_a")
                topic_a = st.text_input("[(가) 주제]", placeholder="예: 칸트의 미학", key="topic_a_input")
                st.markdown("#### 🅱️ (나) 글 설정")
                domain_b = st.selectbox("[(나) 영역]", domains, key="dom_b", index=7)
                topic_b = st.text_input("[(나) 주제]", placeholder="예: 현대 미술의 추상성", key="topic_b_input")
                current_domain = f"{domain_a} + {domain_b}"
                current_topic = f"(가) {topic_a} / (나) {topic_b}"
            
            difficulty = st.select_slider("난이도", ["하", "중", "상", "최상(LEET급)"], value="최상(LEET급)", key="difficulty_select")
            current_difficulty = difficulty
            current_mode = mode

        else: # 직접 입력
            mode = st.radio("지문 구성 방식", ["단일 지문", "주제 통합 (가) + (나)"], index=0, key="manual_mode")
            current_mode = mode
            current_domain = "사용자 지정"
            current_topic = "사용자 입력 지문"
            current_difficulty = "사용자 지정"

        st.markdown("---")
        st.header("2️⃣ 문제 유형 및 개수 선택")
        
        label_type1 = "1. 핵심 주장 요약 (서술형)" if current_mode.startswith("단일") else "1. (가),(나) 요약 및 연관성 서술"
        
        select_t1 = st.checkbox(label_type1, value=True, key="select_t1")
        select_t2 = st.checkbox("2. 내용 일치 O/X", key="select_t2")
        count_t2 = st.number_input(" - 문항 수", 1, 10, 2, key="t2") if select_t2 else 0
        select_t3 = st.checkbox("3. 빈칸 채우기", key="select_t3")
        count_t3 = st.number_input(" - 문항 수", 1, 10, 2, key="t3") if select_t3 else 0
        select_t4 = st.checkbox("4. 변형 문장 정오판단", key="select_t4")
        count_t4 = st.number_input(" - 문항 수", 1, 10, 2, key="t4") if select_t4 else 0
        select_t5 = st.checkbox("5. 객관식 (일치/불일치)", key="select_t5")
        count_t5 = st.number_input(" - 문항 수", 1, 10, 2, key="t5") if select_t5 else 0
        select_t6 = st.checkbox("6. 객관식 (추론)", key="select_t6")
        count_t6 = st.number_input(" - 문항 수", 1, 10, 2, key="t6") if select_t6 else 0
        select_t7 = st.checkbox("7. 객관식 (보기 적용 3점)", key="select_t7")
        count_t7 = st.number_input(" - 문항 수", 1, 10, 1, key="t7") if select_t7 else 0
        
        use_summary = st.checkbox("📌 지문 문단별 요약 훈련", value=False, key="select_summary")
        use_recommendation = st.checkbox(f"🌟 영역 맞춤 추천 문제 추가", value=False, key="select_recommendation")

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
            status.info(f"⚡ [{current_domain}] 출제 중... (Gemma-3 모델)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                # --- 프롬프트 구성 ---
                reqs = []
                if select_t1: reqs.append(f"""<div class="type-box"><h3>{label_type1}</h3><div class="question-box"><b>1. 핵심 내용을 요약하시오.</b><div class="write-box"></div></div></div>""")
                if select_t2: reqs.append(f"""<div class="type-box"><h3>내용 일치 O/X ({count_t2}문항)</h3>- 문항 끝에 (O/X) 표시 필수.</div>""")
                if select_t3: reqs.append(f"""<div class="type-box"><h3>빈칸 채우기 ({count_t3}문항)</h3>- 문장에 <span class='blank'></span> 태그 사용.</div>""")
                if select_t4: reqs.append(f"""<div class="type-box"><h3>변형 문장 정오판단 ({count_t4}문항)</h3></div>""")
                
                # [수정] 객관식 5지 선다 및 줄바꿈 지시 강화, 개수만큼 생성 지시 강화
                if select_t5: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 일치/불일치 ({count_t5}문항)</h3>
                        - **[지시]**: 지문 내용을 바탕으로 일치/불일치 여부를 묻는 객관식 문제 **{count_t5}문항**을 출제하시오.
                        - **[형식]**: 각 문항은 독립적인 `<div class="question-box">`로 감싸고, 발문, 그리고 **반드시 5개의 선지(①~⑤)**를 `<div class='choices'>` 안에 각 선지마다 `<div>① ...</div>` 태그로 감싸서 <b>줄바꿈</b>되도록 작성하시오.
                    </div>""")
                if select_t6: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 추론 ({count_t6}문항)</h3>
                        - **[지시]**: 지문 내용을 바탕으로 추론하는 객관식 문제 **{count_t6}문항**을 출제하시오.
                        - **[형식]**: 각 문항은 독립적인 `<div class="question-box">`로 감싸고, 발문, 그리고 **반드시 5개의 선지(①~⑤)**를 `<div class='choices'>` 안에 각 선지마다 `<div>① ...</div>` 태그로 감싸서 <b>줄바꿈</b>되도록 작성하시오.
                    </div>""")
                if select_t7: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 보기 적용 ({count_t7}문항)</h3>
                        - **[지시]**: `<div class="example-box">` 태그를 사용하여 보기를 작성하고, 이를 적용하여 푸는 객관식 문제 **{count_t7}문항**을 출제하시오.
                        - **[형식]**: 각 문항은 독립적인 `<div class="question-box">`로 감싸고, 발문, 그리고 **반드시 5개의 선지(①~⑤)**를 `<div class='choices'>` 안에 각 선지마다 `<div>① ...</div>` 태그로 감싸서 <b>줄바꿈</b>되도록 작성하시오.
                    </div>""")
                if use_recommendation: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>🌟 영역 맞춤 추천 문제</h3>
                        - **[지시]**: 5지 선다 객관식 1문항을 출제하시오.
                        - **[형식]**: `<div class="question-box">`로 감싸고, 선지는 `<div class='choices'>` 안에 각 선지마다 `<div>① ...</div>` 태그로 감싸서 <b>줄바꿈</b>되도록 작성하시오.
                    </div>""")
                
                reqs_content = "\n".join(reqs)
                
                # [수정] 지문 요약 및 출력 지시 강화 (빈칸으로 두고 정답지에 표시)
                summary_inst_passage = ""
                summary_inst_answer = ""
                if use_summary:
                    summary_inst_passage = """
                    - **[필수]** 지문 작성 시, 각 문단(`<p>...</p>`)이 끝날 때마다 **반드시** `<div class='summary-blank'>📝 문단 요약 : (빈칸)</div>` 태그를 바로 뒤에 삽입하여 출력하시오. **절대 여기에 요약 내용을 미리 적지 마시오.**
                    """
                    summary_inst_answer = """
                    - 정답지 맨 앞부분에 **<I. 문단별 핵심 요약 정답>** 섹션을 만들고, 각 문단의 핵심 요약 내용을 순서대로 작성하시오.
                    """

                # 지문 처리 지시 (AI 모드 vs 직접 입력 모드)
                if current_d_mode == 'AI 생성':
                    passage_inst = f"""
                    **[지시 1] 지문 작성 (필수)**
                    - 주제: {current_topic} ({current_domain})
                    - 난이도: {current_difficulty}
                    - **반드시** 수능형 지문을 작성하고 `<div class="passage">` 태그로 감싸서 출력하시오.
                    - 문단 구분은 `<p>` 태그를 사용하시오.
                    {summary_inst_passage}
                    """
                else:
                    passage_inst = f"""
                    **[지시 1] 지문 확인**
                    - 아래 지문을 읽고 문제를 출제하시오. **지문 본문은 다시 출력하지 마시오.**
                    [지문 시작]
                    {current_manual_passage}
                    [지문 끝]
                    """

                prompt = f"""
                당신은 수능 국어 출제 위원장입니다.
                
                **[출력 형식: HTML <body> 내부 태그만 작성]**
                
                {passage_inst}
                
                **[지시 2] 문제 출제**
                다음 유형에 맞춰 문제를 출제하시오.
                {reqs_content}
                
                **[지시 3] 정답 및 해설 (필수)**
                - 문서 맨 마지막에 `<div class="answer-sheet">`를 열고 정답을 작성하시오.
                {summary_inst_answer}
                - **반드시** 위에서 출제한 문제 순서대로 번호를 매겨 해설하시오.
                - 형식: **[문제번호] 정답** / **해설** / **오답분석**
                """
                
                response = model.generate_content(prompt)
                clean_content = response.text.replace("```html", "").replace("```", "").strip()
                
                # HTML 조립
                full_html = HTML_HEAD
                full_html += f"<h1>사계국어 비문학 모의고사</h1><h2>[{current_domain}] {current_topic}</h2>"
                full_html += "<div class='time-box'>⏱️ 목표 시간: 10분</div>"
                
                # 직접 입력 모드일 경우 지문을 Python에서 삽입
                if current_d_mode == '직접 입력':
                    # [수정] 직접 입력 모드에서도 요약 칸 기능 적용 (빈칸 유지)
                    def add_summary_box(text):
                        if not use_summary: return f"<p>{text}</p>"
                        return f"<p>{text}</p><div class='summary-blank'>📝 문단 요약 : </div>"

                    if current_mode == '단일 지문':
                        paragraphs = [p.strip() for p in current_manual_passage.split('\n\n') if p.strip()]
                        formatted_p = "".join([add_summary_box(p) for p in paragraphs])
                        formatted_p = f'<div class="passage">{formatted_p}</div>'
                    else:
                        paragraphs_a = [p.strip() for p in st.session_state.manual_passage_input_a.split('\n\n') if p.strip()]
                        formatted_a = "".join([add_summary_box(p) for p in paragraphs_a])
                        
                        paragraphs_b = [p.strip() for p in st.session_state.manual_passage_input_b.split('\n\n') if p.strip()]
                        formatted_b = "".join([add_summary_box(p) for p in paragraphs_b])
                        
                        formatted_p = f'<div class="passage"><b>(가)</b><br>{formatted_a}<br><br><b>(나)</b><br>{formatted_b}</div>'
                    full_html += formatted_p
                
                full_html += clean_content
                full_html += HTML_TAIL
                
                # 결과 저장
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "clean_content": clean_content,
                    "domain": current_domain,
                    "topic": current_topic,
                    "type": "non_fiction"
                }
                status.success("✅ 생성 완료!")
                st.session_state.generation_requested = False

            except Exception as e:
                status.error(f"오류 발생: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 📖 문학 문제 제작 함수
# ==========================================

def fiction_app():
    global GOOGLE_API_KEY
    
    with st.sidebar:
        st.header("1️⃣ 작품 정보")
        work_name = st.text_input("작품명", key="fiction_work_name_input")
        author_name = st.text_input("작가명", key="fiction_author_name_input")
        
        st.markdown("---")
        st.header("2️⃣ 출제 유형")
        count_t1 = st.number_input("1. 어휘 문제", 0, 20, 5, key="fiction_c_t1")
        count_t2 = st.number_input("2. 서술형 심화", 0, 20, 3, key="fiction_c_t2")
        count_t3 = st.number_input("3. 객관식", 0, 10, 3, key="fiction_c_t3")
        
        select_t4 = st.checkbox("4. 인물 정리 표", key="fiction_select_t4")
        select_t5 = st.checkbox("5. 상황 요약", key="fiction_select_t5")
        select_t6 = st.checkbox("6. 인물 관계도", key="fiction_select_t6")
        select_t7 = st.checkbox("7. 갈등 구조", key="fiction_select_t7")
        
        count_t8 = st.number_input("8. 사용자 지정", 0, 10, 0, key="fiction_c_t8")
        if count_t8 > 0:
            custom_title_t8 = st.text_input("유형 8 제목", key="fiction_title_t8")

    if st.session_state.generation_requested:
        current_novel_text = st.session_state.fiction_novel_text_input_area
        
        if not current_novel_text or not work_name:
            st.warning("작품명과 본문을 입력해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info("⚡ 문학 분석 생성 중...")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                # 프롬프트 구성
                reqs = []
                if count_t1 > 0: reqs.append(f"- 어휘 문제 {count_t1}문항 (단답형)")
                if count_t2 > 0: reqs.append(f"- 서술형 심화 문제 {count_t2}문항")
                if count_t3 > 0: reqs.append(f"- 객관식 문제 {count_t3}문항 (5지 선다). 선지는 `<div class='choices'>` 안에 각 선지마다 `<div>① ...</div>` 태그로 감싸서 줄바꿈.")
                if select_t4: reqs.append("- 주요 등장인물 정리 표 작성")
                if select_t5: reqs.append("- 소설 속 상황 요약")
                if select_t6: reqs.append("- 인물 관계도 및 갈등 서술")
                if select_t7: reqs.append("- 핵심 갈등 구조 및 심리 분석")
                if count_t8 > 0: reqs.append(f"- {st.session_state.fiction_title_t8} {count_t8}문항")
                
                reqs_str = "\n".join(reqs)
                
                prompt = f"""
                당신은 수능 문학 출제위원입니다.
                작품: {work_name} ({author_name})
                
                **[지시 1] 지문 읽기**
                아래 텍스트를 분석하시오. (지문은 출력하지 마시오)
                {current_novel_text}
                
                **[지시 2] 문제 출제**
                아래 유형대로 HTML 형식으로 문제를 출제하시오.
                {reqs_str}
                
                **[지시 3] 태그 규칙**
                - 문제는 `<div class="question-box">` 사용.
                - 객관식 선지는 `<div class="choices">` 사용. 각 선지는 `<div>`로 감싸 줄바꿈.
                
                **[지시 4] 정답 및 해설**
                - 문서 맨 마지막에 `<div class="answer-sheet">`를 열고 정답을 작성하시오.
                """
                
                response = model.generate_content(prompt)
                clean_content = response.text.replace("```html", "").replace("```", "").strip()
                
                # HTML 조립 (지문은 Python이 삽입)
                full_html = HTML_HEAD
                full_html += f"<h1>{work_name} 분석 학습지</h1><h2>{author_name}</h2>"
                full_html += f'<div class="passage">{current_novel_text.replace(chr(10), "<br>")}</div>'
                full_html += clean_content
                full_html += HTML_TAIL
                
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "clean_content": clean_content,
                    "domain": work_name,
                    "topic": author_name,
                    "type": "fiction"
                }
                status.success("✅ 생성 완료!")
                st.session_state.generation_requested = False
                
            except Exception as e:
                status.error(f"오류: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 🚀 메인 실행 로직
# ==========================================
def display_results():
    if st.session_state.generated_result:
        res = st.session_state.generated_result
        st.markdown("---")
        st.subheader("📊 생성 결과")
        
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("🔄 다시 생성"):
                st.session_state.generated_result = None
                st.session_state.generation_requested = True
                st.rerun()
        with c2:
            st.download_button("📥 HTML 다운로드", res["full_html"], f"{res['domain']}.html", "text/html")
        with c3:
            docx = create_docx(res["full_html"], "result.docx", res["topic"])
            st.download_button("📄 워드 다운로드", docx, f"{res['domain']}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
        st.components.v1.html(res["full_html"], height=800, scrolling=True)

# 앱 시작 (초기화 코드)
if 'app_mode' not in st.session_state: st.session_state.app_mode = "⚡ 비문학 문제 제작"

st.title("📚 사계국어 AI 모의고사 제작 시스템")
st.markdown("---")

col_L, col_R = st.columns([1.5, 3])

with col_L:
    st.radio("모드 선택", ["⚡ 비문학 문제 제작", "📖 문학 문제 제작"], key="app_mode")

with col_R:
    if st.session_state.app_mode == "⚡ 비문학 문제 제작":
        st.header("⚡ 비문학 모의평가")
        
        # 직접 입력 모드일 때 메인 화면에 입력창 표시
        if st.session_state.get("domain_mode_select") == "직접 입력":
            current_manual_mode = st.session_state.get("manual_mode", "단일 지문")
            if current_manual_mode == "단일 지문":
                st.text_area("지문 입력", height=300, key="manual_passage_input_col_main")
            else:
                c1, c2 = st.columns(2)
                with c1: st.text_area("(가) 지문", height=300, key="manual_passage_input_a")
                with c2: st.text_area("(나) 지문", height=300, key="manual_passage_input_b")
        
        if st.button("🚀 모의고사 생성", key="run_non_fiction"):
            st.session_state.generation_requested = True
        
        non_fiction_app()

    else: # 문학
        st.header("📖 문학 심층 분석")
        st.text_area("소설 본문 입력", height=300, key="fiction_novel_text_input_area")
        
        if st.button("🚀 분석 자료 생성", key="run_fiction"):
            st.session_state.generation_requested = True
            
        fiction_app()

display_results()
