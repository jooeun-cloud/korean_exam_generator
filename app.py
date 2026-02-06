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
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except (KeyError, AttributeError):
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)

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
    "gpt-5.2",              # 1순위 (OpenAI - 최신)
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
# [공통 HTML/CSS 정의] - 원본 스타일 100% 보존
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
        
        .header-container {
            margin-bottom: 30px;
            border-bottom: 2px solid #000; 
            padding-bottom: 15px;
            text-align: center; 
        }
        
        .top-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-end; 
            margin-bottom: 20px;
        }
        
        .main-title {
            font-size: 26px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            color: #000;
            line-height: 1.2;
            flex-grow: 1;
            text-align: left; 
        }
        
        .time-box {
            font-size: 14px;
            font-weight: bold;
            border: 1px solid #000;
            padding: 5px 15px;
            border-radius: 4px;
            white-space: nowrap;
        }
        
        .topic-info {
            font-size: 16px;
            font-weight: 800; 
            color: #000;
            background-color: #f4f4f4; 
            padding: 8px 20px;
            display: inline-block;
            border-radius: 8px;
            margin-top: 5px;
        }

        .passage { 
            font-size: 10.5pt; border: 1px solid #444; padding: 30px; 
            margin-bottom: 40px; background-color: #fff; 
            line-height: 1.8; text-align: justify;
        }
        .passage p { text-indent: 0.7em; margin-bottom: 15px; }

        /* 현대시 행/연 구분 보존 스타일 */
        .poetry-passage {
            white-space: pre-wrap; font-family: 'Batang', serif; line-height: 2.2;
            font-size: 11pt; border: 1px solid #444; padding: 35px;
            margin-bottom: 40px; background-color: #fff; text-align: left;
        }
        
        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        
        h3 { font-size: 1.2em; color: #000; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px; font-weight: bold; margin-top: 40px; } 

        .question-box { margin-bottom: 40px; page-break-inside: avoid; }
        .question-text { font-weight: bold; margin-bottom: 15px; display: block; font-size: 1.1em; word-break: keep-all;} 

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

        .write-box { 
            margin-top: 15px; height: 120px; 
            border: 1px solid #ccc; border-radius: 4px;
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
        } 

        .summary-blank {
            border: 1px dashed #aaa; padding: 15px; margin: 15px 0 25px 0;
            min-height: 100px;
            color: #666; font-size: 0.9em; background-color: #fcfcfc;
            font-weight: bold; display: flex; align-items: flex-start;
        } 

        .blank {
            display: inline-block;
            min-width: 80px; 
            border-bottom: 1.5px solid #000;
            margin: 0 5px;
            height: 1.2em;
            vertical-align: middle;
        } 

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
# [헬퍼 함수]
# ==========================================
def get_custom_header_html(main_title, topic_info):
    return f"""
    <div class="header-container">
        <div class="top-row">
            <h1 class="main-title">{main_title}</h1>
            <div class="time-box">소요 시간: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</div>
        </div>
        <div class="topic-info">주제: {topic_info}</div>
    </div>
    """ 

def generate_content_with_fallback(prompt, generation_config=None, status_placeholder=None):
    last_exception = None
    for model_name in MODEL_PRIORITY:
        try:
            if status_placeholder:
                status_placeholder.info(f"⚡ 생성 중... (사용 모델: {model_name})")
            if model_name.startswith("gpt") or model_name.startswith("o1"):
                if not openai_client: continue
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
                    def __init__(self, text_content): self.text = text_content
                return OpenAIResponseWrapper(response.choices[0].message.content)
            else:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=generation_config)
                return response
        except Exception as e:
            last_exception = e; continue 
    if last_exception: raise last_exception
    else: raise Exception("모델 응답 실패")

