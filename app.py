import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import openai
import re
import os
from docx import Document
from io import BytesIO
# [수정] 올바른 import 경로: 정렬 상수는 docx.enum.text에 있음
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH 
import time

# ==========================================
# [설정] 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="사계국어 모의고사 시스템", page_icon="📚", layout="wide")

# ==========================================
# [설정] API 클라이언트 초기화 (Google + OpenAI 통합)
# ==========================================
# 1. Google Gemini 설정
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except (KeyError, AttributeError):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)

# 2. OpenAI (GPT) 설정
openai_client = None
try:
    if "OPENAI_API_KEY" in st.secrets:
        from openai import OpenAI
        openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    print(f"OpenAI 설정 실패(건너뜀): {e}")

# ==========================================
# [설정] 모델 우선순위 정의
# ==========================================
MODEL_PRIORITY = [
    "gpt-5.2",              # 1순위 (OpenAI)
    "gpt-4o",               # 2순위
    "gemini-1.5-pro",       # 3순위 (Google)
    "gemini-1.5-flash"      # 4순위
]

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
# [공통 HTML/CSS 정의] - 가운데 정렬 헤더 적용
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
            max-width: 900px; 
            margin: 0 auto; 
            line-height: 1.6; 
            color: #000; 
            font-size: 11pt;
        }
        
        /* ---------------------------------------------------- */
        /* [헤더] 가운데 정렬 및 소요시간 배치 수정 */
        /* ---------------------------------------------------- */
        .header-container {
            margin-bottom: 30px;
            border-bottom: 2px solid #000; /* 하단 굵은 줄 */
            padding-bottom: 20px;
            text-align: center; /* 전체 가운데 정렬 */
        }
        
        .main-title {
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 15px 0;
            letter-spacing: -1px;
            color: #000;
            line-height: 1.2;
        }
        
        .time-wrapper {
            text-align: right; /* 소요시간만 우측 정렬 */
            margin-bottom: 15px;
            padding-right: 10px;
        }
        
        .time-box {
            font-size: 14px;
            font-weight: bold;
            border: 1px solid #000;
            padding: 6px 18px;
            border-radius: 4px;
            background-color: #fff;
            white-space: nowrap;
        }
        
        .exam-info {
            font-size: 16px;
            color: #333;
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .topic-info {
            font-size: 18px;
            font-weight: 800; /* 굵게 강조 */
            color: #000;
            background-color: #f4f4f4;
            padding: 8px 20px;
            display: inline-block;
            border-radius: 8px;
            margin-top: 5px;
        }

        /* ---------------------------------------------------- */

        /* 지문 스타일 */
        .passage { 
            font-size: 10.5pt; border: 1px solid #444; padding: 30px; 
            margin-bottom: 40px; background-color: #fff; 
            line-height: 1.8; text-align: justify;
        }
        .passage p { text-indent: 0.7em; margin-bottom: 15px; }
        
        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        
        h3 { font-size: 1.2em; color: #000; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px; font-weight: bold; margin-top: 40px; }

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

        /* 문단 요약 빈칸 스타일 */
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

# ==========================================
# [헬퍼 함수] 맞춤형 헤더 HTML 생성기 (수정됨)
# ==========================================
def get_custom_header_html(main_title, exam_info, topic_info):
    """
    사용자 요청 양식:
    1. 메인 타이틀 (가운데 정렬)
    2. 소요 시간 박스 (우측 정렬, 줄바꿈 후)
    3. 시험 정보 및 주제 (가운데 정렬)
    """
    return f"""
    <div class="header-container">
        <h1 class="main-title">{main_title}</h1>
        <div class="time-wrapper">
            <span class="time-box">소요 시간: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>
        </div>
        <div class="exam-info">{exam_info}</div>
        <div class="topic-info">주제: {topic_info}</div>
    </div>
    """

# ==========================================
# [모델 생성 로직] OpenAI(GPT) + Google(Gemini) 통합 Fallback
# ==========================================
def generate_content_with_fallback(prompt, generation_config=None, status_placeholder=None):
    last_exception = None
    
    for model_name in MODEL_PRIORITY:
        try:
            if status_placeholder:
                status_placeholder.info(f"⚡ 생성 중... (사용 모델: {model_name})")
            
            # [CASE 1] OpenAI
            if model_name.startswith("gpt") or model_name.startswith("o1"):
                if not openai_client:
                    continue
                
                response = openai_client.chat.completions.create(
                    model=model_name, 
                    messages=[
                        {"role": "system", "content": "당신은 대한민국 수능 국어 출제 위원장입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=8192 if not generation_config else generation_config.max_output_tokens,
                    temperature=0.7 if not generation_config else generation_config.temperature
                )
                
                class OpenAIResponseWrapper:
                    def __init__(self, text_content):
                        self.text = text_content
                
                return OpenAIResponseWrapper(response.choices[0].message.content)

            # [CASE 2] Google Gemini
            else:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=generation_config)
                return response
            
        except Exception as e:
            last_exception = e
            continue 

    if last_exception:
        raise last_exception
    else:
        raise Exception("설정된 모든 AI 모델(OpenAI/Google)이 응답하지 않습니다.")

# ==========================================
# [DOCX 생성 함수] (가운데 정렬 반영 - WD_ALIGN_PARAGRAPH 사용)
# ==========================================
def create_docx(html_content, file_name, main_title, sub_title, topic_title):
    document = Document()
    style = document.styles['Normal']
    style.font.name = 'Batang'
    style.font.size = Pt(10)

    # HTML 태그 제거 및 텍스트 추출
    clean_text = re.sub(r'<[^>]+>', '\n', html_content)
    clean_text = re.sub(r'\n+', '\n', clean_text).strip()
    
    # 1. 메인 타이틀 (가운데 정렬)
    h1 = document.add_heading(main_title, 0)
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 2. 소요 시간 (우측 정렬)
    p_time = document.add_paragraph("소요 시간: ___________")
    p_time.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    # 3. 보조 타이틀 (가운데 정렬)
    if sub_title:
        h2 = document.add_heading(sub_title, 1)
        h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
    # 4. 주제 (가운데 정렬)
    p_topic = document.add_paragraph(f"주제: {topic_title}")
    p_topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    document.add_paragraph("-" * 50)
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
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="nf_title")
        st.markdown("---")

        st.header("🛠️ 지문 입력 방식")
        st.selectbox("방식 선택", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.markdown("---")

        st.header("1️⃣ 지문 및 주제 설정")
        current_manual_passage = ""
        current_topic = ""
        current_domain = ""
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
        if current_d_mode == '직접 입력':
            if current_mode == '단일 지문':
                current_manual_passage = st.session_state.get("manual_passage_input_col_main", "")
            else:
                p_a = st.session_state.get("manual_passage_input_a", "")
                p_b = st.session_state.get("manual_passage_input_b", "")
                current_manual_passage = f"[가] 지문:\n{p_a}\n\n[나] 지문:\n{p_b}"

        if current_d_mode == 'AI 생성' and not current_topic:
            st.warning("주제를 입력해주세요.")
            st.session_state.generation_requested = False
        elif current_d_mode == '직접 입력' and not current_manual_passage.strip():
            st.warning("지문을 입력해주세요.")
            st.session_state.generation_requested = False
        else:
            status = st.empty()
            status.info(f"⚡ [{current_domain}] 출제 준비 중...")
            
            try:
                # 프롬프트 구성
                reqs = []
                if select_t1: 
                    reqs.append(f"""<div class="question-box"><span class="question-text">1. {label_type1}</span><div class="write-box"></div></div>""")
                if select_t2: 
                    reqs.append(f"""<div class="type-box"><h3>내용 일치 O/X ({count_t2}문항)</h3>- 문항 끝에 ( O / X ) 포함.</div>""")
                if select_t3:
                    reqs.append(f"""<div class="type-box"><h3>빈칸 채우기 ({count_t3}문항)</h3>- 빈칸은 `<span class='blank'>&nbsp;&nbsp;&nbsp;&nbsp;</span>` 사용. 영어 정답 금지.</div>""")
                if select_t4:
                    reqs.append(f"""<div class="type-box"><h3>변형 문장 정오판단 ({count_t4}문항)</h3>- 문항 끝에 ( O / X ) 포함.</div>""")
                
                mcq_template = """<div class="question-box"><span class="question-text">[문제번호] [발문]</span><div class="choices"><div>① [선지]</div><div>② [선지]</div><div>③ [선지]</div><div>④ [선지]</div><div>⑤ [선지]</div></div></div>"""
                
                if select_t5: reqs.append(f"""<div class="type-box"><h3>객관식: 세부 내용 파악 ({count_t5}문항)</h3>{mcq_template}</div>""")
                if select_t6: reqs.append(f"""<div class="type-box"><h3>객관식: 추론 및 비판 ({count_t6}문항)</h3>{mcq_template}</div>""")
                if select_t7: reqs.append(f"""<div class="type-box"><h3>객관식: [보기] 적용 문제 ({count_t7}문항) [3점]</h3><div class="question-box"><span class="question-text">[문제번호] 윗글을 바탕으로 [보기]를 이해한 내용으로 적절하지 않은 것은? [3점]</span><div class="example-box">(보기 내용)</div><div class="choices"><div>① ...</div><div>② ...</div><div>③ ...</div><div>④ ...</div><div>⑤ ...</div></div></div></div>""")
                
                reqs_content = "\n".join(reqs)
                summary_inst_passage = """- 문단이 끝날 때마다 `<div class='summary-blank'>📝 문단 요약 연습: (이곳에 핵심 내용을 요약해보세요)</div>`를 삽입하시오.""" if use_summary else ""

                passage_inst = f"""**[Step 1] 지문 작성** - 주제: {current_topic} ({current_domain}) - 난이도: {current_difficulty} - 길이: 1800자 내외""" if current_d_mode == 'AI 생성' else "**[Step 1] 지문 인식** - 사용자 입력 지문 기반."
                user_passage_block = f"\n[사용자 입력 지문 시작]\n{current_manual_passage}\n[사용자 입력 지문 끝]\n" if current_d_mode == '직접 입력' else ""

                prompt_p1 = f"""
                당신은 대한민국 수능 국어 출제 위원장입니다. 
                아래 지시사항에 맞춰 완벽한 HTML 포맷의 모의고사 문제지를 생성하시오.
                - `<html>`, `<head>` 생략, `<body>` 내용만 출력.
                - 정답 및 해설 제외. 학생용 문제지.
                
                # 🚨 [매우 중요] 출력 시 절대 제목/헤더를 생성하지 마시오.
                - `<h1>`, `<h2>` 태그는 절대 사용하지 마시오. 본문 내용(`<h3>` 이하)부터 바로 출력하시오.
                - "사계국어 모의고사" 같은 제목도 출력 금지.

                {passage_inst}
                {user_passage_block}

                # ----------------------------------------------------------------
                # 🚨 [난이도 및 출제 심화 가이드 - 필독]
                # ----------------------------------------------------------------
                1. **[복합 추론 필수]**: 두 문단 이상의 정보 종합.
                2. **[매력적인 오답]**: 부분적 진실, 인과 전도, 개념 혼동 사용.
                3. **[패러프레이징]**: 지문 문장을 동의어로 재진술.
                4. **[보기 적용 심화]**: 핵심 원리를 새로운 사례에 적용.

                **[Step 2] 문제 출제**
                {reqs_content}
                """
                
                generation_config = GenerationConfig(max_output_tokens=8192, temperature=0.7)
                response_problems = generate_content_with_fallback(prompt_p1, generation_config=generation_config, status_placeholder=status)
                html_problems = response_problems.text.replace("```html", "").replace("```", "").strip()

                if current_d_mode == '직접 입력':
                     html_problems = re.sub(r'<div class="passage">.*?</div>', '', html_problems, flags=re.DOTALL).strip()
                
                # [안전장치] AI가 생성한 H1, H2 태그 강제 제거
                html_problems = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_problems, flags=re.DOTALL | re.IGNORECASE)

                # 해설 생성 (Chunking)
                total_q_cnt = sum([1 if select_t1 else 0, count_t2 if select_t2 else 0, count_t3 if select_t3 else 0, count_t4 if select_t4 else 0, count_t5 if select_t5 else 0, count_t6 if select_t6 else 0, count_t7 if select_t7 else 0])
                problem_matches = re.findall(r'문제\s*\d+', html_problems)
                if problem_matches: total_q_cnt = max(total_q_cnt, len(problem_matches))
                if total_q_cnt == 0: total_q_cnt = 18 

                BATCH_SIZE = 6
                final_answer_html_parts = []
                summary_done = False 
                
                extra_passage_context = f"\n**[참고: 사용자 입력 지문 원문]**\n{current_manual_passage}\n" if current_d_mode == '직접 입력' else ""

                for i in range(0, total_q_cnt, BATCH_SIZE):
                    start_num = i + 1
                    end_num = min(i + BATCH_SIZE, total_q_cnt)
                    status.info(f"📝 정답 및 해설 생성 중... ({start_num}~{end_num}번 / 총 {total_q_cnt}문항)")
                    
                    current_summary_prompt = ""
                    if use_summary and not summary_done:
                        current_summary_prompt = """- **[필수]**: 답변 맨 위에 `<div class="summary-ans-box">`를 열고 **[문단별 요약]**을 작성하시오."""
                        summary_done = True 

                    prompt_chunk = f"""
                    당신은 대한민국 수능 국어 출제 위원장입니다.
                    전체 {total_q_cnt}문제 중, **{start_num}번부터 {end_num}번까지**의 문제에 대해서만 정답 및 해설을 작성하시오.
                    {extra_passage_context}
                    [입력된 문제]: {html_problems}
                    
                    **[지시사항]**
                    1. 서론/인사말 생략. HTML 코드만 출력.
                    2. **[토큰 절약]**: 문제 발문, 보기 다시 적지 말고 해설만 작성.
                    3. 절대 제목(`<h1>`, `<h2>`)을 생성하지 마시오.
                    {current_summary_prompt}
                    
                    **[해설 작성 규칙]**:
                    1. **객관식**: 정답 해설 + 오답 상세 분석(①~⑤) 필수.
                    2. **O/X, 빈칸**: 정답만 명확히.

                    **[작성 포맷 HTML]**
                    <div class="ans-item">
                        <div class="ans-type-badge">[유형]</div>
                        <span class="ans-num">[문제번호] 정답: (정답표기)</span>
                        <span class="ans-content-title">1. 정답 상세 해설</span>
                        <span class="ans-text">...</span>
                        <span class="ans-content-title">2. 오답 상세 분석</span>
                        <div class="ans-wrong-box"><span class="ans-text">① (X): ... <br>② (X): ...</span></div>
                    </div>
                    """
                    
                    response_chunk = generate_content_with_fallback(prompt_chunk, generation_config=GenerationConfig(max_output_tokens=8192, temperature=0.3))
                    chunk_text = response_chunk.text.replace("```html", "").replace("```", "").strip()
                    
                    if i == 0:
                        if '<div class="answer-sheet">' not in chunk_text:
                                chunk_text = '<div class="answer-sheet"><h2 class="ans-main-title">정답 및 해설</h2>' + chunk_text
                        chunk_text = re.sub(r'</div>\s*$', '', chunk_text)
                    else:
                        chunk_text = re.sub(r'<div[^>]*class=["\']answer-sheet["\'][^>]*>', '', chunk_text, flags=re.IGNORECASE)
                        chunk_text = re.sub(r'<h2[^>]*>.*?정답.*?</h2>', '', chunk_text, flags=re.DOTALL | re.IGNORECASE)
                        chunk_text = re.sub(r'</div>\s*$', '', chunk_text)
                    
                    final_answer_html_parts.append(chunk_text)

                html_answers = "".join(final_answer_html_parts)
                if not html_answers.strip().endswith("</div>"):
                    html_answers += "</div>"

                # -----------------------------------------------------------
                # [핵심] 고정 헤더 적용 (HTML 조립)
                # -----------------------------------------------------------
                full_html = HTML_HEAD
                
                # 보조 타이틀 결정 (비문학)
                sub_title_text = f"2025학년도 수능 대비 - 비문학({current_domain})" if current_d_mode == 'AI 생성' else "비문학 독해 훈련"
                topic_text = current_topic if current_topic else "지문 분석"
                
                # 고정 헤더 삽입 (가운데 정렬 + 소요시간 우측)
                full_html += get_custom_header_html(custom_main_title, sub_title_text, topic_text)
                
                # 지문 삽입
                if current_d_mode == '직접 입력':
                    def make_p_with_summary(text):
                        box = f"<p>{text}</p>"
                        if use_summary:
                            box += "<div class='summary-blank'>📝 문단 요약 연습: </div>"
                        return box
                    raw_paras = [p.strip() for p in re.split(r'\n\s*\n', current_manual_passage.strip()) if p.strip()]
                    formatted_paras = "".join([make_p_with_summary(p) for p in raw_paras])
                    full_html += f'<div class="passage">{formatted_paras}</div>'
                
                full_html += html_problems
                full_html += html_answers
                full_html += HTML_TAIL
                
                st.session_state.generated_result = {
                    "full_html": full_html,
                    "domain": current_domain,
                    "topic": current_topic,
                    "main_title": custom_main_title,
                    "sub_title": sub_title_text,
                    "topic_title": topic_text
                }
                status.success("✅ 생성 완료!")
                st.session_state.generation_requested = False

            except Exception as e:
                status.error(f"오류 발생: {e}")
                st.session_state.generation_requested = False

# ==========================================
# 📖 문학 문제 제작 함수 (고도화: 타이틀+8가지 유형)
# ==========================================
def fiction_app():
    global GOOGLE_API_KEY
    
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="fic_custom_main_title")
        st.markdown("---")

        st.header("1️⃣ 작품 정보")
        work_name = st.text_input("작품명", key="fic_name")
        author_name = st.text_input("작가명", key="fic_auth")
        
        st.markdown("---")
        st.header("2️⃣ 문제 유형 및 개수")
        
        # 유형 1~4 (문항수 조절 가능)
        use_vocab = st.checkbox("1. 어휘 문제 (단답형)", value=True, key="fic_t1")
        cnt_vocab = st.number_input(" - 문항 수", 1, 20, 5, key="fic_cnt_1") if use_vocab else 0
        
        use_essay = st.checkbox("2. 서술형 심화 (감상/의도)", value=True, key="fic_t2")
        cnt_essay = st.number_input(" - 문항 수", 1, 10, 3, key="fic_cnt_2") if use_essay else 0
        
        use_mcq_gen = st.checkbox("3. 객관식 (일반 5지선다)", value=True, key="fic_t3_gen")
        cnt_mcq_gen = st.number_input(" - 문항 수", 1, 10, 3, key="fic_cnt_3_gen") if use_mcq_gen else 0

        use_mcq_bogey = st.checkbox("4. 객관식 (보기 적용 심화)", value=True, key="fic_t4_bogey")
        cnt_mcq_bogey = st.number_input(" - 문항 수", 1, 10, 2, key="fic_cnt_4_bogey") if use_mcq_bogey else 0
        
        st.markdown("---")
        st.caption("3️⃣ 분석 및 정리 활동 (서술형/표)")
        
        # 유형 5~8 (활동)
        use_char = st.checkbox("5. 주요 등장인물 정리 (표)", key="fic_t5_char")
        use_summ = st.checkbox("6. 소설 속 상황 요약", key="fic_t6_summ")
        use_rel = st.checkbox("7. 인물 관계도 및 갈등", key="fic_t7_rel")
        use_conf = st.checkbox("8. 갈등 구조 및 심리 정리", key="fic_t8_conf")

    if st.session_state.generation_requested:
        text_input = st.session_state.fiction_novel_text_input_area
        if not text_input:
            st.warning("작품 내용을 입력하세요.")
            st.session_state.generation_requested = False
            return

        status = st.empty()
        status.info("⚡ 문학 분석 및 문제 생성 중... (잠시만 기다려주세요)")
        
        try:
            # -----------------------------------------------------------
            # [1단계] 학생용 문제지 생성 프롬프트
            # -----------------------------------------------------------
            req_q_list = []
            
            # 1. 어휘
            if use_vocab:
                req_q_list.append(f"""<div class="type-box"><h3>유형 1. 어휘 문제 ({cnt_vocab}문항)</h3>- 지문의 어려운 어휘 {cnt_vocab}개의 의미 묻기 (단답형).<div class="question-box"><span class="question-text">[번호] '____'의 문맥적 의미는?</span><div class="write-box" style="height:50px;"></div></div></div>""")
            # 2. 서술형
            if use_essay:
                req_q_list.append(f"""<div class="type-box"><h3>유형 2. 서술형 심화 문제 ({cnt_essay}문항)</h3>- 작가의 의도, 효과, 이유를 묻는 고난도 서술형.<div class="question-box"><span class="question-text">[번호] (질문)</span><div class="write-box"></div></div></div>""")
            # 3. 객관식(일반)
            if use_mcq_gen:
                req_q_list.append(f"""<div class="type-box"><h3>유형 3. 객관식 문제 (일반) ({cnt_mcq_gen}문항)</h3>- 수능형 5지 선다 (추론/비판).<div class="question-box"><span class="question-text">[번호] (발문)</span><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div></div>""")
            # 4. 객관식(보기)
            if use_mcq_bogey:
                req_q_list.append(f"""<div class="type-box"><h3>유형 4. 객관식 문제 (보기 적용) ({cnt_mcq_bogey}문항)</h3>- **<보기>** 박스 필수 포함 (3점 킬러문항).<div class="question-box"><span class="question-text">[번호] <보기>를 참고하여 감상한 내용으로 적절하지 않은 것은? [3점]</span><div class="example-box">(보기 내용)</div><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div></div>""")
            # 5~8. 활동형
            if use_char: req_q_list.append(f"""<div class="type-box"><h3>유형 5. 주요 등장인물 정리</h3>- 인물명, 호칭, 역할, 심리 빈칸 표 제공.</div>""")
            if use_summ: req_q_list.append(f"""<div class="type-box"><h3>유형 6. 소설 속 상황 요약</h3>- 핵심 갈등 요약 서술.<div class="write-box"></div></div>""")
            if use_rel: req_q_list.append(f"""<div class="type-box"><h3>유형 7. 인물 관계도 및 갈등</h3>- 직접 그릴 수 있는 박스.<div class="write-box" style="height:200px;"></div></div>""")
            if use_conf: req_q_list.append(f"""<div class="type-box"><h3>유형 8. 갈등 구조 및 심리 정리</h3>- 갈등 양상 및 비판 의도 서술.<div class="write-box"></div></div>""")

            reqs_str = "\n".join(req_q_list)

            prompt_1 = f"""
            당신은 수능 문학 출제위원입니다.
            작품: {work_name} ({author_name})
            본문: {text_input}
            
            학생용 문제지(HTML)를 작성하시오. (정답/해설 제외)
            
            # 🚨 [매우 중요] 출력 시 절대 제목/헤더를 생성하지 마시오.
            - `<h1>`, `<h2>` 태그 절대 금지. 본문 내용부터 바로 출력.
            
            # 🚨 [수능 최고난도 출제 지침]
            1. **[복합적 사고]**: 작품 전체 맥락과 함축적 의미를 종합해야 풀 수 있는 문제.
            2. **[매력적인 오답]**: 부분적 진실, 주객 전도, 과잉 해석 함정 배치.
            3. **[보기 적용]**: 비평적 관점을 적용해 새롭게 해석하는 3점 문항.

            [출제 요청 목록]
            {reqs_str}
            """
            
            res_1 = generate_content_with_fallback(prompt_1, status_placeholder=status)
            html_q = res_1.text.replace("```html","").replace("```","").strip()
            
            # [안전장치] AI 제목 태그 제거
            html_q = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_q, flags=re.DOTALL | re.IGNORECASE)
            
            # -----------------------------------------------------------
            # [2단계] 정답 및 해설 (교사용)
            # -----------------------------------------------------------
            prompt_2 = f"""
            당신은 수능 문학 해설 위원입니다.
            앞서 출제된 문제들에 대한 **완벽한 정답 및 해설**을 작성하시오.
            입력된 문제: {html_q}
            본문: {text_input}
            
            **[작성 규칙]**
            1. `<div class="answer-sheet">` 태그 안에 작성.
            2. **객관식**: [정답], [상세 해설], [오답 분석] 필수.
            3. **활동형**: 빈 표를 채운 완성된 예시 답안 제시.
            """
            
            res_2 = generate_content_with_fallback(prompt_2, status_placeholder=status)
            html_a = res_2.text.replace("```html","").replace("```","").strip()
            
            if '<div class="answer-sheet">' in html_a:
                html_a = html_a[html_a.find('<div class="answer-sheet">'):]
            else:
                html_a = '<div class="answer-sheet">' + html_a + '</div>'
            
            # -----------------------------------------------------------
            # [핵심] 문학 모드에도 고정 헤더 적용
            # -----------------------------------------------------------
            full_html = HTML_HEAD
            
            # 정보 텍스트 구성
            exam_info_text = f"2025학년도 수능 대비 - 문학({work_name})"
            topic_text = f"작품: {work_name} ({author_name})"
            
            # 고정 헤더 함수 호출 (가운데 정렬 + 우측 소요시간)
            full_html += get_custom_header_html(custom_main_title, exam_info_text, topic_text)
            
            full_html += f'<div class="passage">{text_input.replace(chr(10), "<br>")}</div>'
            full_html += html_q + html_a + HTML_TAIL
            
            st.session_state.generated_result = {
                "full_html": full_html, 
                "domain": "문학", 
                "topic": work_name,
                "main_title": custom_main_title,
                "sub_title": exam_info_text,
                "topic_title": topic_text
            }
            status.success("✅ 문학 분석 학습지 생성 완료!")
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
            main_t = res.get("main_title", "사계국어 모의고사")
            sub_t = res.get("sub_title", "")
            topic_t = res.get("topic_title", "")
            docx = create_docx(res["full_html"], "exam.docx", main_t, sub_t, topic_t)
            st.download_button("📄 Word 저장", docx, "exam.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            
        st.components.v1.html(res["full_html"], height=800, scrolling=True)

# -----------------------------------------
# [실행부] 앱 모드 선택 및 실행
# -----------------------------------------
st.title("📚 사계국어 모의고사 제작 시스템")
st.markdown("---")

col_L, col_R = st.columns([1.5, 3])

with col_L:
    st.radio("모드 선택", ["⚡ 비문학 문제 제작", "📖 문학 문제 제작"], key="app_mode")

with col_R:
    if st.session_state.app_mode == "⚡ 비문학 문제 제작":
        st.header("⚡ 비문학 모의평가")
        
        # 직접 입력일 경우 UI 미리 표시
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
        
        # 핵심: 함수 실행
        non_fiction_app()

    else:
        st.header("📖 문학 심층 분석")
        st.text_area("작품 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 분석 생성", key="run_fiction"):
            st.session_state.generation_requested = True
        fiction_app()

display_results()
