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
        
        /* 현대시 줄바꿈 보존 스타일 */
        .poetry-passage {
            white-space: pre-wrap; font-family: 'Batang', serif; line-height: 2.2;
            font-size: 11pt; border: 1px solid #444; padding: 35px;
            margin-bottom: 40px; background-color: #fff;
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
        
        @media print { body { padding: 0; } }
    </style>
</head>
<body>
""" 
HTML_TAIL = "</body></html>" 

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
            if model_name.startswith("gpt"):
                if not openai_client: continue
                response = openai_client.chat.completions.create(
                    model=model_name, 
                    messages=[{"role": "system", "content": "당신은 대한민국 수능 국어 출제 위원장입니다."}, {"role": "user", "content": prompt}],
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
            last_exception = e
            continue 
    if last_exception: raise last_exception
    else: raise Exception("모델 응답 실패")

def create_docx(html_content, file_name, main_title, topic_title):
    document = Document()
    document.add_heading(main_title, 0).alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_time = document.add_paragraph("소요 시간: ___________")
    p_time.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_topic = document.add_paragraph(f"주제: {topic_title}")
    p_topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("-" * 50)
    clean_text = re.sub(r'<[^>]+>', '\n', html_content)
    document.add_paragraph(re.sub(r'\n+', '\n', clean_text).strip()) 
    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream 

# ==========================================
# 🧩 1. 비문학 문제 제작 함수 (원래 코드 유지)
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
        if current_d_mode == 'AI 생성':
            mode = st.radio("구성", ["단일 지문", "주제 통합"], key="ai_mode")
            if mode == "단일 지문":
                domain = st.selectbox("영역", ["인문", "사회", "과학", "기술", "예술"], key="domain_select")
                topic = st.text_input("주제", placeholder="예: 금리 인하", key="topic_input")
            else:
                topic = st.text_input("주제", placeholder="예: (가) 공리주의 / (나) 의무론", key="topic_input_mix")
            difficulty = st.select_slider("난이도", ["중", "상", "최상"], value="최상")
        else: 
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합"], key="manual_mode")
            topic = "사용자 지문"
        st.markdown("---")
        st.header("2️⃣ 문제 유형 및 개수 선택")
        label_t1 = "1. 핵심 주장 요약 (서술형)" if (not current_d_mode == 'AI 생성' or mode == '단일 지문') else "1. (가),(나) 요약 및 연관성 서술"
        select_t1 = st.checkbox(label_t1, value=True, key="select_t1")
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

    if st.session_state.generation_requested:
        manual_p = ""
        if current_d_mode == '직접 입력':
            if mode == '단일 지문': manual_p = st.session_state.get("manual_passage_input_col_main", "")
            else: manual_p = f"[가] 지문:\n{st.session_state.get('manual_passage_input_a','')}\n\n[나] 지문:\n{st.session_state.get('manual_passage_input_b','')}"
        
        status = st.empty()
        try:
            reqs = []
            if select_t1: reqs.append(f'<div class="question-box"><span class="question-text">1. {label_t1}</span><div class="write-box"></div></div>')
            if select_t2: reqs.append(f'<h3>내용 일치 O/X ({count_t2}문항)</h3>')
            if select_t3: reqs.append(f'<h3>빈칸 채우기 ({count_t3}문항)</h3>')
            if select_t4: reqs.append(f'<h3>변형 문장 정오판단 ({count_t4}문항)</h3>')
            mcq = '<div class="question-box"><span class="question-text">[문제번호] [발문]</span><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div>'
            if select_t5: reqs.append(f'<h3>객관식: 세부 내용 ({count_t5}문항)</h3>{mcq}')
            if select_t6: reqs.append(f'<h3>객관식: 추론 및 비판 ({count_t6}문항)</h3>{mcq}')
            if select_t7: reqs.append(f'<h3>객관식: [보기] 적용 ({count_t7}문항)</h3>')
            
            prompt = f"수능 국어 출제 위원장으로서 HTML 모의고사 생성(h1, h2 금지).\n요청:\n" + "\n".join(reqs) + f"\n지문:{manual_p}\n주제:{topic}\n문단요약:{use_summary}"
            res_q = generate_content_with_fallback(prompt, status_placeholder=status)
            html_q = res_q.text.replace("```html", "").replace("```", "").strip()
            
            res_a = generate_content_with_fallback(f"위 문제의 정답 및 해설을 <div class='answer-sheet'>에 작성.\n{html_q}", status_placeholder=status)
            html_a = res_a.text.replace("```html", "").replace("```", "").strip()

            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, topic)
            if current_d_mode == '직접 입력':
                paras = "".join([f"<p>{p.strip()}</p>" + ("<div class='summary-blank'>📝 문단 요약 연습</div>" if use_summary else "") for p in re.split(r'\n\s*\n', manual_p.strip()) if p.strip()])
                full_html += f'<div class="passage">{paras}</div>'
            full_html += html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": topic}
            status.success("✅ 비문학 생성 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 📖 2. 문학(소설) 문제 제작 함수 (원래 코드 유지)
# ==========================================
def fiction_app():
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="fic_custom_main_title")
        st.header("1️⃣ 작품 정보")
        work_name = st.text_input("작품명", key="fic_name")
        author_name = st.text_input("작가명", key="fic_auth")
        st.header("2️⃣ 문제 유형 선택")
        use_v = st.checkbox("1. 어휘 (단답)", value=True, key="fic_t1")
        cnt_v = st.number_input(" - 문항 수", 1, 20, 5, key="fic_cnt_1") if use_v else 0
        use_e = st.checkbox("2. 서술형 (감상)", value=True, key="fic_t2")
        cnt_e = st.number_input(" - 문항 수", 1, 10, 3, key="fic_cnt_2") if use_e else 0
        use_m = st.checkbox("3. 객관식 (일반)", value=True, key="fic_t3_gen")
        cnt_m = st.number_input(" - 문항 수", 1, 10, 3, key="fic_cnt_3_gen") if use_m else 0
        use_b = st.checkbox("4. 객관식 (보기 적용)", value=True, key="fic_t4_bogey")
        cnt_b = st.number_input(" - 문항 수", 1, 10, 2, key="fic_cnt_4_bogey") if use_b else 0
        st.caption("3️⃣ 분석 및 정리 활동")
        use_char = st.checkbox("5. 인물 정리", key="fic_t5_char")
        use_summ = st.checkbox("6. 상황 요약", key="fic_t6_summ")
        use_rel = st.checkbox("7. 관계도", key="fic_t7_rel")
        use_conf = st.checkbox("8. 갈등 정리", key="fic_t8_conf")

    if st.session_state.generation_requested:
        text = st.session_state.fiction_novel_text_input_area
        if not text: st.warning("본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty()
        try:
            reqs = [f"어휘 {cnt_v}개" if use_v else "", f"서술형 {cnt_e}개" if use_e else "", f"객관식 {cnt_m}개" if use_m else "", f"보기객관식 {cnt_b}개" if use_b else "", "인물정리" if use_char else "", "요약" if use_summ else "", "관계도" if use_rel else "", "갈등정리" if use_conf else ""]
            prompt = f"수능 국어 위원장으로서 소설 '{work_name}' 기반 HTML 문제지 작성.\n본문:\n{text}\n유형:\n" + "\n".join(reqs)
            res_q = generate_content_with_fallback(prompt, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            res_a = generate_content_with_fallback(f"위 문제의 정답 및 해설을 <div class='answer-sheet'>에 작성.\n{html_q}", status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()
            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, work_name)
            full_html += f'<div class="passage">{text.replace(chr(10), "<br>")}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": work_name}
            status.success("✅ 문학 생성 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🌸 3. [개선] 현대시 문제 제작 함수
# ==========================================
def poetry_app():
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="po_main_t")
        st.markdown("---")
        st.header("1️⃣ 작품 정보")
        po_name = st.text_input("작품명", key="po_name")
        po_auth = st.text_input("작가명", key="po_auth")
        
        st.markdown("---")
        st.header("2️⃣ 문항 제작 유형 및 문제 수")
        
        # 각 유형별 체크박스와 문제 수 설정 (1~5개)
        c1 = st.checkbox("1. 작품 개요 파악 문항", value=True)
        n1 = st.number_input(" - 문항 수", 1, 5, 1, key="po_n1") if c1 else 0
        
        c2 = st.checkbox("2. 시상 전개 및 핵심 내용 문항", value=True)
        n2 = st.number_input(" - 문항 수", 1, 5, 1, key="po_n2") if c2 else 0
        
        c3 = st.checkbox("3. 시어의 상징적 의미 문항", value=True)
        n3 = st.number_input(" - 문항 수", 1, 5, 2, key="po_n3") if c3 else 0
        
        c4 = st.checkbox("4. 표현상의 특징 및 효과 문항", value=True)
        n4 = st.number_input(" - 문항 수", 1, 5, 2, key="po_n4") if c4 else 0
        
        c5 = st.checkbox("5. 작품의 이해와 감상 문항", value=True)
        n5 = st.number_input(" - 문항 수", 1, 5, 1, key="po_n5") if c5 else 0
        
        c6 = st.checkbox("6. 수능 킬러 개념(키포인트) 문항", value=True)
        n6 = st.number_input(" - 문항 수", 1, 5, 1, key="po_n6") if c6 else 0
        
        c7 = st.checkbox("7. 다른 작품과의 연계 비교 문항", value=True)
        n7 = st.number_input(" - 문항 수", 1, 5, 1, key="po_n7") if c7 else 0
        cnt_rel_works = st.slider(" - 연계 작품 수(보기 제시용)", 1, 5, 1) if c7 else 0
        
        st.markdown("---")
        st.header("3️⃣ 추가 문항 설정")
        c8 = st.checkbox("8. 수능형 선지 O,X 세트", value=True)
        n8 = st.number_input(" - OX 문항 수", 1, 15, 10, key="po_n8") if c8 else 0
        
        c9 = st.checkbox("9. 고난도 수능형 서술형", value=True)
        n9 = st.number_input(" - 서술형 문항 수", 1, 5, 2, key="po_n9") if c9 else 0

    if st.session_state.generation_requested:
        po_text = st.session_state.get("poetry_text_input_area", "")
        if not po_text: st.warning("시 본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty(); status.info("⚡ 현대시 시험지 및 분석 문항 생성 중...")
        
        try:
            reqs = []
            if c1: reqs.append(f"<h3>문항 1. 작품 개요 파악 ({n1}문항)</h3>- 갈래, 성격, 주제 등을 묻는 질문")
            if c2: reqs.append(f"<h3>문항 2. 시상 전개 및 핵심 내용 ({n2}문항)</h3>- 정서 변화 및 흐름 파악 질문")
            if c3: reqs.append(f"<h3>문항 3. 시어의 상징적 의미 ({n3}문항)</h3>- 특정 시어의 함축적 의미 질문")
            if c4: reqs.append(f"<h3>문항 4. 표현상의 특징 및 효과 ({n4}문항)</h3>- 수사법 및 운율의 효과 질문")
            if c5: reqs.append(f"<h3>문항 5. 작품의 이해와 감상 ({n5}문항)</h3>- 수능형 고난도 감상 질문")
            if c6: reqs.append(f"<h3>문항 6. 수능의 키포인트 ({n6}문항)</h3>- 킬러급 개념 적용 질문")
            if c7: reqs.append(f"<h3>문항 7. 다른 작품과의 연계성 ({n7}문항)</h3>- 타 작품 {cnt_rel_works}개를 <보기>로 활용한 비교 질문")
            if c8: reqs.append(f"<h3>문항 8. 수능형 선지 O,X 세트 ({n8}문항)</h3>- **[주의] 학생용지에는 절대 정답을 표시하지 말고**, 빈 괄호 ( ) 만 출력하시오.")
            if c9: reqs.append(f"<h3>문항 9. 고난도 수능형 서술형 ({n9}문항)</h3>- 구체적 조건이 포함된 질문만 작성하시오.<div class='write-box'></div>")
            
            prompt_q = f"""
            대한민국 수능 국어 출제 위원장으로서 현대시 '{po_name}'({po_auth})를 바탕으로 학생용 문제지(HTML)를 작성하시오.
            
            [지침]
            - **학생용지에는 절대 정답이나 해설을 포함하지 마시오.**
            - 모든 항목은 단순히 설명하는 것이 아니라 학생들이 직접 풀 수 있는 '질문(문항)' 형태로 만드시오.
            - 시 본문:\n{po_text}
            
            [출제 요청 문항]
            {chr(10).join(reqs)}
            """
            res_q = generate_content_with_fallback(prompt_q, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            html_q = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_q, flags=re.DOTALL | re.IGNORECASE)

            prompt_a = f"""
            당신은 수능 국어 해설 위원입니다. 위 문항들에 대한 완벽한 교사용 '정답 및 상세 해설'을 작성하시오.
            OX 문항은 정답(O/X)과 지문 근거를 반드시 포함하고, 서술형은 모범 답안을 제시하시오.
            반드시 <div class="answer-sheet"> 태그 내부에 작성하시오.
            입력된 문항 내용: {html_q}
            """
            res_a = generate_content_with_fallback(prompt_a, status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()

            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, f"{po_name}({po_auth})")
            full_html += f'<div class="poetry-passage">{po_text}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": po_name}
            status.success("✅ 현대시 모의고사 생성 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🚀 결과 출력 및 메인 로직
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
            if st.session_state.get("manual_mode", "단일 지문") == "단일 지문":
                st.text_area("지문 입력", height=300, key="manual_passage_input_col_main")
            else:
                c1, c2 = st.columns(2)
                with c1: st.text_area("(가) 지문", height=300, key="manual_passage_input_a")
                with c2: st.text_area("(나) 지문", height=300, key="manual_passage_input_b")
        if st.button("🚀 모의고사 생성", key="run_nf"): st.session_state.generation_requested = True
        non_fiction_app()
    elif st.session_state.app_mode == "🌸 현대시 문제 제작":
        st.header("🌸 현대시 문항 제작")
        st.text_area("시 본문 입력 (행/연 구분을 위해 줄바꿈을 정확히 해주세요)", height=400, key="poetry_text_input_area")
        if st.button("🚀 문항 제작 시작", key="run_po"): st.session_state.generation_requested = True
        poetry_app()
    else:
        st.header("📖 문학 심층 분석")
        st.text_area("작품 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 분석 생성", key="run_fi"): st.session_state.generation_requested = True
        fiction_app()

display_results()