def create_docx(html_content, file_name, main_title, topic_title):
    document = Document()
    style = document.styles['Normal']; style.font.name = 'Batang'; style.font.size = Pt(10)
    clean_text = re.sub(r'<[^>]+>', '\n', html_content); clean_text = re.sub(r'\n+', '\n', clean_text).strip()
    h1 = document.add_heading(main_title, 0); h1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_time = document.add_paragraph("소요 시간: ___________"); p_time.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_topic = document.add_paragraph(f"주제: {topic_title}"); p_topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("-" * 50); document.add_paragraph(clean_text)
    file_stream = BytesIO(); document.save(file_stream); file_stream.seek(0)
    return file_stream 

# ==========================================
# 🧩 1. 비문학 문제 제작 함수 (원본 100% 무삭제 복구)
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
                # [복구] 주제 통합 가/나 분리 입력 필드
                topic_a = st.text_input("주제 (가)", placeholder="예: 공리주의", key="t_a")
                topic_b = st.text_input("주제 (나)", placeholder="예: 의무론", key="t_b")
                current_topic = "(가) " + topic_a + " / (나) " + topic_b
            
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
        select_t2 = st.checkbox("2. 내용 일치 O/X", key="select_t2"); count_t2 = st.number_input(" - 문항 수", 1, 10, 2, key="t2") if select_t2 else 0
        select_t3 = st.checkbox("3. 빈칸 채우기", key="select_t3"); count_t3 = st.number_input(" - 문항 수", 1, 10, 2, key="t3") if select_t3 else 0
        select_t4 = st.checkbox("4. 변형 문장 정오판단", key="select_t4"); count_t4 = st.number_input(" - 문항 수", 1, 10, 2, key="t4") if select_t4 else 0
        select_t5 = st.checkbox("5. 객관식 (일치/불일치)", value=True, key="select_t5"); count_t5 = st.number_input(" - 문항 수", 1, 10, 2, key="t5") if select_t5 else 0
        select_t6 = st.checkbox("6. 객관식 (추론)", value=True, key="select_t6"); count_t6 = st.number_input(" - 문항 수", 1, 10, 2, key="t6") if select_t6 else 0
        select_t7 = st.checkbox("7. 객관식 (보기 적용 3점)", value=True, key="select_t7"); count_t7 = st.number_input(" - 문항 수", 1, 10, 1, key="t7") if select_t7 else 0
        use_summary = st.checkbox("📌 문단별 요약 훈련 칸 생성", value=True, key="select_summary")

    if st.session_state.generation_requested:
        if current_d_mode == '직접 입력':
            if current_mode == '단일 지문':
                current_manual_passage = st.session_state.get("manual_passage_input_col_main", "")
            else:
                p_a = st.session_state.get("manual_passage_input_a", "")
                p_b = st.session_state.get("manual_passage_input_b", "")
                current_manual_passage = "[가] 지문:\n" + p_a + "\n\n[나] 지문:\n" + p_b

        if not current_topic and current_d_mode == 'AI 생성': st.warning("주제를 입력해주세요."); st.session_state.generation_requested = False
        elif current_d_mode == '직접 입력' and not current_manual_passage.strip(): st.warning("지문을 입력해주세요."); st.session_state.generation_requested = False
        else:
            status = st.empty(); status.info(f"⚡ [{current_domain}] 출제 준비 중...")
            try:
                # 프롬프트 구성 (백슬래시 에러 방지를 위해 변수 결합)
                req_list = []
                if select_t1: req_list.append('<div class="question-box"><span class="question-text">1. ' + label_type1 + '</span><div class="write-box"></div></div>')
                if select_t2: req_list.append('<h3>내용 일치 O/X (' + str(count_t2) + '문항)</h3>- 문항 끝에 ( O / X ) 포함.')
                if select_t3: req_list.append('<h3>빈칸 채우기 (' + str(count_t3) + '문항)</h3>- 빈칸은 `<span class="blank">&nbsp;&nbsp;&nbsp;&nbsp;</span>` 사용. 영어 정답 금지.')
                if select_t4: req_list.append('<h3>변형 문장 정오판단 (' + str(count_t4) + '문항)</h3>- 문항 끝에 ( O / X ) 포함.')
                mcq_tpl = '<div class="question-box"><span class="question-text">[문제번호] [발문]</span><div class="choices"><div>① [선지]</div><div>② [선지]</div><div>③ [선지]</div><div>④ [선지]</div><div>⑤ [선지]</div></div></div>'
                if select_t5: req_list.append('<h3>객관식: 세부 내용 파악 (' + str(count_t5) + '문항)</h3>' + mcq_tpl)
                if select_t6: req_list.append('<h3>객관식: 추론 및 비판 (' + str(count_t6) + '문항)</h3>' + mcq_tpl)
                if select_t7: req_list.append('<h3>객관식: [보기] 적용 문제 (' + str(count_t7) + '문항) [3점]</h3><div class="question-box"><span class="question-text">[문제번호] 윗글을 바탕으로 [보기]를 이해한 내용으로 적절하지 않은 것은? [3점]</span><div class="example-box">(보기 내용)</div><div class="choices"><div>① ...</div><div>② ...</div><div>③ ...</div><div>④ ...</div><div>⑤ ...</div></div></div>')
                
                reqs_str = "\n".join(req_list)
                
                # [복구] 문단 요약 상세 지침 원본 100% 복구
                summary_inst_passage = ""
                if use_summary:
                    summary_inst_passage = """
                    - **[필수]**: 각 문단이 끝날 때마다 반드시 `<div class='summary-blank'>📝 문단 요약 연습: (이곳에 핵심 내용을 요약해보세요)</div>` 코드를 삽입하여 사용자가 내용을 요약할 수 있는 빈칸을 만들어주시오.
                    - 이 부분은 사용자가 글을 쓸 공간이므로 절대 내용을 채우지 마시오.
                    """

                # [복구] 지문 가이드라인 원본 100% 복구
                p1_prompt = """
당신은 대한민국 수능 국어 출제 위원장입니다. 
아래 지시사항에 맞춰 완벽한 HTML 포맷의 모의고사 문제지를 생성하시오.
- `<html>`, `<head>` 생략, `<body>` 내용만 출력.
- 정답 및 해설 제외. 학생용 문제지.

# 🚨 [매우 중요] 출력 시 절대 제목/헤더를 생성하지 마시오.
- `<h1>`, `<h2>` 태그는 절대 사용하지 마시오. 본문 내용(`<h3>` 이하)부터 바로 출력하시오.
- "사계국어 모의고사" 같은 제목도 출력 금지.

{STEP1}
{USER_BLOCK}

# ----------------------------------------------------------------
# 🚨 [고난도(킬러 문항) 출제 필수 가이드라인]
# ----------------------------------------------------------------
1. **[정보의 재구성 필수 - 1:1 매칭 금지]**: 
   - 정답 선지는 절대 한 문단이나 한 문장의 내용만으로 판단할 수 없게 하시오.
   - **반드시 '1문단 + 3문단' 혹은 'A주장 + B반론'처럼 서로 멀리 떨어진 두 개 이상의 정보를 결합**해야만 참/거짓을 판별할 수 있도록 문장을 재구성하시오.

2. **[단어 바꿔치기(Paraphrasing)]**:
   - 지문에 있는 단어를 그대로 선지에 쓰지 마시오. (학생들이 그림 맞추기 식으로 풀게 됨)
   - 지문의 '상승했다'를 '하락하지 않았다'나 '고점에 도달했다'처럼 **동의어나 함축적 의미로 변환**하여 선지를 작성하시오.

3. **[인과관계 비틀기 (오답 설계)]**:
   - 단순히 '아니다'를 붙이는 유치한 오답을 금지합니다.
   - 'A라서 B이다'를 'B라서 A이다'로 **인과관계를 뒤집거나**, 주체(주어)와 객체(목적어)를 서로 바꾸어 매력적인 오답을 만드시오.

4. **[선지 분포]**:
   - 선지 ①~⑤번이 지문의 특정 부분에 쏠리지 않게, 지문 전체(서론, 본론, 결론)를 아우르도록 배치하시오.

**[Step 2] 문제 출제**
{REQS}
                """.format(
                    STEP1 = f"**[Step 1] 지문 작성** - 주제: {current_topic} ({current_domain}) - 난이도: {current_difficulty} - 길이: 1800자 내외 \n{summary_inst_passage}" if current_d_mode == 'AI 생성' else "**[Step 1] 지문 인식** - 사용자 입력 지문 기반.",
                    USER_BLOCK = "\n[사용자 입력 지문 시작]\n" + current_manual_passage + "\n[사용자 입력 지문 끝]\n" if current_d_mode == '직접 입력' else "",
                    REQS = reqs_str
                )
                
                res_problems = generate_content_with_fallback(p1_prompt, status_placeholder=status)
                html_problems = res_problems.text.replace("```html", "").replace("```", "").strip()
                html_problems = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_problems, flags=re.DOTALL | re.IGNORECASE)

                # [복구] 해설 분할 생성 (Batch Size 6) 로직 원본 100% 복구
                problem_matches = re.findall(r'문제\s*\d+', html_problems)
                total_q_cnt = max(len(problem_matches), sum([1 if select_t1 else 0, count_t2, count_t3, count_t4, count_t5, count_t6, count_t7]))
                if total_q_cnt == 0: total_q_cnt = 18 

                BATCH_SIZE = 6; final_ans_parts = []; summary_done = False
                extra_context = "\n**[참고: 사용자 입력 지문 원문]**\n" + current_manual_passage + "\n" if current_d_mode == '직접 입력' else ""

                for i in range(0, total_q_cnt, BATCH_SIZE):
                    start_num = i + 1; end_num = min(i + BATCH_SIZE, total_q_cnt)
                    status.info(f"📝 정답 및 해설 생성 중... ({start_num}~{end_num}번 / 총 {total_q_cnt}문항)")
                    
                    current_summary_prompt = ""
                    if use_summary and not summary_done:
                        if current_d_mode == '직접 입력':
                             user_paras = [p for p in re.split(r'\n\s*\n', current_manual_passage.strip()) if p.strip()]
                             para_count = len(user_paras)
                             current_summary_prompt = "- **[필수 - 최우선 작성]**: 답변 맨 위에 `<div class='summary-ans-box'>`를 열고 **[문단별 요약 예시 답안]**을 작성하시오.\n- **[중요]**: 입력된 지문은 총 **" + str(para_count) + "개의 문단**입니다. 각 문단의 핵심 내용을 1문장씩 요약하여 총 " + str(para_count) + "개를 제시하시오."
                        else:
                             current_summary_prompt = "- **[필수 - 최우선 작성]**: 답변 맨 위에 `<div class='summary-ans-box'>`를 열고 **[문단별 요약 예시 답안]**을 작성하시오. 지문의 각 문단별 핵심 내용을 요약하여 제시하시오."
                        summary_done = True 

                    p_chunk = """
당신은 대한민국 수능 국어 출제 위원장입니다.
전체 {T_CNT}문제 중, **{S_NUM}번부터 {E_NUM}번까지**의 문제에 대해서만 정답 및 해설을 작성하시오.
{CONTEXT}
[입력된 문제]: {Q_TEXT}

**[지시사항]**
1. 서론/인사말 생략. HTML 코드만 출력.
2. **[토큰 절약]**: 문제 발문, 보기 다시 적지 말고 해설만 작성.
3. 절대 제목(`<h1>`, `<h2>`)을 생성하지 마시오.
{SUM_PROM}

**[해설 작성 규칙 (상세하게)]**:
1. **객관식**: 정답 해설 + 오답 상세 분석(①~⑤) 필수.
2. **O/X 및 빈칸**:
   - 단순히 'O', 'X' 또는 정답 단어만 적지 마십시오.
   - **[해설]**을 반드시 덧붙여서, 왜 그것이 정답인지 지문의 내용을 근거로 설명하시오.
   - 예: [문제 1] O - (해설) 지문 2문단에서 ~~라고 언급하였으므로 일치한다.

**[작성 포맷 HTML]**
<div class="ans-item">
    <div class="ans-type-badge">[유형]</div>
    <span class="ans-num">[{S_NUM}] 정답: (정답표기)</span>
    <span class="ans-content-title">1. 정답 상세 해설</span>
    <span class="ans-text">...</span>
    <!-- 객관식일 경우에만 아래 오답 분석 작성 -->
    <span class="ans-content-title">2. 오답 상세 분석</span>
    <div class="ans-wrong-box"><span class="ans-text">① (X): ... <br>② (X): ...</span></div>
</div>
                    """.format(T_CNT=total_q_cnt, S_NUM=start_num, E_NUM=end_num, CONTEXT=extra_context, Q_TEXT=html_problems, SUM_PROM=current_summary_prompt)
                    
                    res_chunk = generate_content_with_fallback(p_chunk, status_placeholder=status)
                    chunk_text = res_chunk.text.replace("```html","").replace("```","").strip()
                    if i == 0: chunk_text = '<div class="answer-sheet"><h2 class="ans-main-title">정답 및 해설</h2>' + chunk_text
                    final_ans_parts.append(chunk_text)

                html_answers = "".join(final_ans_parts) + "</div>"
                full_html = HTML_HEAD + get_custom_header_html(custom_main_title, current_topic)
                if current_d_mode == '직접 입력':
                    paras = [p.strip() for p in re.split(r'\n\s*\n', current_manual_passage.strip()) if p.strip()]
                    formatted_p = ""
                    for p in paras:
                        formatted_p += "<p>" + p + "</p>"
                        if use_summary: formatted_p += "<div class='summary-blank'>📝 문단 요약 연습: </div>"
                    full_html += f'<div class="passage">{formatted_p}</div>'
                full_html += html_problems + html_answers + HTML_TAIL
                st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": current_topic}
                status.success("✅ 비문학 생성 완료!"); st.session_state.generation_requested = False
            except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 📖 2. 문학(소설) 문제 제작 함수 (원본 100% 무삭제 복구)
