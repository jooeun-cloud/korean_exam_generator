import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig # 설정 추가
import re 
import os
from docx import Document
from io import BytesIO
from docx.shared import Inches, Pt
import time

# ==========================================
# [설정] API 키 연동
# ==========================================
try:
    # 스트림릿 클라우드 배포 시 secrets 사용, 로컬 테스트 시 환경변수 혹은 직접 입력
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
    # 로컬 환경 변수 등 Fallback
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "") 

st.set_page_config(page_title="사계국어 AI 모의고사 시스템", page_icon="📚", layout="wide")

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
# [공통 HTML/CSS 정의] - 디자인 개선
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
            line-height: 1.7; 
            color: #000; 
            font-size: 10.5pt;
        }
        
        h1 { text-align: center; margin-bottom: 5px; font-size: 24px; font-weight: bold; }
        h2 { text-align: center; margin-top: 0; margin-bottom: 30px; font-size: 16px; color: #555; }
        
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 20px;
            padding: 5px 20px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fdfdfd; font-size: 0.9em;
        }

        /* 지문 스타일 (1단 변경) */
        .passage { 
            font-size: 10pt; border: 1px solid #000; padding: 25px; 
            margin-bottom: 30px; background-color: #fff; 
            line-height: 1.8; text-align: justify;
        }
        .passage p { text-indent: 0.5em; margin-bottom: 10px; }
        
        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        h3 { font-size: 1.1em; color: #000; border-bottom: 1px solid #000; padding-bottom: 5px; margin-bottom: 15px; }

        /* 문제 박스 */
        .question-box { margin-bottom: 30px; page-break-inside: avoid; }
        .question-text { font-weight: bold; margin-bottom: 10px; display: block; font-size: 1.05em; }

        /* 보기 박스 (수능 스타일) */
        .example-box { 
            border: 1px solid #000; 
            padding: 15px; 
            margin: 10px 0 15px 0; 
            background-color: #fff; 
            font-size: 0.95em; 
            position: relative;
        }
        .example-box::before {
            content: "< 보 기 >";
            display: block;
            text-align: center;
            font-weight: bold;
            color: #555;
            margin-bottom: 10px;
        }

        /* 선지 스타일 (들여쓰기 적용) */
        .choices { 
            margin-top: 10px; 
            font-size: 0.95em; 
            margin-left: 25px; /* 문제 안쪽으로 들여쓰기 */
        }
        .choices div { 
            margin-bottom: 6px; 
            padding-left: 10px; 
            text-indent: -10px; 
        }
        .choices div:hover { background-color: #f0f8ff; cursor: pointer; }

        /* 서술형/요약 칸 */
        .write-box { 
            margin-top: 10px; height: 100px; 
            border: 1px solid #ccc; border-radius: 4px;
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
        }

        /* 문단 요약 빈칸 스타일 */
        .summary-blank {
            border: 1px dashed #999; padding: 10px; margin: 10px 0;
            color: #555; font-size: 0.9em; background-color: #fafafa;
            font-weight: bold;
        }

        .blank {
            display: inline-block; width: 60px; border-bottom: 1px solid #000;
        }

        /* 정답 및 해설 */
        .answer-sheet { 
            background: #f8f9fa; padding: 30px; margin-top: 50px; 
            border-top: 2px solid #333; 
            page-break-before: always; 
        }
        .ans-header { font-size: 1.2em; font-weight: bold; margin-bottom: 15px; color: #333; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
        .ans-item { margin-bottom: 20px; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
        .ans-num { font-weight: bold; color: #d63384; font-size: 1.1em; }
        .ans-exp { display: block; margin-top: 5px; color: #333; line-height: 1.6; }
        .ans-wrong { display: block; margin-top: 5px; color: #666; font-size: 0.9em; background: #eee; padding: 5px; border-radius: 4px; }
        .summary-ans-box { background-color: #e8f4fd; padding: 15px; margin-bottom: 30px; border-radius: 5px; border: 1px solid #b6d4fe; }
        
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

def create_docx(html_content, file_name, current_topic):
    document = Document()
    
    # 스타일 설정
    style = document.styles['Normal']
    style.font.name = 'Batang'
    style.font.size = Pt(10)

    clean_html_body = re.sub(r'.*?<body[^>]*>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_html_body = re.sub(r'<\/body>.*?<\/html>', '', clean_html_body, flags=re.DOTALL | re.IGNORECASE)
    
    # 제목
    h1_match = re.search(r'<h1>(.*?)<\/h1>', clean_html_body, re.DOTALL)
    if h1_match:
        document.add_heading(re.sub(r'<[^>]+>', '', h1_match.group(1)).strip(), level=0)
    
    h2_match = re.search(r'<h2>(.*?)<\/h2>', clean_html_body, re.DOTALL)
    if h2_match:
        document.add_heading(re.sub(r'<[^>]+>', '', h2_match.group(1)).strip(), level=2)

    # 지문 처리
    passage_match = re.search(r'<div class="passage">(.*?)<\/div>', clean_html_body, re.DOTALL)
    if passage_match:
        document.add_heading("I. 지문", level=1)
        p_text = re.sub(r'<br\s*\/?>', '\n', passage_match.group(1))
        p_text = re.sub(r'<[^>]+>', '', p_text)
        document.add_paragraph(p_text.strip())

    # 문제 처리 (간략화된 텍스트 추출)
    document.add_heading("II. 문제 및 정답", level=1)
    
    # HTML 태그를 모두 제거하고 텍스트만 추출하는 방식 (복잡한 구조 유지 어려움)
    text_content = re.sub(r'<[^>]+>', '\n', clean_html_body)
    # 지문 부분 제거 (이미 추가했으므로)
    if passage_match:
        text_content = text_content.replace(re.sub(r'<[^>]+>', '\n', passage_match.group(1)), "")
    
    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
    
    # 문제 영역과 정답 영역 구분해서 넣기 (단순 텍스트 덤프)
    doc_body = "\n".join(lines)
    document.add_paragraph(doc_body)

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
        st.header("🛠️ 지문 입력 방식")
        st.selectbox("방식 선택", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.markdown("---")

        st.header("1️⃣ 지문 및 주제 설정")
        
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""
        
        if current_d_mode == 'AI 생성':
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합 (가)+(나)"], key="ai_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술"]
            
            if mode == "단일 지문":
                domain = st.selectbox("영역", domains, key="domain_select")
                topic = st.text_input("주제", placeholder="예: 양자역학의 불확정성", key="topic_input")
                current_domain = domain
                current_topic = topic
            else:
                domain_a = st.selectbox("(가) 영역", domains, key="dom_a")
                topic_a = st.text_input("(가) 주제", key="topic_a_input")
                domain_b = st.selectbox("(나) 영역", domains, key="dom_b", index=7)
                topic_b = st.text_input("(나) 주제", key="topic_b_input")
                current_domain = f"{domain_a} + {domain_b}"
                current_topic = f"(가) {topic_a} / (나) {topic_b}"
            
            difficulty = st.select_slider("난이도", ["하", "중", "상", "최상(LEET급)"], value="최상(LEET급)")
            current_difficulty = difficulty
            current_mode = mode

        else: # 직접 입력
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합 (가)+(나)"], key="manual_mode")
            current_mode = mode
            current_domain = "사용자 지정"
            current_topic = "사용자 입력 지문"
            current_difficulty = "사용자 지정"

        st.markdown("---")
        st.header("2️⃣ 문제 유형 및 개수 선택")
        
        # [수정] 모든 문제 유형 선택지 부활
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
        
        use_summary = st.checkbox("📌 문단별 요약 훈련 칸 생성", value=False, key="select_summary")

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
                
                # --- 프롬프트 구성 (핵심 수정 부분) ---
                reqs = []
                
                # 1. 요약 문제
                if select_t1: 
                    reqs.append(f"""
                    <div class="question-box">
                        <span class="question-text">1. {label_type1}</span>
                        <div class="write-box"></div>
                    </div>
                    """)

                # 2. OX 문제
                if select_t2: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>내용 일치 O/X ({count_t2}문항)</h3>
                        - 지문의 세부 정보와 일치하는지 묻는 문제를 {count_t2}개 출제하시오.
                        - 문항 끝에 ( O / X ) 표시를 포함하시오.
                    </div>""")

                # 3. 빈칸 채우기
                if select_t3:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>빈칸 채우기 ({count_t3}문항)</h3>
                        - 지문의 핵심 키워드나 문장을 빈칸으로 만든 문제를 {count_t3}개 출제하시오.
                        - 빈칸은 `<span class='blank'></span>` 태그를 사용하시오.
                    </div>""")

                # 4. 변형 문장 정오판단
                if select_t4:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>변형 문장 정오판단 ({count_t4}문항)</h3>
                        - 지문의 문장을 살짝 변형하여 맞는지 틀리는지 판단하는 문제를 {count_t4}개 출제하시오.
                        - 문항 끝에 ( O / X ) 표시를 포함하시오.
                    </div>""")

                # 5. 객관식 (일치)
                if select_t5: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: 세부 내용 파악 ({count_t5}문항)</h3>
                        - [지시] 지문의 내용과 일치/불일치를 묻는 5지 선다형 문제를 {count_t5}개 작성하시오.
                        - [형식]
                        <div class="question-box">
                             <span class="question-text">[문제번호] 윗글의 내용과 일치하지 않는 것은?</span>
                             <div class="choices">
                                <div>① ...</div>
                                <div>② ...</div>
                                ...
                                <div>⑤ ...</div>
                             </div>
                        </div>
                    </div>""")

                # 6. 객관식 (추론)
                if select_t6: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: 추론 및 비판 ({count_t6}문항)</h3>
                        - [지시] 지문을 바탕으로 논리적으로 추론하거나 비판하는 5지 선다형 문제를 {count_t6}개 작성하시오.
                        - [형식] 위와 동일한 객관식 포맷 사용.
                    </div>""")

                # 7. 보기 적용 (핵심 수정)
                if select_t7: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식: [보기] 적용 문제 ({count_t7}문항) [3점]</h3>
                        - **[필수 지시]**: 반드시 `<div class="example-box">` 태그를 사용하여 **[보 기]** 박스를 만드시오.
                        - **[내용]**: [보 기] 안에는 지문의 내용과 관련된 구체적인 **새로운 사례(Case)**, **반대 이론**, 또는 **도표/그래프에 대한 설명**을 3~4문장으로 작성하시오.
                        - **[문제]**: "윗글을 바탕으로 [보기]를 이해한 내용으로 적절하지 않은 것은?"과 같은 형식으로 출제하시오.
                        - [형식]
                        <div class="question-box">
                             <span class="question-text">[문제번호] 윗글을 참고하여 [보기]를 감상한 내용으로 적절하지 않은 것은? [3점]</span>
                             <div class="example-box">
                                 (여기에 지문과 연관된 구체적 사례나 다른 관점의 텍스트를 작성)
                             </div>
                             <div class="choices">
                                <div>① ...</div>
                                ...
                                <div>⑤ ...</div>
                             </div>
                        </div>
                    </div>""")
                
                reqs_content = "\n".join(reqs)
                
                # 요약 지시 및 해설용 요약 지시 설정
                summary_inst_passage = ""
                summary_inst_answer = ""
                
                if use_summary:
                    summary_inst_passage = """
                    - 문단이 끝날 때마다 `<div class='summary-blank'>📝 [문단 요약 연습]: (이곳에 핵심 내용을 요약해보세요)</div>`를 삽입하시오.
                    - **중요**: 이 부분은 학생이 직접 푸는 공간이므로 내용은 비워두시오.
                    """
                    summary_inst_answer = """
                    - **[필수 추가]**: 정답 및 해설 섹션의 맨 앞부분에 `<div class="summary-ans-box">` 태그를 사용하여 **[문단별 요약 예시 답안]**을 먼저 작성하시오. 각 문단의 핵심 내용을 1줄씩 요약하여 제시하시오.
                    """

                # 지문 처리 지시
                if current_d_mode == 'AI 생성':
                    passage_inst = f"""
                    **[Step 1] 지문 작성**
                    - 주제: {current_topic} ({current_domain})
                    - 난이도: {current_difficulty} (수능 비문학 스타일)
                    - 길이: 충분히 길게 (1500자 내외)
                    - 형식: `<div class="passage">` 태그 안에 `<p>` 태그로 문단을 구분하여 작성.
                    {summary_inst_passage}
                    """
                else:
                    passage_inst = f"""
                    **[Step 1] 지문 인식**
                    - 다음 지문을 읽고 분석하시오. (출력 시 지문 본문은 생략하고 문제만 출력할 것)
                    [지문 시작]
                    {current_manual_passage}
                    [지문 끝]
                    """

                # 통합 프롬프트
                prompt = f"""
                당신은 대한민국 수능 국어 출제 위원장입니다. 
                아래 지시사항에 맞춰 완벽한 HTML 포맷의 모의고사 문제지를 생성하시오.

                **[전체 출력 형식]**
                - `<html>`, `<head>` 등은 생략하고 `<body>` 태그 내부의 내용만 출력하시오.

                {passage_inst}

                **[Step 2] 문제 출제**
                다음 유형에 맞춰 문제를 순서대로 출제하시오. 문항 번호를 매기시오.
                {reqs_content}

                **[Step 3] 정답 및 해설 (매우 중요)**
                - 문서 맨 마지막에 반드시 `<div class="answer-sheet">`를 생성하시오.
                {summary_inst_answer}
                - **[주의] 절대 중간에 끊지 말고, 위에서 출제한 모든 문제(서술형, O/X, 객관식 포함)에 대한 정답과 상세 해설을 끝까지 작성하시오.**
                - 해설이 짤리면 안 됩니다. 마지막 문제까지 완벽하게 작성하십시오.
                - **[형식 준수]**: 각 문제마다 아래 포맷을 따르시오. (해설이 누락되면 안됨)
                
                <div class="ans-item">
                    <span class="ans-num">[문제 번호] 정답: ⑤</span>
                    <span class="ans-exp"><b>[정답 해설]</b>: 지문의 3문단에서 "~"라고 언급했으므로, 보기의 상황에 적용하면 ...가 된다. 따라서 적절하다.</span>
                    <span class="ans-wrong"><b>[오답 분석]</b>: ①번은 1문단의 내용과 배치되므로 틀렸다. ②번은 인과관계가 잘못되었다.</span>
                </div>
                """
                
                # [수정] 해설 짤림 방지를 위한 토큰 설정 강화
                generation_config = GenerationConfig(
                    max_output_tokens=8192,  # 최대 토큰 수 설정
                    temperature=0.7,
                )
                
                response = model.generate_content(prompt, generation_config=generation_config)
                clean_content = response.text.replace("```html", "").replace("```", "").strip()
                
                # HTML 조립
                full_html = HTML_HEAD
                full_html += f"<h1>사계국어 AI 모의고사</h1><h2>[{current_domain}] {current_topic}</h2>"
                full_html += "<div class='time-box'>⏱️ 목표 시간: 12분</div>"
                
                # 직접 입력 모드일 경우 지문을 Python에서 삽입
                if current_d_mode == '직접 입력':
                    def add_summary_box(text):
                        if not use_summary: return f"<p>{text}</p>"
                        return f"<p>{text}</p><div class='summary-blank'>📝 문단 요약 연습: (이곳에 핵심 내용을 요약해보세요)</div>"

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
                
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "clean_content": clean_content,
                    "domain": current_domain,
                    "topic": current_topic
                }
                status.success("✅ 출제 완료! 아래에서 확인하세요.")
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
        work_name = st.text_input("작품명", key="fiction_work_name_input")
        author_name = st.text_input("작가명", key="fiction_author_name_input")
        st.markdown("---")
        st.header("2️⃣ 출제 유형")
        count_t3 = st.number_input("객관식 문제 수", 1, 10, 3, key="fiction_c_t3")
        select_t7 = st.checkbox("보기(외적 준거) 적용 문제", value=True, key="fiction_select_t7")
        select_t6 = st.checkbox("인물 관계도 및 갈등 분석", key="fiction_select_t6")

    if st.session_state.generation_requested:
        current_novel_text = st.session_state.fiction_novel_text_input_area
        
        if not current_novel_text or not work_name:
            st.warning("작품명과 본문을 입력해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info("⚡ 문학 문제 출제 중...")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                reqs = []
                reqs.append(f"- 작품의 내용 이해를 묻는 객관식 5지 선다형 문제를 {count_t3}문항 출제하시오.")
                
                if select_t7:
                    reqs.append(f"""
                    - **[고난도 보기 문제]**: 
                      `<div class="example-box">` 안에 이 작품과 관련된 **시대적 상황**, **작가의 다른 경향**, 또는 **비평문의 일부**를 [보 기]로 제시하시오.
                      그리고 이를 바탕으로 작품을 감상한 내용으로 적절하지 않은 것을 묻는 문제를 1문항 출제하시오.
                    """)
                
                if select_t6:
                    reqs.append("- **[서술형]**: 주요 등장인물 간의 갈등 구조와 그 원인을 분석하여 서술하시오.")

                reqs_str = "\n".join(reqs)
                
                prompt = f"""
                당신은 수능 문학 출제위원입니다.
                작품: {work_name} ({author_name})
                
                **[지시 1] 지문 분석**
                아래 텍스트를 바탕으로 문제를 출제하시오. (지문은 출력하지 않음)
                {current_novel_text}
                
                **[지시 2] 문제 출제**
                {reqs_str}
                
                **[HTML 형식 규칙]**
                - 문제는 `<div class="question-box">` 사용.
                - 보기 박스는 `<div class="example-box">` 사용.
                - 선지는 `<div class="choices">` 사용.
                
                **[지시 3] 정답 및 해설**
                - 문서 끝에 `<div class="answer-sheet">`를 만들고, 모든 문제에 대해 **정답**, **해설(근거)**, **오답 분석**을 상세히 작성하시오.
                - **[주의] 절대 중간에 끊지 말고, 위에서 출제한 모든 문제에 대한 정답과 해설을 끝까지 작성하시오.**
                - 해설이 짤리면 안 됩니다. 마지막 문제까지 완벽하게 작성하십시오.
                - 형식: `<div class="ans-item"><span class="ans-num">[번호] 정답</span><br><span class="ans-exp">해설...</span></div>`
                """
                
                # [수정] 해설 짤림 방지를 위한 토큰 설정 강화 (문학도 동일 적용)
                generation_config = GenerationConfig(
                    max_output_tokens=8192, 
                    temperature=0.7,
                )
                
                response = model.generate_content(prompt, generation_config=generation_config)
                clean_content = response.text.replace("```html", "").replace("```", "").strip()
                
                full_html = HTML_HEAD
                full_html += f"<h1>{work_name} 실전 문제</h1><h2>{author_name}</h2>"
                full_html += f'<div class="passage">{current_novel_text.replace(chr(10), "<br>")}</div>'
                full_html += clean_content
                full_html += HTML_TAIL
                
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "clean_content": clean_content,
                    "domain": work_name,
                    "topic": author_name
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

# 앱 시작
st.title("📚 사계국어 AI 모의고사 제작 시스템")
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
        st.text_area("소설/시 본문 입력", height=300, key="fiction_novel_text_input_area")
        
        if st.button("🚀 문제 생성", key="run_fiction"):
            st.session_state.generation_requested = True
            
        fiction_app()

display_results()
