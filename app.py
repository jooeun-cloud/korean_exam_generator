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
st.set_page_config(page_title="사계국어 AI 모의고사 시스템", page_icon="📚", layout="wide")

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
            min-height: 50px;
            color: #666; font-size: 0.9em; background-color: #fcfcfc;
            font-weight: bold; display: flex; align-items: center;
        }

        /* 정답 및 해설 */
        .answer-sheet { 
            background: #f8f9fa; padding: 40px; margin-top: 60px; 
            border-top: 2px solid #333; 
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
    """안정적인 모델 선택"""
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
    
    document.add_heading("사계국어 AI 모의고사", 0)
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
        st.header("🛠️ 설정")
        st.selectbox("입력 방식", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.markdown("---")

        st.header("1️⃣ 지문 설정")
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""
        
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
            mode = st.radio("구성", ["단일 지문", "주제 통합"], key="manual_mode")
            current_mode = mode
            current_domain = "사용자 입력"
            current_topic = "사용자 지문"
            current_difficulty = "사용자 지정"

        st.markdown("---")
        st.header("2️⃣ 문제 유형")
        
        select_t1 = st.checkbox("1. 핵심 요약 (서술형)", value=True, key="select_t1")
        select_t2 = st.checkbox("2. 내용 일치 O/X", key="select_t2")
        count_t2 = st.number_input(" - 문항 수", 1, 5, 2, key="t2") if select_t2 else 0
        select_t3 = st.checkbox("3. 빈칸 채우기", key="select_t3")
        count_t3 = st.number_input(" - 문항 수", 1, 5, 2, key="t3") if select_t3 else 0
        select_t5 = st.checkbox("4. 객관식 (일치)", value=True, key="select_t5")
        count_t5 = st.number_input(" - 문항 수", 1, 5, 2, key="t5") if select_t5 else 0
        select_t6 = st.checkbox("5. 객관식 (추론)", value=True, key="select_t6")
        count_t6 = st.number_input(" - 문항 수", 1, 5, 1, key="t6") if select_t6 else 0
        select_t7 = st.checkbox("6. 객관식 (보기 적용 3점)", value=True, key="select_t7")
        count_t7 = st.number_input(" - 문항 수", 1, 3, 1, key="t7") if select_t7 else 0
        
        use_summary = st.checkbox("📌 문단별 요약 훈련 추가", value=True, key="select_summary")

    # --- 메인 실행 ---
    if st.session_state.generation_requested:
        
        if current_d_mode == '직접 입력':
            if current_mode == '단일 지문':
                current_manual_passage = st.session_state.get("manual_passage_input_col_main", "")
            else:
                p_a = st.session_state.get("manual_passage_input_a", "")
                p_b = st.session_state.get("manual_passage_input_b", "")
                current_manual_passage = f"[가]\n{p_a}\n\n[나]\n{p_b}"

        if current_d_mode == 'AI 생성' and not current_topic:
            st.warning("주제를 입력해주세요.")
            st.session_state.generation_requested = False
        elif current_d_mode == '직접 입력' and not current_manual_passage.strip():
            st.warning("지문을 입력해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡ 문제 생성 중입니다... ({get_best_model()})")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                # 프롬프트 구성
                reqs = []
                if select_t1: reqs.append("""<div class="question-box"><span class="question-text">1. 윗글의 핵심 내용을 요약하시오.</span><div class="write-box"></div></div>""")
                if select_t2: reqs.append(f"""<div class="type-box"><h3>내용 일치 O/X ({count_t2}문항)</h3>- 지문 내용과 일치 여부를 묻는 O/X 문제를 {count_t2}개 출제하시오.</div>""")
                if select_t3: reqs.append(f"""<div class="type-box"><h3>빈칸 채우기 ({count_t3}문항)</h3>- 핵심 어휘나 구절을 빈칸으로 만든 문제를 {count_t3}개 출제하시오.</div>""")
                
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
                
                if select_t5: reqs.append(f"""<div class="type-box"><h3>객관식: 세부 내용 파악 ({count_t5}문항)</h3>- 내용 일치/불일치 5지선다 문제 {count_t5}개를 작성하시오. 형식: {mcq_template}</div>""")
                if select_t6: reqs.append(f"""<div class="type-box"><h3>객관식: 추론 ({count_t6}문항)</h3>- 지문을 바탕으로 추론하는 5지선다 문제 {count_t6}개를 작성하시오. 형식: {mcq_template}</div>""")
                if select_t7: reqs.append(f"""<div class="type-box"><h3>객관식: 보기 적용 ({count_t7}문항)</h3>- `<div class="example-box">`에 구체적 사례(보기)를 제시하고 이를 적용하는 3점짜리 고난도 문제를 {count_t7}개 작성하시오. 형식: {mcq_template}</div>""")
                
                reqs_content = "\n".join(reqs)
                
                # 지문 처리
                passage_inst = ""
                if current_d_mode == 'AI 생성':
                    passage_inst = f"""
                    **[Step 1] 지문 작성**
                    - 주제: {current_topic}
                    - 난이도: {current_difficulty}
                    - 길이: 1800자 내외의 수능형 비문학 지문
                    - 형식: `<div class="passage">` 태그 안에 `<p>` 태그로 문단을 구분하여 작성.
                    """
                else:
                    passage_inst = """**[Step 1] 지문 인식** (사용자가 입력한 지문을 바탕으로 문제만 출제할 것. 지문은 다시 출력하지 마시오.)"""

                # 1단계: 문제 생성 프롬프트
                prompt_p1 = f"""
                당신은 수능 국어 출제 위원장입니다. 
                다음 지시사항에 따라 완벽한 HTML 포맷의 문제지를 생성하시오.
                
                {passage_inst}
                {current_manual_passage if current_d_mode == '직접 입력' else ''}

                **[Step 2] 문제 출제**
                {reqs_content}
                
                **[출력 규칙]**
                - `<html>`, `<body>` 태그 없이 내용만 출력하시오.
                - 정답 및 해설은 절대 포함하지 마시오.
                """
                
                gen_config = GenerationConfig(max_output_tokens=8192, temperature=0.7)
                res_p1 = model.generate_content(prompt_p1, generation_config=gen_config)
                html_problems = res_p1.text.replace("```html", "").replace("```", "").strip()
                
                if current_d_mode == '직접 입력':
                    # AI가 혹시 지문을 포함했다면 제거 (중복 방지)
                    html_problems = re.sub(r'<div class="passage">.*?</div>', '', html_problems, flags=re.DOTALL).strip()

                # 2단계: 해설 생성 프롬프트
                
                # 요약 정답 생성 로직
                summary_prompt_add = ""
                if use_summary:
                    # 사용자 입력 지문의 문단 수 계산 (엔터 두번 기준)
                    para_count = len(re.split(r'\n\s*\n', current_manual_passage.strip())) if current_d_mode == '직접 입력' else "지문의 실제 문단 수"
                    summary_prompt_add = f"""
                    - **[최우선 작성]**: 정답표 맨 위에 `<div class="summary-ans-box">`를 만들고, **[문단별 요약 예시 답안]**을 작성하시오.
                    - 사용자가 입력한 지문은 총 {para_count}개의 문단입니다. 반드시 **{para_count}개의 문단 요약**을 순서대로 작성하시오.
                    """

                prompt_p2 = f"""
                당신은 수능 국어 출제 위원장입니다.
                방금 출제한 문제에 대한 **[정답 및 해설]**을 작성하시오.

                **[입력된 문제 데이터]**
                {html_problems}
                
                **[원문 참고]**
                {current_manual_passage if current_d_mode == '직접 입력' else '위에서 생성한 지문 참고'}

                **[해설 작성 규칙 (매우 중요)]**
                1. 문서 마지막에 `<div class="answer-sheet">`를 생성하고 `<h2 class='ans-main-title'>정답 및 해설</h2>`를 붙이시오.
                {summary_prompt_add}
                2. **객관식 문제 해설**:
                   - 반드시 `[객관식 보기적용]`, `[객관식 추론]` 등 문제 유형을 배지(`ans-type-badge`)로 표시하시오.
                   - **1. 정답 상세 해설**: 정답인 이유를 지문 내 근거를 들어 설명하시오.
                   - **2. 오답 상세 분석 (필수)**: 각 오답 선지(①~⑤)별로 왜 답이 아닌지, 지문의 어느 부분과 배치되는지 구체적으로 줄바꿈(`<br>`)하여 설명하시오. "보기에 있다" 같은 단순 서술은 금지.
                3. **주관식/OX 문제**:
                   - 정답과 해설만 작성하고 오답 분석은 생략하시오.
                
                **[출력 예시]**
                <div class="ans-item">
                    <div class="ans-type-badge">[문제유형]</div>
                    <span class="ans-num">[1] 정답: ④</span>
                    <span class="ans-content-title">1. 정답 상세 해설</span>
                    <span class="ans-text">...</span>
                    <span class="ans-content-title">2. 오답 상세 분석</span>
                    <div class="ans-wrong-box">
                        <span class="ans-text">① (X): ...<br>② (X): ...</span>
                    </div>
                </div>
                """
                
                gen_config_ans = GenerationConfig(max_output_tokens=8192, temperature=0.3) # 해설은 정확하게
                res_p2 = model.generate_content(prompt_p2, generation_config=gen_config_ans)
                html_answers = res_p2.text.replace("```html", "").replace("```", "").strip()

                # 최종 HTML 조립
                full_html = HTML_HEAD
                full_html += f"<h1>사계국어 AI 모의고사</h1><h2>[{current_domain}] {current_topic}</h2>"
                full_html += "<div class='time-box'>⏱️ 소요 시간: <span class='time-blank'></span></div>"
                
                # 직접 입력 시 지문 삽입 (요약 빈칸 포함)
                if current_d_mode == '직접 입력':
                    def make_p_with_summary(text):
                        box = f"<p>{text}</p>"
                        if use_summary:
                            box += "<div class='summary-blank'>📝 문단 요약 연습: </div>"
                        return box

                    # 문단 나누기 (엔터 두번 기준)
                    raw_paras = re.split(r'\n\s*\n', current_manual_passage.strip())
                    formatted_paras = "".join([make_p_with_summary(p) for p in raw_paras if p.strip()])
                    
                    if current_mode == '단일 지문':
                        full_html += f'<div class="passage">{formatted_paras}</div>'
                    else:
                        # (가), (나) 등 복합 지문일 경우 단순 처리 (사용자가 알아서 나누었다고 가정)
                        full_html += f'<div class="passage">{formatted_paras}</div>'
                
                # AI 생성 지문일 경우, 1단계 결과에 이미 passage 태그가 포함되어 있을 것임.
                # 하지만 요약 빈칸을 AI가 안 넣었을 수 있으므로... 
                # (AI 생성 모드에서는 프롬프트에서 요청했으니 믿고 감)
                
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
# 📖 문학 문제 제작 함수
# ==========================================
def fiction_app():
    # (비문학 로직과 유사하게 구조화하여 안정성 확보)
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
            
            # 문제 생성
            prompt_1 = f"""
            당신은 수능 문학 출제위원입니다.
            작품: {work_name} ({author_name})
            본문: {text_input}
            
            다음 조건에 맞춰 HTML 포맷으로 문제만 출제하시오 (해설 제외).
            1. 5지 선다형 문제 {count_q}개.
            2. { '`<div class="example-box">`를 활용한 보기 적용 3점 문제 포함' if select_bogey else '' }
            3. { '서술형 감상 문제 1개 포함' if select_desc else '' }
            
            형식: `<div class="question-box">...</div>`
            """
            res_1 = model.generate_content(prompt_1)
            html_q = res_1.text.replace("```html","").replace("```","").strip()
            
            # 해설 생성
            prompt_2 = f"""
            위에서 출제한 문학 문제의 **정답 및 해설**을 작성하시오.
            입력된 문제: {html_q}
            
            규칙:
            1. `<div class="answer-sheet">` 내부에 작성.
            2. 객관식은 **[정답 상세 해설]**과 **[오답 상세 분석]**(각 선지별 줄바꿈 설명)을 모두 포함.
            3. 서술형은 예시 답안 제시.
            """
            res_2 = model.generate_content(prompt_2)
            html_a = res_2.text.replace("```html","").replace("```","").strip()
            
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