# ==========================================
def fiction_app():
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="fic_t")
        st.header("1️⃣ 작품 정보"); work_name = st.text_input("작품명", key="fic_n"); author_name = st.text_input("작가명", key="fic_a")
        st.header("2️⃣ 문제 유형 및 개수")
        uv = st.checkbox("1. 어휘 문제 (단답형)", value=True, key="fv"); cv = st.number_input("수", 1, 20, 5, key="fcv") if uv else 0
        ue = st.checkbox("2. 서술형 심화 (감상)", value=True, key="fe"); ce = st.number_input("수", 1, 10, 3, key="fce") if ue else 0
        um = st.checkbox("3. 객관식 (일반)", value=True, key="fm"); cm = st.number_input("수", 1, 10, 3, key="fcm") if um else 0
        ub = st.checkbox("4. 객관식 (보기 적용)", value=True, key="fb"); cb = st.number_input("수", 1, 10, 2, key="fcb") if ub else 0
        st.caption("3️⃣ 분석 및 정리 활동 (서술형/표)")
        u5 = st.checkbox("5. 주요 등장인물 정리 (표)", key="f5"); u6 = st.checkbox("6. 소설 속 상황 요약", key="f6")
        u7 = st.checkbox("7. 인물 관계도 및 갈등", key="f7"); u8 = st.checkbox("8. 갈등 구조 및 심리 정리", key="f8")

    if st.session_state.generation_requested:
        text = st.session_state.fiction_novel_text_input_area
        if not text: st.warning("본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty(); status.info("⚡ 소설 심층 분석 및 문제 제작 중...")
        try:
            req_list = []
            if uv: req_list.append('<div class="type-box"><h3>유형 1. 어휘 문제 (' + str(cv) + '문항)</h3>- 지문의 어려운 어휘 ' + str(cv) + '개의 의미 묻기 (단답형).<div class="question-box"><span class="question-text">[번호] "____"의 문맥적 의미는?</span><div class="write-box" style="height:50px;"></div></div></div>')
            if ue: req_list.append('<div class="type-box"><h3>유형 2. 서술형 심화 문제 (' + str(ce) + '문항)</h3>- 작가의 의도, 효과, 이유를 묻는 고난도 서술형.<div class="question-box"><span class="question-text">[번호] (질문)</span><div class="write-box"></div></div></div>')
            if um: req_list.append('<div class="type-box"><h3>유형 3. 객관식 문제 (일반) (' + str(cm) + '문항)</h3>- 수능형 5지 선다 (추론/비판).<div class="question-box"><span class="question-text">[번호] (발문)</span><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div></div>')
            if ub: req_list.append('<div class="type-box"><h3>유형 4. 객관식 문제 (보기 적용) (' + str(cb) + '문항)</h3>- **<보기>** 박스 필수 포함 (3점 킬러문항).<div class="question-box"><span class="question-text">[번호] <보기>를 참고하여 감상한 내용으로 적절하지 않은 것은? [3점]</span><div class="example-box">(보기 내용)</div><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div></div>')
            if u5: req_list.append('<div class="type-box"><h3>유형 5. 주요 등장인물 정리</h3>- 인물명, 호칭, 역할, 심리 빈칸 표 제공.</div>')
            if u6: req_list.append('<div class="type-box"><h3>유형 6. 소설 속 상황 요약</h3>- 핵심 갈등 요약 서술.<div class="write-box"></div></div>')
            if u7: req_list.append('<div class="type-box"><h3>유형 7. 인물 관계도 및 갈등</h3>- 직접 그릴 수 있는 박스.<div class="write-box" style="height:200px;"></div></div>')
            if u8: req_list.append('<div class="type-box"><h3>유형 8. 갈등 구조 및 심리 정리</h3>- 갈등 양상 및 비판 의도 서술.<div class="write-box"></div></div>')
            
            r_str = "\n".join(req_list)
            p1_p = """
당신은 수능 문학 출제위원입니다. 작품 '{W_N}'({A_N}) 기반 학생용 문제지(HTML)를 작성하시오.
# 🚨 [수능 최고난도 출제 지침]
1. **[복합적 사고]**: 작품 전체 맥락과 함축적 의미를 종합해야 풀 수 있는 문제.
2. **[매력적인 오답]**: 부분적 진실, 주객 전도, 과잉 해석 함정 배치.
3. **[보기 적용]**: 비평적 관점을 적용해 새롭게 해석하는 3점 문항.

# 🚨 [매우 중요] h1, h2 제목 생성 금지. 본문 내용부터 바로 출력.
본문: {BODY}
[출제 요청 목록]:
{REQS}
            """.format(W_N=work_name, A_N=author_name, BODY=text, REQS=r_str)
            
            res_q = generate_content_with_fallback(p1_p, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            html_q = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_q, flags=re.DOTALL | re.IGNORECASE)

            p2_p = """
당신은 수능 문학 해설 위원입니다. 앞서 출제된 문제들에 대한 **완벽한 정답 및 해설**을 <div class="answer-sheet"> 내부에 작성하시오.
**[작성 규칙]**: 1. 객관식은 [정답], [상세 해설], [오답 분석] 필수. 2. 활동형은 예시 답안 제시.
[입력 문제 내용]: {Q_TEXT}
            """.format(Q_TEXT=html_q)
            res_a = generate_content_with_fallback(p2_p, status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()
            
            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, work_name)
            full_html += f'<div class="passage">{text.replace(chr(10), "<br>")}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": work_name}
            status.success("✅ 문학 분석 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🌸 3. 현대시 고난도 문항 제작 함수 (원본 디자인 통일)
# ==========================================
def poetry_app():
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        c_title = st.text_input("메인 타이틀", value="사계국어 모의고사", key="po_t")
        st.header("1️⃣ 작품 정보"); po_n = st.text_input("작품명", key="po_n"); po_a = st.text_input("작가명", key="po_a")
        st.header("2️⃣ 문항 제작 및 개수 (1~5개)")
        ct1 = st.checkbox("1. 작품 개요 문제", value=True); nt1 = st.number_input("수", 1, 5, 1, key="pn1") if ct1 else 0
        ct2 = st.checkbox("2. 핵심 내용 정리 문제", value=True); nt2 = st.number_input("수", 1, 5, 1, key="pn2") if ct2 else 0
        ct3 = st.checkbox("3. 주요 소재의 의미 문제", value=True); nt3 = st.number_input("수", 1, 5, 2, key="pn3") if ct3 else 0
        ct4 = st.checkbox("4. 표현상의 특징 문제", value=True); nt4 = st.number_input("수", 1, 5, 2, key="pn4") if ct4 else 0
        ct5 = st.checkbox("5. 작품의 이해와 감상 문제", value=True); nt5 = st.number_input("수", 1, 5, 1, key="pn5") if ct5 else 0
        ct6 = st.checkbox("6. 수능의 키포인트 문제", value=True); nt6 = st.number_input("수", 1, 5, 1, key="pn6") if ct6 else 0
        ct7 = st.checkbox("7. 다른 작품과의 연계성 문제", value=True); nt7 = st.number_input("수", 1, 5, 1, key="pn7") if ct7 else 0
        st.header("3️⃣ 추가 세트")
        ct8 = st.checkbox("8. 수능형 선지 O,X 세트", value=True); nt8 = st.number_input("OX수", 1, 15, 10, key="pn8") if ct8 else 0
        ct9 = st.checkbox("9. 수능형 서술형 문제", value=True); nt9 = st.number_input("서술수", 1, 10, 3, key="pn9") if ct9 else 0

    if st.session_state.generation_requested:
        text = st.session_state.get("poetry_text_input_area", "")
        if not text: st.warning("시 본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty(); status.info("⚡ 현대시 고난도 문항 제작 중...")
        try:
            r_list = []
            if ct1: r_list.append("<h3>문항 1. 작품 개요 파악 (" + str(nt1) + "개)</h3>- 갈래, 성격, 주제 등을 묻는 실제 문제 형식.")
            if ct2: r_list.append("<h3>문항 2. 핵심 내용 정리 (" + str(nt2) + "개)</h3>- 시상 전개 과정이나 시적 상황을 묻는 질문.")
            if ct3: r_list.append("<h3>문항 3. 주요 소재의 상징성 (" + str(nt3) + "개)</h3>- 특정 시어의 함축적 의미를 묻는 질문.")
            if ct4: r_list.append("<h3>문항 4. 표현상의 특징/수사법 (" + str(nt4) + "개)</h3>- 심상, 운율, 비유의 효과를 묻는 질문.")
            if ct5: r_list.append("<h3>문항 5. 작품의 이해와 감상 (" + str(nt5) + "개)</h3>- 작품 전체의 내외적 가치 감상 질문.")
            if ct6: r_list.append("<h3>문항 6. 수능 빈출 킬러 포인트 (" + str(nt6) + "개)</h3>- 고난도 사고를 요하는 수능형 실제 질문.")
            if ct7: r_list.append("<h3>문항 7. 타 작품과의 연계 비교 (" + str(nt7) + "개)</h3>- <보기>를 활용해 타 시와의 공통점/차이점을 묻는 질문.")
            if ct8: r_list.append("<h3>문항 8. 수능형 선지 OX 판단 (" + str(nt8) + "개)</h3>- 문항 끝에 ( ) 빈칸 출력. 정답 절대 포함 금지.")
            if ct9: r_list.append("<h3>문항 9. 고난도 수능형 서술형 (" + str(nt9) + "개)</h3>- 특정 조건(시어 사용 등)을 제시한 고난도 질문.")
            
            r_str = "\n".join(r_list)
            p_q = """
당신은 대한민국 수능 국어 출제 위원장입니다. 현대시 '{W_N}'({A_N})를 바탕으로 학생용 시험지(HTML)를 제작하시오.

🚨 [출제 지침]:
- '이 작품의 킬러 포인트는?' 같은 메타 질문을 절대 던지지 마시오. 
- 대신, 지문의 특정 구절이나 화자의 정서, 심상 등을 근거로 삼아 학생이 깊이 사고해야 풀 수 있는 '실제 수능형 문항'을 제작하시오.
- 디자인: 반드시 `type-box`, `question-box`, `choices`, `example-box` 클래스를 사용하여 기존 비문학/문학 코드와 완벽히 통일된 디자인을 갖출 것.
- 힌트 금지: '※ ~를 고려하시오'와 같은 추가 가이드나 힌트는 절대 포함하지 말 것. 오직 문제와 선지만 제시할 것.
- 정답 비공개: 8번 OX는 ( ) 빈칸으로 출력하고, 모든 문제의 정답은 학생용지에 절대 노출하지 말 것.

본문: {BODY}
요청 문항:
{REQS}
            """.format(W_N=po_n, A_N=po_a, BODY=text, REQS=r_str)
            
            res_q = generate_content_with_fallback(p_q, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            html_q = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_q, flags=re.DOTALL | re.IGNORECASE)
            
            p_a = "위 현대시 문항들에 대해 교사 전용의 완벽 정답 및 상세 근거 해설을 <div class='answer-sheet'> 내부에 작성하시오.\nOX는 반드시 정답(O/X)과 지문 근거를 제시할 것.\n문제 내용: " + html_q
            res_a = generate_content_with_fallback(p_a, status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()
            
            full_html = HTML_HEAD + get_custom_header_html(c_title, po_n)
            full_html += f'<div class="poetry-passage">{text}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": c_title, "topic_title": po_n}
            status.success("✅ 현대시 생성 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🚀 메인 실행 로직
# ==========================================
def display_results():
    if st.session_state.generated_result:
        res = st.session_state.generated_result
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🔄 다시 생성"):
                st.session_state.generated_result = None; st.session_state.generation_requested = True; st.rerun()
        with c2: st.download_button("📥 HTML 저장", res["full_html"], "exam.html", "text/html")
        with c3:
            docx = create_docx(res["full_html"], "exam.docx", res["main_title"], res["topic_title"])
            st.download_button("📄 Word 저장", docx, "exam.docx")
        st.components.v1.html(res["full_html"], height=800, scrolling=True)

st.title("📚 사계국어 모의고사 제작 시스템")
st.markdown("---")
col_L, col_R = st.columns([1.5, 3])

with col_L:
    st.radio("모드 선택", ["⚡ 비문학 문제 제작", "📖 문학 문제 제작", "🌸 현대시 문제 제작"], key="app_mode")

with col_R:
    if st.session_state.app_mode == "⚡ 비문학 문제 제작":
        st.header("⚡ 비문학 모의평가")
        if st.session_state.get("domain_mode_select") == "직접 입력":
            m_mode = st.session_state.get("manual_mode", "단일 지문")
            if m_mode == "단일 지문": st.text_area("지문 입력 (엔터 두번으로 문단 구분)", height=300, key="manual_passage_input_col_main")
            else:
                ca, cb = st.columns(2)
                with ca: st.text_area("(가) 지문", height=300, key="manual_passage_input_a")
                with cb: st.text_area("(나) 지문", height=300, key="manual_passage_input_b")
        if st.button("🚀 모의고사 생성", key="r_nf"): st.session_state.generation_requested = True
        non_fiction_app()
    elif st.session_state.app_mode == "🌸 현대시 문제 제작":
        st.header("🌸 현대시 고난도 문항 제작")
        st.text_area("시 본문 입력 (행/연 구분을 위해 줄바꿈을 정확히 해주세요)", height=400, key="poetry_text_input_area")
        if st.button("🚀 문항 제작 시작", key="r_po"): st.session_state.generation_requested = True
        poetry_app()
    else:
        st.header("📖 문학 심층 분석")
        st.text_area("작품 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 분석 생성", key="r_fi"): st.session_state.generation_requested = True
        fiction_app()

display_results()
