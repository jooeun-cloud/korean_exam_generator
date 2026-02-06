import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import openai
import re
import os
from docx import Document
from io import BytesIO
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH 
import time

# ==========================================
# [설정] 페이지 기본 설정
# ==========================================
st.set_page_config(page_title="사계국어 모의고사 시스템", page_icon="📚", layout="wide")

# ==========================================
# [설정] API 클라이언트 초기화
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
    pass

MODEL_PRIORITY = [
    "gpt-4o",               
    "gemini-1.5-pro",       
    "gemini-1.5-flash"      
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
        body { font-family: 'Malgun Gothic', 'Batang', serif; padding: 40px; max-width: 900px; margin: 0 auto; line-height: 1.6; color: #000; font-size: 11pt; }
        .header-container { margin-bottom: 30px; border-bottom: 2px solid #000; padding-bottom: 15px; text-align: center; }
        .top-row { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 20px; }
        .main-title { font-size: 26px; font-weight: 800; margin: 0; letter-spacing: -0.5px; color: #000; line-height: 1.2; flex-grow: 1; text-align: left; }
        .time-box { font-size: 14px; font-weight: bold; border: 1px solid #000; padding: 5px 15px; border-radius: 4px; white-space: nowrap; }
        .topic-info { font-size: 16px; font-weight: 800; color: #000; background-color: #f4f4f4; padding: 8px 20px; display: inline-block; border-radius: 8px; margin-top: 5px; }
        .passage { font-size: 10.5pt; border: 1px solid #444; padding: 30px; margin-bottom: 40px; background-color: #fff; line-height: 1.8; text-align: justify; }
        .poetry-passage { white-space: pre-wrap; font-family: 'Batang', serif; line-height: 2.2; text-align: left; border: 1px solid #444; padding: 30px; margin-bottom: 40px; background-color: #fff; font-size: 11pt; }
        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        h3 { font-size: 1.2em; color: #000; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px; font-weight: bold; margin-top: 40px; }
        .question-box { margin-bottom: 40px; page-break-inside: avoid; }
        .question-text { font-weight: bold; margin-bottom: 15px; display: block; font-size: 1.1em; word-break: keep-all;}
        .example-box { border: 1px solid #444; padding: 15px; margin: 15px 0 20px 0; background-color: #fff; font-size: 0.95em; position: relative; }
        .example-box::before { content: "< 보 기 >"; display: block; text-align: center; font-weight: bold; color: #333; margin-bottom: 10px; }
        .choices { margin-top: 15px; font-size: 1em; margin-left: 15px; }
        .choices div { margin-bottom: 8px; padding-left: 15px; text-indent: -15px; }
        .write-box { margin-top: 15px; height: 120px; border: 1px solid #ccc; border-radius: 4px; background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); line-height: 30px; }
        .summary-blank { border: 1px dashed #aaa; padding: 15px; margin: 15px 0 25px 0; min-height: 60px; color: #666; font-size: 0.9em; background-color: #fcfcfc; }
        .answer-sheet { background: #f8f9fa; padding: 40px; margin-top: 60px; border-top: 4px double #333; page-break-before: always; }
        .ans-main-title { font-size: 1.6em; font-weight: bold; text-align: center; margin-bottom: 40px; padding-bottom: 15px; border-bottom: 3px double #999; }
        .ans-item { margin-bottom: 50px; border-bottom: 1px dashed #ccc; padding-bottom: 30px; }
        .ans-type-badge { display: inline-block; background-color: #555; color: #fff; padding: 4px 12px; border-radius: 15px; font-size: 0.85em; font-weight: bold; margin-bottom: 12px; }
        .ans-num { font-weight: bold; color: #d63384; font-size: 1.3em; display: block; margin-bottom: 15px; }
        .ans-content-title { font-weight: bold; color: #2c3e50; margin-top: 20px; margin-bottom: 8px; font-size: 1.05em; display: block; border-left: 4px solid #2c3e50; padding-left: 10px; }
        .ans-text { display: block; margin-left: 5px; color: #333; line-height: 1.8; }
        .ans-wrong-box { background-color: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-top: 10px; color: #555; }
        .summary-ans-box { background-color: #e3f2fd; padding: 25px; margin-bottom: 50px; border-radius: 10px; border: 1px solid #90caf9; }
    </style>
</head>
<body>
"""
HTML_TAIL = "</body></html>"

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
        <div class="topic-info">주제/작품: {topic_info}</div>
    </div>
    """

def generate_content_with_fallback(prompt, generation_config=None, status_placeholder=None):
    last_exception = None
    for model_name in MODEL_PRIORITY:
        try:
            if status_placeholder:
                status_placeholder.info(f"⚡ 생성 중... ({model_name})")
            if model_name.startswith("gpt"):
                if not openai_client: continue
                response = openai_client.chat.completions.create(
                    model=model_name, 
                    messages=[{"role": "system", "content": "당신은 대한민국 수능 국어 출제 위원장입니다."}, {"role": "user", "content": prompt}],
                    max_completion_tokens=8192 if not generation_config else generation_config.max_output_tokens,
                    temperature=0.7 if not generation_config else generation_config.temperature
                )
                class OpenAIWrapper:
                    def __init__(self, t): self.text = t
                return OpenAIWrapper(response.choices[0].message.content)
            else:
                model = genai.GenerativeModel(model_name)
                return model.generate_content(prompt, generation_config=generation_config)
        except Exception as e:
            last_exception = e
            continue 
    raise last_exception if last_exception else Exception("AI 모델 응답 실패")

def create_docx(html_content, file_name, main_title, topic_title):
    document = Document()
    document.add_heading(main_title, 0).alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_time = document.add_paragraph("소요 시간: ___________")
    p_time.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_topic = document.add_paragraph(f"주제/작품: {topic_title}")
    p_topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("-" * 50)
    clean_text = re.sub(r'<[^>]+>', '\n', html_content)
    document.add_paragraph(re.sub(r'\n+', '\n', clean_text).strip())
    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream

# ==========================================
# 🧩 1. 비문학 문제 제작 함수
# ==========================================
def non_fiction_app():
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
                domain = "주제 통합"
            difficulty = st.select_slider("난이도", ["중", "상", "최상"], value="최상")
        else:
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합"], key="manual_mode")
            domain = "사용자 입력"
            topic = "사용자 지문"
            difficulty = "사용자 지정"

        st.markdown("---")
        st.header("2️⃣ 문제 유형 선택")
        label_t1 = "1. 핵심 주장 요약" if mode == "단일 지문" else "1. (가),(나) 요약 및 연관성"
        select_t1 = st.checkbox(label_t1, value=True)
        select_t2 = st.checkbox("2. 내용 일치 O/X")
        count_t2 = st.number_input(" - OX 문항 수", 1, 10, 2) if select_t2 else 0
        select_t3 = st.checkbox("3. 빈칸 채우기")
        count_t3 = st.number_input(" - 빈칸 문항 수", 1, 10, 2) if select_t3 else 0
        select_t5 = st.checkbox("4. 객관식 (세부 내용)", value=True)
        count_t5 = st.number_input(" - 객관식 수", 1, 10, 2) if select_t5 else 0
        select_t7 = st.checkbox("5. 객관식 (보기 적용)", value=True)
        count_t7 = st.number_input(" - 보기 적용 수", 1, 5, 1) if select_t7 else 0
        use_summary = st.checkbox("📌 문단별 요약 칸 생성", value=True)

    if st.session_state.generation_requested:
        manual_p = ""
        if current_d_mode == '직접 입력':
            if mode == '단일 지문': manual_p = st.session_state.get("manual_passage_input_col_main", "")
            else: manual_p = f"[가]\n{st.session_state.get('manual_passage_input_a','')}\n\n[나]\n{st.session_state.get('manual_passage_input_b','')}"
            if not manual_p.strip(): 
                st.warning("지문을 입력하세요."); st.session_state.generation_requested = False; return
        elif not topic:
            st.warning("주제를 입력하세요."); st.session_state.generation_requested = False; return

        status = st.empty()
        try:
            reqs = []
            if select_t1: reqs.append(f'<div class="question-box"><span class="question-text">1. {label_t1}</span><div class="write-box"></div></div>')
            if select_t2: reqs.append(f'<h3>내용 일치 O/X ({count_t2}문항)</h3>')
            if select_t3: reqs.append(f'<h3>빈칸 채우기 ({count_t3}문항)</h3>')
            if select_t5: reqs.append(f'<h3>객관식: 세부 내용 ({count_t5}문항)</h3>')
            if select_t7: reqs.append(f'<h3>객관식: [보기] 적용 ({count_t7}문항)</h3>')
            
            sum_inst = "<div class='summary-blank'>📝 문단 요약 연습</div> 코드를 각 문단 끝에 삽입" if use_summary else ""
            p_inst = f"주제 {topic}, 난이도 {difficulty} 지문 작성 및 {sum_inst}" if current_d_mode == 'AI 생성' else "제공된 지문 기반 문제 출제"
            
            prompt = f"수능 국어 출제위원으로서 다음 요청을 HTML로 수행하시오(h1, h2 금지).\n{p_inst}\n지문:\n{manual_p}\n요청:\n" + "\n".join(reqs)
            res = generate_content_with_fallback(prompt, status_placeholder=status)
            html_q = res.text.replace("```html","").replace("```","").strip()
            
            ans_prompt = f"위 문제에 대한 정답과 해설을 <div class='answer-sheet'> 내부에 작성하시오.\n문제:\n{html_q}"
            res_a = generate_content_with_fallback(ans_prompt, status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()

            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, topic)
            if current_d_mode == '직접 입력':
                paras = "".join([f"<p>{p}</p>" + ("<div class='summary-blank'>📝 문단 요약 연습</div>" if use_summary else "") for p in manual_p.split('\n\n')])
                full_html += f'<div class="passage">{paras}</div>'
            
            full_html += html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": topic}
            status.success("✅ 생성 완료")
        except Exception as e: status.error(f"오류: {e}")
        st.session_state.generation_requested = False

# ==========================================
# 🧩 2. 문학(소설) 문제 제작 함수
# ==========================================
def fiction_app():
    with st.sidebar:
        st.header("🏫 타이틀")
        custom_main_title = st.text_input("메인 타이틀", value="사계국어 모의고사", key="fic_custom_main_title")
        st.header("1️⃣ 작품 정보")
        work_name = st.text_input("작품명", key="fic_name")
        author_name = st.text_input("작가명", key="fic_auth")
        st.header("2️⃣ 유형 선택")
        use_v = st.checkbox("1. 어휘 (단답)", value=True)
        use_e = st.checkbox("2. 서술형 (감상)", value=True)
        use_m = st.checkbox("3. 객관식 (일반)", value=True)
        use_b = st.checkbox("4. 객관식 (보기)", value=True)
        use_char = st.checkbox("5. 등장인물 정리")
        use_summ = st.checkbox("6. 상황 요약")

    if st.session_state.generation_requested:
        text = st.session_state.fiction_novel_text_input_area
        if not text: st.warning("본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty()
        try:
            reqs = []
            if use_v: reqs.append("어휘 문제 (단답형)")
            if use_e: reqs.append("서술형 심화 (작가 의도/효과)")
            if use_m: reqs.append("객관식 (추론/비판)")
            if use_b: reqs.append("객관식 (보기 적용 3점)")
            if use_char: reqs.append("등장인물 관계 및 심리 표 정리")
            if use_summ: reqs.append("소설 상황 요약 서술형")
            
            prompt = f"수능 국어 위원으로서 작품 '{work_name}'({author_name}) 기반 문제지 HTML 작성(h1,h2 금지).\n본문:\n{text}\n요청유형:\n" + "\n".join(reqs)
            res_q = generate_content_with_fallback(prompt, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            
            res_a = generate_content_with_fallback(f"위 문제의 정답/해설을 <div class='answer-sheet'>에 작성.\n문제:\n{html_q}", status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()

            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, f"{work_name}({author_name})")
            full_html += f'<div class="passage">{text.replace(chr(10), "<br>")}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": work_name}
            status.success("✅ 생성 완료")
        except Exception as e: status.error(f"오류: {e}")
        st.session_state.generation_requested = False

# ==========================================
# 🧩 3. [신규] 현대시 문제 제작 함수
# ==========================================
def poetry_app():
    with st.sidebar:
        st.header("🏫 타이틀")
        custom_main_title = st.text_input("메인 타이틀", value="사계국어 모의고사", key="po_main_t")
        st.header("1️⃣ 작품 정보")
        po_name = st.text_input("작품명", key="po_name")
        po_auth = st.text_input("작가명", key="po_auth")
        
        st.header("2️⃣ 분석 차트 항목")
        u1 = st.checkbox("1. 작품 개요", value=True)
        u2 = st.checkbox("2. 핵심 내용 정리", value=True)
        u3 = st.checkbox("3. 주요 소재의 의미", value=True)
        u4 = st.checkbox("4. 표현상의 특징", value=True)
        u5 = st.checkbox("5. 작품의 이해와 감상", value=True)
        u6 = st.checkbox("6. 수능의 키포인트", value=True)
        u7 = st.checkbox("7. 타 작품 연계성", value=True)
        cnt_rel = st.slider(" - 연계 작품 수", 1, 5, 2) if u7 else 0
        
        st.header("3️⃣ 문제 제작")
        u8 = st.checkbox("8. 수능형 선지 O,X", value=True)
        cnt_ox = st.number_input(" - OX 문항 수", 1, 15, 8) if u8 else 0
        u9 = st.checkbox("9. 수능형 서술형 문제", value=True)
        cnt_essay = st.number_input(" - 서술형 문항 수", 1, 10, 3) if u9 else 0

    if st.session_state.generation_requested:
        po_text = st.session_state.get("poetry_text_input_area", "")
        if not po_text: st.warning("시 본문을 입력하세요."); st.session_state.generation_requested = False; return
        status = st.empty()
        try:
            reqs = []
            if u1: reqs.append("<h3>1. 작품 개요</h3>(갈래, 성격, 주제, 특징 표 정리)")
            if u2: reqs.append("<h3>2. 핵심 내용 정리</h3>(시상 전개 요약)")
            if u3: reqs.append("<h3>3. 주요 소재의 상징적/비유적 의미</h3>(시어 풀이)")
            if u4: reqs.append("<h3>4. 표현상의 특징</h3>(운율, 심상, 기법)")
            if u5: reqs.append("<h3>5. 작품의 이해와 감상</h3>")
            if u6: reqs.append("<h3>6. 수능의 키포인트</h3>(킬러 포인트)")
            if u7: reqs.append(f"<h3>7. 다른 작품과의 연계성 ({cnt_rel}개)</h3>(유사 작품 대조)")
            if u8: reqs.append(f"<h3>8. 수능형 선지 O,X ({cnt_ox}문항)</h3>(각 문항 끝에 ( O / X ) 표시)")
            if u9: reqs.append(f"<h3>9. 수능형 서술형 문제 ({cnt_essay}문항)</h3><div class='write-box'></div>")
            
            prompt = f"수능 국어 위원으로서 현대시 '{po_name}'({po_auth}) 분석/문제 HTML 작성(h1,h2 금지).\n시 본문:\n{po_text}\n요청 항목:\n" + "\n".join(reqs)
            res_q = generate_content_with_fallback(prompt, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            
            res_a = generate_content_with_fallback(f"위 분석/문제의 정답/해설을 <div class='answer-sheet'>에 작성.\n내용:\n{html_q}", status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()

            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, f"{po_name}({po_auth})")
            full_html += f'<div class="poetry-passage">{po_text}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": po_name}
            status.success("✅ 현대시 분석지 생성 완료")
        except Exception as e: status.error(f"오류: {e}")
        st.session_state.generation_requested = False

# ==========================================
# 🚀 메인 실행부
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
    if st.session_state.app_mode == "🌸 현대시 문제 제작":
        st.header("🌸 현대시 심층 분석 차트")
        st.text_area("시 본문 입력 (행/연 구분을 정확히 입력해주세요)", height=400, key="poetry_text_input_area")
        if st.button("🚀 분석 및 문제 생성"): st.session_state.generation_requested = True
        poetry_app()
    elif st.session_state.app_mode == "⚡ 비문학 문제 제작":
        st.header("⚡ 비문학 모의평가")
        if st.session_state.get("domain_mode_select") == "직접 입력":
            if st.session_state.get("manual_mode") == "단일 지문": st.text_area("지문 입력", height=300, key="manual_passage_input_col_main")
            else:
                c1, c2 = st.columns(2)
                with c1: st.text_area("(가) 지문", height=300, key="manual_passage_input_a")
                with c2: st.text_area("(나) 지문", height=300, key="manual_passage_input_b")
        if st.button("🚀 모의고사 생성"): st.session_state.generation_requested = True
        non_fiction_app()
    else:
        st.header("📖 문학 심층 분석")
        st.text_area("소설 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 분석 생성"): st.session_state.generation_requested = True
        fiction_app()

display_results()
