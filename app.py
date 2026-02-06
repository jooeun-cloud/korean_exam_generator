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
        
        /* 현대시 전용 스타일: 줄바꿈(행/연) 보존 */
        .poetry-passage {
            white-space: pre-wrap; font-family: 'Batang', serif; line-height: 2.2;
            font-size: 11pt; border: 1px solid #444; padding: 35px;
            margin-bottom: 40px; background-color: #fff;
        }

        .type-box { margin-bottom: 30px; page-break-inside: avoid; }
        h3 { font-size: 1.2em; color: #000; border-bottom: 2px solid #000; padding-bottom: 5px; margin-bottom: 20px; font-weight: bold; margin-top: 40px; }
        .question-box { margin-bottom: 40px; page-break-inside: avoid; }
        .question-text { font-weight: bold; margin-bottom: 15px; display: block; font-size: 1.1em; word-break: keep-all;}
        .example-box { border: 1px solid #444; padding: 15px; margin: 15px 0 20px 0; background-color: #fff; font-size: 0.95em; position: relative; }
        .example-box::before { content: "< 보 기 >"; display: block; text-align: center; font-weight: bold; color: #333; margin-bottom: 10px; }
        .choices { margin-top: 15px; font-size: 1em; margin-left: 15px; }
        .choices div { margin-bottom: 8px; padding-left: 15px; text-indent: -15px; cursor: pointer; }
        .choices div:hover { background-color: #f8f9fa; }
        .write-box { margin-top: 15px; height: 120px; border: 1px solid #ccc; border-radius: 4px; background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); line-height: 30px; }
        .summary-blank { border: 1px dashed #aaa; padding: 15px; margin: 15px 0 25px 0; min-height: 100px; color: #666; font-size: 0.9em; background-color: #fcfcfc; font-weight: bold; display: flex; align-items: flex-start; }
        .blank { display: inline-block; min-width: 80px; border-bottom: 1.5px solid #000; margin: 0 5px; height: 1.2em; vertical-align: middle; }
        .answer-sheet { background: #f8f9fa; padding: 40px; margin-top: 60px; border-top: 4px double #333; page-break-before: always; }
        .ans-main-title { font-size: 1.6em; font-weight: bold; text-align: center; margin-bottom: 40px; padding-bottom: 15px; border-bottom: 3px double #999; color: #333; }
        .ans-item { margin-bottom: 50px; border-bottom: 1px dashed #ccc; padding-bottom: 30px; }
        .ans-type-badge { display: inline-block; background-color: #555; color: #fff; padding: 4px 12px; border-radius: 15px; font-size: 0.85em; font-weight: bold; margin-bottom: 12px; }
        .ans-num { font-weight: bold; color: #d63384; font-size: 1.3em; display: block; margin-bottom: 15px; }
        .ans-content-title { font-weight: bold; color: #2c3e50; margin-top: 20px; margin-bottom: 8px; font-size: 1.05em; display: block; border-left: 4px solid #2c3e50; padding-left: 10px; }
        .ans-text { display: block; margin-left: 5px; color: #333; line-height: 1.8; }
        .ans-wrong-box { background-color: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 8px; margin-top: 10px; color: #555; }
        .summary-ans-box { background-color: #e3f2fd; padding: 25px; margin-bottom: 50px; border-radius: 10px; border: 1px solid #90caf9; }
        @media print { body { padding: 0; } }
    </style>
</head>
<body>
"""
HTML_TAIL = "</body></html>"

# ==========================================
# [헬퍼 함수] 맞춤형 헤더 및 모델 생성 로직
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
            if status_placeholder: status_placeholder.info(f"⚡ 생성 중... ({model_name})")
            if model_name.startswith("gpt"):
                if not openai_client: continue
                response = openai_client.chat.completions.create(
                    model=model_name, 
                    messages=[{"role": "system", "content": "당신은 대한민국 수능 국어 출제 위원장입니다."}, {"role": "user", "content": prompt}],
                    max_completion_tokens=8192 if not generation_config else generation_config.max_output_tokens,
                    temperature=0.7 if not generation_config else generation_config.temperature
                )
                class Wrapper:
                    def __init__(self, t): self.text = t
                return Wrapper(response.choices[0].message.content)
            else:
                model = genai.GenerativeModel(model_name)
                return model.generate_content(prompt, generation_config=generation_config)
        except Exception as e:
            last_exception = e; continue 
    if last_exception: raise last_exception
    else: raise Exception("모델 응답 실패")

def create_docx(html_content, file_name, main_title, topic_title):
    document = Document()
    document.add_heading(main_title, 0).alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_time = document.add_paragraph("소요 시간: ___________"); p_time.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_topic = document.add_paragraph(f"주제: {topic_title}"); p_topic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph("-" * 50)
    clean_text = re.sub(r'<[^>]+>', '\n', html_content)
    document.add_paragraph(re.sub(r'\n+', '\n', clean_text).strip())
    fs = BytesIO(); document.save(fs); fs.seek(0)
    return fs

# ==========================================
# 🧩 1. 비문학 문제 제작 함수 (원본 로직 보존)
# ==========================================
def non_fiction_app():
    global GOOGLE_API_KEY
    current_d_mode = st.session_state.get('domain_mode_select', 'AI 생성')
    with st.sidebar:
        st.header("🏫 문서 타이틀 설정")
        custom_main_title = st.text_input("메인 타이틀 (학원명)", value="사계국어 모의고사", key="nf_title")
        st.header("🛠️ 지문 입력 방식")
        st.selectbox("방식 선택", ["AI 생성", "직접 입력"], key="domain_mode_select")
        st.header("1️⃣ 지문 및 주제 설정")
        if current_d_mode == 'AI 생성':
            mode = st.radio("구성", ["단일 지문", "주제 통합"], key="ai_mode")
            domain = st.selectbox("영역", ["인문", "사회", "과학", "기술", "예술"], key="domain_select")
            topic = st.text_input("주제", placeholder="예: 금리 인하", key="topic_input")
            difficulty = st.select_slider("난이도", ["중", "상", "최상"], value="최상")
        else:
            mode = st.radio("지문 구성", ["단일 지문", "주제 통합"], key="manual_mode")
            topic = "사용자 지문"; domain = "사용자 입력"; difficulty = "사용자 지정"
        st.header("2️⃣ 문제 유형 및 개수 선택")
        label_t1 = "1. 핵심 주장 요약 (서술형)" if (not current_d_mode == 'AI 생성' or mode == "단일 지문") else "1. (가),(나) 요약 및 연관성 서술"
        s1 = st.checkbox(label_t1, value=True); s2 = st.checkbox("2. 내용 일치 O/X")
        c2 = st.number_input(" - OX 수", 1, 10, 2) if s2 else 0
        s3 = st.checkbox("3. 빈칸 채우기"); c3 = st.number_input(" - 빈칸 수", 1, 10, 2) if s3 else 0
        s4 = st.checkbox("4. 변형 문장 정오판단"); c4 = st.number_input(" - 판단 수", 1, 10, 2) if s4 else 0
        s5 = st.checkbox("5. 객관식 (일치)", value=True); c5 = st.number_input(" - 객관식 수", 1, 10, 2) if s5 else 0
        s6 = st.checkbox("6. 객관식 (추론)", value=True); c6 = st.number_input(" - 추론 수", 1, 10, 2) if s6 else 0
        s7 = st.checkbox("7. 객관식 (보기 3점)", value=True); c7 = st.number_input(" - 보기 수", 1, 10, 1) if s7 else 0
        use_summary = st.checkbox("📌 문단 요약 칸 생성", value=True)

    if st.session_state.generation_requested:
        manual_p = ""
        if current_d_mode == '직접 입력':
            if mode == '단일 지문': manual_p = st.session_state.get("manual_passage_input_col_main", "")
            else: manual_p = f"[가]\n{st.session_state.get('manual_passage_input_a','')}\n\n[나]\n{st.session_state.get('manual_passage_input_b','')}"
        
        status = st.empty()
        try:
            reqs = []
            if s1: reqs.append(f'<div class="question-box"><span class="question-text">1. {label_t1}</span><div class="write-box"></div></div>')
            if s2: reqs.append(f'<h3>내용 일치 O/X ({c2}문항)</h3>- ( O / X ) 포함.')
            if s3: reqs.append(f"<h3>빈칸 채우기 ({c3}문항)</h3>- `<span class='blank'>&nbsp;&nbsp;&nbsp;&nbsp;</span>` 사용.")
            if s4: reqs.append(f'<h3>변형 문장 정오판단 ({c4}문항)</h3>')
            mcq = '<div class="question-box"><span class="question-text">[번호] [발문]</span><div class="choices"><div>①...</div><div>②...</div><div>③...</div><div>④...</div><div>⑤...</div></div></div>'
            if s5: reqs.append(f'<h3>객관식: 세부 내용 ({c5}문항)</h3>{mcq}')
            if s6: reqs.append(f'<h3>객관식: 추론 및 비판 ({c6}문항)</h3>{mcq}')
            if s7: reqs.append(f'<h3>객관식: [보기] 적용 ({c7}문항) [3점]</h3><div class="example-box">(보기)</div>{mcq}')
            
            reqs_str = "\n".join(reqs)
            sum_inst = """- **[필수]**: 문단 끝에 `<div class='summary-blank'>📝 문단 요약 연습: (요약해보세요)</div>` 삽입.""" if use_summary else ""
            
            p1_prompt = f"""
            당신은 수능 국어 위원장입니다. HTML 문제지를 생성하시오. h1, h2 태그 금지.
            {f"지문 작성 - 주제: {topic}, 난이도: {difficulty} {sum_inst}" if current_d_mode == 'AI 생성' else ""}
            {f"[사용자 지문]\n{manual_p}" if current_d_mode == '직접 입력' else ""}
            🚨 [고난도 가이드] 1.정보 재구성(1:1 매칭 금지) 2.Paraphrasing 3.인과관계 비틀기 4.전체 균형
            [요청]:\n{reqs_str}
            """
            res_q = generate_content_with_fallback(p1_prompt, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            html_q = re.sub(r'<h[12].*?>.*?</h[12]>', '', html_q, flags=re.DOTALL | re.IGNORECASE)

            # [복구] 해설 분할 생성 (Batch Size 6)
            total_q_cnt = sum([1 if s1 else 0, c2, c3, c4, c5, c6, c7])
            BATCH_SIZE = 6
            ans_parts = []; sum_done = False
            for i in range(0, total_q_cnt, BATCH_SIZE):
                start_n, end_n = i + 1, min(i + BATCH_SIZE, total_q_cnt)
                status.info(f"📝 해설 생성 중... ({start_n}~{end_n}/{total_q_cnt})")
                curr_sum = """- **[필수]**: 답변 맨 위에 `<div class="summary-ans-box">`를 열고 문단별 요약 예시 작성.""" if use_summary and not sum_done else ""
                sum_done = True
                p_chunk = f"""수능 해설 위원으로서 {start_n}~{end_n}번 해설만 HTML로 작성.\n{curr_sum}\n문제 내용: {html_q}"""
                res_c = generate_content_with_fallback(p_chunk, status_placeholder=status)
                text_c = res_c.text.replace("```html","").replace("```","").strip()
                if i == 0: text_c = '<div class="answer-sheet"><h2 class="ans-main-title">정답 및 해설</h2>' + text_c
                ans_parts.append(text_c)

            html_a = "".join(ans_parts) + "</div>"
            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, topic)
            if current_d_mode == '직접 입력':
                def m_p(t): return f"<p>{t}</p>" + ("<div class='summary-blank'>📝 문단 요약 연습</div>" if use_summary else "")
                full_html += f'<div class="passage">{"".join([m_p(p) for p in re.split(r"\\n\s*\\n", manual_p) if p.strip()])}</div>'
            full_html += html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": topic}
            status.success("✅ 비문학 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 📖 2. 문학(소설) 문제 제작 함수 (원본 보존)
# ==========================================
def fiction_app():
    with st.sidebar:
        st.header("🏫 타이틀"); custom_main_title = st.text_input("메인 타이틀", value="사계국어 모의고사", key="fi_t")
        st.header("1️⃣ 작품 정보"); w_n = st.text_input("작품명", key="fi_n"); a_n = st.text_input("작가명", key="fi_a")
        st.header("2️⃣ 유형"); u_v = st.checkbox("어휘"); c_v = st.number_input("수", 1, 20, 5) if u_v else 0
        u_e = st.checkbox("서술형"); c_e = st.number_input("수", 1, 10, 3) if u_e else 0
        u_m = st.checkbox("객관식"); c_m = st.number_input("수", 1, 10, 3) if u_m else 0
        u_b = st.checkbox("보기객관식"); c_b = st.number_input("수", 1, 10, 2) if u_b else 0
        st.caption("3️⃣ 분석 활동"); u5 = st.checkbox("인물정리"); u6 = st.checkbox("상황요약"); u7 = st.checkbox("관계도"); u8 = st.checkbox("갈등정리")

    if st.session_state.generation_requested:
        text = st.session_state.fiction_novel_text_input_area
        if not text: st.warning("본문 입력 필수"); st.session_state.generation_requested = False; return
        status = st.empty()
        try:
            reqs = [f"어휘 {c_v}개", f"서술형 {c_e}개", f"객관식 {c_m}개", f"보기적용 {c_b}개", "인물표" if u5 else "", "상황요약" if u6 else "", "관계도" if u7 else "", "갈등정리" if u8 else ""]
            r_str = "\n".join([r for r in reqs if r])
            p_q = f"수능 위원으로서 소설 '{w_n}' 기반 HTML 문제지 작성(h1,h2 금지).\n본문:\n{text}\n요청:\n{r_str}"
            res_q = generate_content_with_fallback(p_q, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            res_a = generate_content_with_fallback(f"위 문제 정답/해설을 <div class='answer-sheet'>에 작성.\n{html_q}", status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()
            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, w_n)
            full_html += f'<div class="passage">{text.replace(chr(10), "<br>")}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": w_n}
            status.success("✅ 문학 완료!"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🌸 3. 현대시 문제 제작 함수 (문항수 조절)
# ==========================================
def poetry_app():
    with st.sidebar:
        st.header("🏫 타이틀"); custom_main_title = st.text_input("메인 타이틀", value="사계국어 모의고사", key="po_t")
        st.header("1️⃣ 작품 정보"); po_n = st.text_input("작품명", key="po_n"); po_a = st.text_input("작가명", key="po_a")
        st.header("2️⃣ 문항 조절 (1~5개)")
        c1 = st.checkbox("개요 문제", value=True); n1 = st.number_input("수", 1, 5, 1, key="pn1") if c1 else 0
        c2 = st.checkbox("시상 전개", value=True); n2 = st.number_input("수", 1, 5, 1, key="pn2") if c2 else 0
        c3 = st.checkbox("시어 의미", value=True); n3 = st.number_input("수", 1, 5, 2, key="pn3") if c3 else 0
        c4 = st.checkbox("표현 특징", value=True); n4 = st.number_input("수", 1, 5, 2, key="pn4") if c4 else 0
        c5 = st.checkbox("종합 감상", value=True); n5 = st.number_input("수", 1, 5, 1, key="pn5") if c5 else 0
        c6 = st.checkbox("킬러 포인트", value=True); n6 = st.number_input("수", 1, 5, 1, key="pn6") if c6 else 0
        c7 = st.checkbox("연계 비교", value=True); n7 = st.number_input("수", 1, 5, 1, key="pn7") if c7 else 0
        st.header("3️⃣ 추가")
        c8 = st.checkbox("OX 세트"); n8 = st.number_input("수", 1, 15, 10, key="pn8") if c8 else 0
        c9 = st.checkbox("서술형"); n9 = st.number_input("수", 1, 10, 3, key="pn9") if c9 else 0

    if st.session_state.generation_requested:
        po_text = st.session_state.get("poetry_text_input_area", "")
        if not po_text: st.warning("시 입력 필수"); st.session_state.generation_requested = False; return
        status = st.empty()
        try:
            reqs = [f"개요 {n1}개", f"전개 {n2}개", f"의미 {n3}개", f"특징 {n4}개", f"감상 {n5}개", f"킬러 {n6}개", f"연계 {n7}개", f"OX {n8}개(정답금지)", f"서술 {n9}개"]
            # [수정] f-string 내 백슬래시 방지 위해 변수로 미리 조인
            r_str = "\n".join([r for r in reqs if not r.endswith("0개")])
            p_q = f"수능 위원장으로서 현대시 '{po_n}' 기반 HTML 문제지 작성.\n본문: {po_text}\n요청:\n{r_str}"
            res_q = generate_content_with_fallback(p_q, status_placeholder=status)
            html_q = res_q.text.replace("```html","").replace("```","").strip()
            p_a = f"위 문항 정답/해설을 <div class='answer-sheet'>에 작성.\n내용: {html_q}"
            res_a = generate_content_with_fallback(p_a, status_placeholder=status)
            html_a = res_a.text.replace("```html","").replace("```","").strip()
            full_html = HTML_HEAD + get_custom_header_html(custom_main_title, po_n)
            full_html += f'<div class="poetry-passage">{po_text}</div>' + html_q + html_a + HTML_TAIL
            st.session_state.generated_result = {"full_html": full_html, "main_title": custom_main_title, "topic_title": po_n}
            status.success("✅ 현대시 생성 완료"); st.session_state.generation_requested = False
        except Exception as e: status.error(f"오류: {e}"); st.session_state.generation_requested = False

# ==========================================
# 🚀 메인 실행
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
        if st.button("🚀 생성", key="r1"): st.session_state.generation_requested = True
        non_fiction_app()
    elif st.session_state.app_mode == "🌸 현대시 문제 제작":
        st.header("🌸 현대시 문항 제작")
        st.text_area("시 입력", height=400, key="poetry_text_input_area")
        if st.button("🚀 생성", key="r2"): st.session_state.generation_requested = True
        poetry_app()
    else:
        st.header("📖 문학 심층 분석")
        st.text_area("작품 본문 입력", height=300, key="fiction_novel_text_input_area")
        if st.button("🚀 생성", key="r3"): st.session_state.generation_requested = True
        fiction_app()
display_results()
