import streamlit as st
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import re 
import os
from docx import Document
from io import BytesIO
from docx.shared import Inches
from docx.shared import Pt
# from google.generativeai.types import Part # **[오류 발생 원인 제거]**


# ==========================================
# [설정] API 키 연동 (Streamlit Cloud Secrets 권장)
# ==========================================
# Streamlit Cloud 배포 시 st.secrets에서 키를 가져옵니다.
try:
    # 1. Streamlit Secrets에 GOOGLE_API_KEY = "발급받은 실제 API 키" 설정
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"] 
except (KeyError, AttributeError):
    # Secrets 설정이 안 되어 있을 경우 (로컬 테스트용)
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
            line-height: 1.6; 
            color: #000; 
            font-size: 10.5pt;
        }
        
        h1 { text-align: center; margin-bottom: 5px; font-size: 28px; letter-spacing: -1px; }
        h2 { text-align: center; margin-top: 0; margin-bottom: 30px; font-size: 16px; color: #333; }
        
        /* [비문학] 시간 박스 */
        .time-box {
            text-align: center; border: 1px solid #333; border-radius: 30px;
            padding: 10px 20px; margin: 0 auto 40px auto; width: fit-content;
            font-weight: bold; background-color: #fdfdfd; font-size: 0.95em;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        .time-blank {
            display: inline-block;
            width: 60px;
            border-bottom: 1px solid #000;
            margin: 0 5px;
            height: 1em;
            vertical-align: middle;
        }
        
        /* [비문학] 유형 구분 헤딩 (h3) */
        h3 { 
            margin-top: 5px; 
            margin-bottom: 15px; 
            font-size: 1.6em; 
            color: #2e8b57; 
            border-bottom: 2px solid #2e8b57;
            padding-bottom: 10px;
            font-weight: bold;
        }
        
        /* [문학] 유형 구분 헤딩 (h4) */
        h4 {
            margin-top: 5px; 
            margin-bottom: 10px; 
            font-size: 1.8em; 
            color: #00008b; 
            border-bottom: 3px solid #00008b; 
            padding-bottom: 8px; 
            font-weight: bold; 
        }

        /* [비문학/문학 통합] 유형 콘텐츠 전체를 감싸는 박스 */
        .type-box { 
            border: 2px solid #999; 
            padding: 20px; 
            margin-bottom: 20px; 
            border-radius: 10px; 
            page-break-inside: avoid; 
        }

        /* 지문 스타일 */
        .passage { 
            font-size: 10pt; 
            border: 1px solid #000; 
            padding: 25px; 
            margin-bottom: 30px; 
            background-color: #fff; 
            line-height: 1.8; 
            text-align: justify;
        }
        .passage p { 
            text-indent: 1em; 
            margin-bottom: 10px; 
            display: block;
        }
        
        /* (가), (나) 지문 표시 */
        .passage-label {
            font-weight: bold; font-size: 1.1em; color: #fff;
            display: inline-block; background-color: #000;
            padding: 2px 8px; border-radius: 4px; margin-right: 5px; margin-bottom: 10px;
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }
        
        /* 문단 요약 칸 */
        .summary-blank { 
            display: block; margin-top: 10px; margin-bottom: 20px; padding: 0 10px; 
            height: 100px; border: 1px solid #777; border-radius: 5px;
            color: #555; font-size: 0.9em; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; 
            font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        /* 문학 작품명/작가명 표시용 */
        .source-info { 
            text-align: right; font-size: 0.85em; color: #666; margin-bottom: 30px; 
            font-style: italic; font-family: 'HanyangShinMyeongjo', 'Batang', serif;
        }

        /* 문제/질문 스타일 */
        .question-box { 
            margin-bottom: 25px; 
            page-break-inside: avoid; 
        }

        /* 문제 발문 강조 스타일 */
        .question-box b, .question-box strong {
            font-weight: 900; 
            display: inline-block;
            margin-bottom: 5px;
        }
        
        /* 보기 박스 */
        .example-box { 
            border: 1px solid #333; padding: 15px; margin: 10px 0; 
            background-color: #f7f7f7; 
            font-size: 0.95em; font-weight: normal;
        }

        /* 객관식 선지 목록 스타일 */
        .choices { 
            padding-left: 20px;
            text-indent: -20px; 
            margin-left: 20px;
            padding-top: 10px;
            line-height: 1.4;
        }
        .choices div { 
            margin-bottom: 5px; 
        }
        
        /* 서술 공간 */
        .write-box { 
            margin-top: 15px; margin-bottom: 10px; height: 150px; 
            border: 1px solid #777; 
            background: repeating-linear-gradient(transparent, transparent 29px, #eee 30px); 
            line-height: 30px; border-radius: 5px; 
        }

        /* 문학 전용 긴 밑줄 */
        .long-blank-line {
            display: block; 
            border-bottom: 1px solid #000; 
            margin: 5px 0 15px 0; 
            min-height: 1.5em; 
            width: 95%; 
        }
        .answer-line-gap { /* 문학 서술형 답안용 큰 공백 밑줄 */
            display: block;
            border-bottom: 1px solid #000;
            margin: 25px 0 25px 0;
            min-height: 1.5em;
            width: 95%;
        }

        /* 빈칸 밑줄 */
        .blank {
            display: inline-block;
            min-width: 60px;
            border-bottom: 1px solid #000;
            margin: 0 2px;
            vertical-align: bottom;
            height: 1.2em;
        }
        
        /* 테이블 스타일 (문학: 유형 4) */
        .analysis-table { 
            width: 100%; border-collapse: collapse; margin-top: 10px; 
            font-size: 0.95em; line-height: 1.4;
        }
        .analysis-table th, .analysis-table td { 
            border: 1px solid #000; padding: 8px; text-align: left;
        }
        .analysis-table th { 
            background-color: #e6e6fa; 
            text-align: center; font-weight: bold;
        }
        .analysis-table .blank-row { height: 35px; }

        /* 정답/해설 */
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

# 모델 자동 선택 함수 
def get_best_model():
    """API 환경에서 유효한 최신 Gemini 모델 ID를 찾아서 반환합니다."""
    if "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY or "APIKEY" in GOOGLE_API_KEY:
          return 'gemini-2.5-flash'
        
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        models = [m.name for m in genai.list_models()]
        
        if 'gemini-2.5-flash' in models: return 'gemini-2.5-flash'
        elif 'gemini-2.5-pro' in models: return 'gemini-2.5-pro'
        elif 'gemini-1.5-flash' in models: return 'gemini-1.5-flash'
        elif 'gemini-pro' in models: return 'gemini-pro'
        else: return 'gemini-2.5-flash'
    except Exception: 
        return 'gemini-2.5-flash'


# ==========================================
# [DOCX 생성 및 다운로드 함수]
# ==========================================

# DOCX 테이블에 테두리를 설정하는 헬퍼 함수
def set_table_borders(table):
    """테이블 및 셀에 기본 테두리 스타일을 설정합니다."""
    try:
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                
                # 기본 테두리 설정 (단색, 1/4 pt)
                for border_name in ('top', 'left', 'bottom', 'right'):
                    borders = OxmlElement(qn('w:tcBorders'))
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'single')
                    border.set(qn('w:sz'), '4') # 두께 1/4 pt
                    border.set(qn('w:color'), 'auto')
                    
                    borders.append(border)
                    tcPr.append(borders)
    except Exception:
        # docx.oxml 관련 import가 실패해도 실행되도록 처리
        pass


def create_docx(html_content, file_name, current_topic, is_fiction=False):
    """HTML 내용을 기반으로 DOCX 문서를 생성하고 BytesIO 객체를 반환"""
    document = Document()
    
    # ------------------ [DOCX 파싱 로직] --------------------
    
    # 0. HTML <head> 및 <body> 태그 이전/이후의 불필요한 부분을 제거
    clean_html_body = re.sub(r'.*?<body[^>]*>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    clean_html_body = re.sub(r'<\/body>.*?<\/html>', '', clean_html_body, flags=re.DOTALL | re.IGNORECASE)
    
    
    # 1. <h1> 사계국어 비문학 스펙트럼 </h1> 추출
    h1_match = re.search(r'<h1>(.*?)<\/h1>', clean_html_body, re.DOTALL)
    if h1_match:
        h1_text = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
        document.add_heading(h1_text, level=0)
    
    # 2. <h2> [영역: 주제] </h2> 추출
    h2_match = re.search(r'<h2>(.*?)<\/h2>', clean_html_body, re.DOTALL)
    if h2_match:
        h2_text = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()
        document.add_heading(h2_text, level=2) # 2레벨 제목
        
    # 3. 시간 박스 추출 및 추가
    time_box_match = re.search(r'<div class="time-box">(.*?)<\/div>', clean_html_body, re.DOTALL)
    if time_box_match:
        time_text = re.sub(r'<[^>]+>', '', time_box_match.group(1)).strip()
        document.add_paragraph(f"--- {time_text} ---") # 텍스트 형태로 간략하게 추가
    
    
    # 4. 지문 영역 추출 및 처리
    passage_match = re.search(r'<div class="passage">(.*?)<\/div>', clean_html_body, re.DOTALL)
    
    # 지문 영역 끝 인덱스를 미리 계산
    passage_end_index = passage_match.end() if passage_match else -1
    
    # --- DOCX 박스 구현 시작 ---
    if passage_match:
        document.add_heading("I. 지문", level=1)
        
        # 지문 전체를 담을 테이블 생성 (테두리 효과)
        table = document.add_table(rows=1, cols=1)
        table.width = Inches(6.5) # 문서 너비에 맞게 설정
        set_table_borders(table)  # 테두리 설정 적용
        cell = table.cell(0, 0)
        
        passage_html = passage_match.group(1).strip()
        
        # 4-1. 지문 내용과 문단 요약 필드를 분리하여 셀에 추가
        parts = re.split(r'(<div class="summary-blank">.*?<\/div>|<div class="source-info">.*?<\/div>)', passage_html, flags=re.DOTALL)
        
        for part in parts:
            if not part.strip():
                continue

            if part.startswith('<div class="summary-blank">'):
                # 문단 요약 테이블 추가 (박스 효과)
                summary_table = document.add_table(rows=1, cols=1)
                summary_table.width = Inches(6.5)
                set_table_borders(summary_table) # 문단 요약 박스 테두리
                sum_cell = summary_table.cell(0, 0)
                p = sum_cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                p.add_run("📝 문단 요약 :").bold = True
                sum_cell.add_paragraph(' \n \n') # 빈 줄 추가 (칸 확보)
            
            elif part.startswith('<div class="source-info">'):
                # 출처 정보 추가
                source_text = re.sub(r'<[^>]+>', '', part).strip()
                cell.add_paragraph(f"\n{source_text}", style='Caption') 
                
            else:
                # 일반 지문 문단 처리
                paragraphs = re.split(r'<\/p>', part)
                for p_html in paragraphs:
                    # (가), (나) 라벨 처리
                    label_match = re.search(r'<span class="passage-label">(.*?)<\/span>', p_html)
                    if label_match:
                           label = label_match.group(1).strip()
                           cell.paragraphs[0].add_run(f"[{label}]\n").bold = True
                           p_html = re.sub(r'<span class="passage-label">.*?<\/span><br>', '', p_html)

                    p_text = re.sub(r'<[^>]+>', '', p_html).strip()
                    if p_text:
                        p = cell.add_paragraph(p_text)
                        p.paragraph_format.first_line_indent = Inches(0.25)
                        
    # 5. 문제 및 해설 영역 처리 (나머지 내용)
    
    # 해설 영역(answer-sheet) 추출
    answer_sheet_match = re.search(r'<div class="answer-sheet">(.*?)<\/div>', clean_html_body, re.DOTALL)
    
    # 문제 블록 끝 지점
    problem_block_end = answer_sheet_match.start() if answer_sheet_match else len(clean_html_body) # 해설이 없으면 문서 끝까지

    # 지문 영역 끝나는 지점 이후의 콘텐츠 (문제 시작점)
    problem_block_start = 0
    if passage_match:
         # 지문 컨테이너 </div> 태그의 끝 지점을 찾음
         passage_div_end = clean_html_body.find('</div>', passage_match.end())
         if passage_div_end != -1 and passage_div_end < problem_block_end:
              problem_block_start = passage_div_end + len('</div>')
         # 만약 지문 닫는 태그를 못 찾으면, 지문 매치 끝 인덱스 사용
         elif passage_match:
              problem_block_start = passage_match.end()
    elif time_box_match: # 지문이 아예 없는 경우 시간 박스 다음부터 시작
         problem_block_start = time_box_match.end()

    
    problem_block = clean_html_body[problem_block_start:problem_block_end].strip()
    
    
    if problem_block:
        document.add_heading("II. 문제", level=1)
        
        # **[수정] 추천 문제의 정답 노출 방지**
        problem_block = re.sub(r'<p style=\'display: none;\'>정답:.*?<\/p>', '', problem_block, flags=re.DOTALL)
        
        # 문제 블록을 문제 유형별로 나누기 (<h3> 또는 #### 태그 기준으로)
        question_parts = re.split(r'(<h3>.*?<\/h3>|<h4>.*?<\/h4>)', problem_block, flags=re.DOTALL)
        
        for part in question_parts:
            if not part.strip():
                continue
            
            # 유형 제목 (h3/h4) 처리
            if re.match(r'<h[34]>', part):
                level = int(re.match(r'<h([34])>', part).group(1))
                title = re.sub(r'<[^>]+>', '', part).strip()
                document.add_heading(title, level=level - 1)
            
            # 실제 문제 내용 처리
            else:
                
                # --- 문제 박스 테이블 생성 ---
                question_table = document.add_table(rows=1, cols=1)
                question_table.width = Inches(6.5)
                set_table_borders(question_table) # 문제 박스 테두리
                q_cell = question_table.cell(0, 0)
                
                # <보기> (example-box) 내용 추출 및 별도 단락으로 처리
                example_box_match = re.search(r'<div class="example-box">(.*?)<\/div>', part, flags=re.DOTALL)
                if example_box_match:
                    example_text = re.sub(r'<[^>]+>', '', example_box_match.group(1)).strip()
                    
                    p = q_cell.add_paragraph()
                    p.add_run("<보기>\n").bold = True
                    p.add_run(example_text).font.size = Pt(10)
                    
                    # 보기 박스 영역을 텍스트에서 제거
                    part = re.sub(r'<div class="example-box">.*?<\/div>', '', part, flags=re.DOTALL)
                
                
                # 나머지 텍스트 (발문, 선지, 서술 공간) 처리
                text = re.sub(r'<div class="write-box">.*?<\/div>', '\n\n(답안 공간)\n\n', part, flags=re.DOTALL)
                text = re.sub(r'<\/?b>|<strong>|<\/?div class="question-box">|<\/?div class="choices">', '', text)
                text = re.sub(r'<[^>]+>', '', text) # 나머지 태그 제거
                text = re.sub(r'<br\s*\/?>', '\n', text)
                
                # 문제 번호별로 문단 추가
                lines = text.split('\n')
                for line in lines:
                    if line.strip():
                        q_cell.add_paragraph(line.strip())

    
    # 해설 부분
    if answer_sheet_match:
        # 해설 섹션 시작점부터 문서 끝까지 추출하여 해설 누락 방지
        answer_html = clean_html_body[answer_sheet_match.start():]
        answer_html = re.sub(r'<div class="answer-sheet">', '', answer_html, flags=re.DOTALL) # 시작 태그 제거
        
        document.add_heading("III. 정답 및 해설", level=1)
        
        answer_text = re.sub(r'<br\s*\/?>', '\n', answer_html)
        answer_text = re.sub(r'<[^>]+>', '', answer_text).strip()
        
        answer_lines = answer_text.split('\n')
        for line in answer_lines:
            if line.strip():
                document.add_paragraph(line.strip())

    # DOCX 파일을 메모리에 저장
    file_stream = BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    return file_stream

# --------------------------------------------------------------------------
# [Session State 및 콜백 함수]
# --------------------------------------------------------------------------
# 공통 세션 상태 초기화
if 'generation_requested' not in st.session_state:
    st.session_state.generation_requested = False
if 'd_mode' not in st.session_state:
    st.session_state.d_mode = 'AI 생성'
if 'manual_passage_input' not in st.session_state:
    st.session_state.manual_passage_input = ""
if 'manual_passage_input_a' not in st.session_state: 
    st.session_state.manual_passage_input_a = ""
if 'manual_passage_input_b' not in st.session_state: 
    st.session_state.manual_passage_input_b = ""
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "⚡ 비문학 문제 제작" 
    
# **[수정 추가] 생성된 결과 데이터를 저장할 Session State 초기화**
if 'generated_result' not in st.session_state:
    st.session_state.generated_result = None

# st.radio 오류 방지를 위한 안전한 초기값 설정
if st.session_state.app_mode not in ["⚡ 비문학 문제 제작", "📖 문학 문제 제작"]:
     st.session_state['app_mode'] = "⚡ 비문학 문제 제작" 


def request_generation():
    # 모든 요청 시, 세션 상태를 True로 설정
    st.session_state.generation_requested = True
    # 새로운 생성을 요청할 때는 이전 결과 데이터를 지웁니다.
    st.session_state.generated_result = None 


def clear_generation_status():
     # 재실행 후 request 상태를 False로 바꾸어 무한 루프를 막고, 결과를 유지합니다.
     st.session_state.generation_requested = False


# 비문학 전용 콜백
def non_fiction_update_mode():
    st.session_state.d_mode = st.session_state.domain_mode_select
    # 모드 변경 시, 기존 AI 생성 입력 필드를 초기화 (필요하다면)
    if st.session_state.d_mode == '직접 입력':
        if 'topic_input' in st.session_state: st.session_state.topic_input = ""
        if 'topic_a_input' in st.session_state: st.session_state.topic_a_input = ""
        if 'topic_b_input' in st.session_state: st.session_state.topic_b_input = ""
    else:
        st.session_state.manual_passage_input = ""

# Streamlit UI 스타일 설정
st.markdown("""
<style>
    /* 기본 버튼 스타일 통일 */
    .stButton>button { width: 100%; background-color: #2e8b57; color: white; height: 3em; font-size: 20px; border-radius: 10px; }
    .stNumberInput input { text-align: center; }
    
    /* 앱 모드 선택 라디오 버튼 컨테이너 스타일 (초록색 박스 제거) */
    div[role="radiogroup"] {
        padding: 0px; 
        justify-content: center;   
        margin-bottom: 30px;
    }
    
    /* 앱 모드 선택 라디오 버튼 개별 라벨 스타일 (크기 확대 및 강조) */
    div[role="radiogroup"] > label {
        padding: 15px 30px; 
        border: 2px solid #ccc; 
        border-radius: 12px;
        margin: 10px; 
        font-size: 22px !important; 
        font-weight: 800;          
        transition: background-color 0.3s, border-color 0.3s;
        min-width: 250px; 
        text-align: center; 
        cursor: pointer;
    }

    /* 선택된 라디오 버튼 배경색 변경 및 테두리 두께 강조 */
    div[role="radiogroup"] > label[data-baseweb="radio"] input[type="radio"]:checked + div {
        background-color: #e0f7e9; 
        border-color: #2e8b57;     
        border-width: 3px; 
    }
    
    /* 앱 모드 선택 상단 제목 스타일 */
    label[data-testid="stWidgetLabel"] {
        font-size: 24px;          
        font-weight: 800;          
        color: #00008b;          
        text-align: center;
        width: 100%;
        display: block;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 🧩 비문학 문제 제작 함수
# ==========================================

def non_fiction_app():
    
    # **[수정] NameError 방지를 위해 global 명시**
    global GOOGLE_API_KEY
    
    # --------------------------------------------------------------------------
    # [설정값 정의]
    # --------------------------------------------------------------------------
    current_d_mode = st.session_state.get('domain_mode_select', st.session_state.d_mode)
    
    # Sidebar UI 렌더링
    with st.sidebar:
        st.header("🛠️ 지문 입력 방식 선택")
        st.selectbox("지문 입력 방식", ["AI 생성", "직접 입력"], key="domain_mode_select", on_change=non_fiction_update_mode)
        st.markdown("---")

        st.header("1️⃣ 지문 구성 및 주제 설정")
        
        # AI 생성 모드
        if current_d_mode == 'AI 생성':
            mode = st.radio("지문 구성 방식", ["단일 지문 (기본)", "주제 통합 (가) + (나)"], index=0, key="ai_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술"]
            
            if st.session_state.ai_mode == "단일 지문 (기본)":
                domain = st.selectbox("문제 영역", domains, key="domain_select")
                topic = st.text_input("주제 입력", placeholder="예: 금리 인하 효과", key="topic_input")
            else:
                st.markdown("#### 🅰️ (가) 글 설정")
                domain_a = st.selectbox("[(가) 영역]", domains, key="dom_a")
                topic_a = st.text_input("[(가) 주제]", placeholder="예: 칸트의 미학", key="topic_a_input")
                
                st.markdown("#### 🅱️ (나) 글 설정")
                domain_b = st.selectbox("[(나) 영역]", domains, key="dom_b", index=7)
                topic_b = st.text_input("[(나) 주제]", placeholder="예: 현대 미술의 추상성", key="topic_b_input")
                
                domain = f"{domain_a} + {domain_b}"
                topic = f"(가) {topic_a} / (나) {topic_b}"
            
            difficulty = st.select_slider("난이도", ["하", "중", "상", "최상(LEET급)"], value="최상(LEET급)", key="difficulty_select")
            current_topic = topic
            current_mode = st.session_state.ai_mode
            current_domain = domain

        # 직접 입력 모드 
        else: 
            mode = st.radio("지문 구성 방식", ["단일 지문", "주제 통합 (가) + (나)"], index=0, key="manual_mode")
            domains = ["인문", "철학", "경제", "법률", "사회", "과학", "기술", "예술", "사용자 지정"]
            
            if st.session_state.manual_mode == "단일 지문":
                # 단일 지문일 경우
                domain = st.selectbox("문제 영역", domains, key="manual_domain_select")
                
                # AI 생성 프롬프트에 넘길 때 사용할 더미 값 설정 (실제 사용은 안 됨)
                topic = "사용자 입력 지문"
                current_domain = domain
            
            else: # 주제 통합 (가) + (나)일 경우
                st.markdown("#### 🅰️ (가) 지문 영역")
                # 직접 입력 통합 지문의 (가) 영역 선택
                domain_a = st.selectbox("[(가) 영역]", domains, key="manual_dom_a")
                
                st.markdown("#### 🅱️ (나) 지문 영역")
                # 직접 입력 통합 지문의 (나) 영역 선택
                domain_b = st.selectbox("[(나) 영역]", domains, key="manual_dom_b", index=7)
                
                # AI 생성 프롬프트에 넘길 때 사용할 통합 영역/주제 설정 (실제 사용은 안 됨)
                domain = f"({domain_a}) + ({domain_b})"
                topic = "사용자 입력 통합 지문"
                current_domain = domain
                
            difficulty = "사용자 지정"
            current_topic = topic
            current_mode = st.session_state.manual_mode

        st.markdown("---")
        
        st.header("2️⃣ 문제 유형 및 개수 선택")
        
        label_type1 = "1. 핵심 주장 요약 (서술형)" if current_mode == "단일 지문 (기본)" or current_mode == "단일 지문" else "1. (가),(나) 요약 및 연관성 서술"
        
        type1 = st.checkbox(label_type1, value=True, key="select_t1")
        type2 = st.checkbox("2. 내용 일치 O/X", key="select_t2")
        type2_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t2") if type2 else 0
        type3 = st.checkbox("3. 빈칸 채우기", key="select_t3")
        type3_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t3") if type3 else 0
        
        type4_original = st.checkbox("4. 변형 문장 정오판단", key="select_t4")
        type4_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t4") if type4_original else 0
        
        type5 = st.checkbox("5. 객관식 (일치/불일치)", key="select_t5")
        type5_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t5") if type5 else 0
        type6 = st.checkbox("6. 객관식 (추론)", key="select_t6")
        type6_cnt = st.number_input(" - 문항 수", 1, 10, 2, key="t6") if type6 else 0
        type7 = st.checkbox("7. 객관식 (보기 적용 3점)", key="select_t7")
        type7_cnt = st.number_input(" - 문항 수", 1, 10, 1, key="t7") if type7 else 0
        
        use_summary = st.checkbox("📌 지문 문단별 요약 훈련", value=False, key="select_summary")
        use_recommendation = st.checkbox(f"🌟 영역 맞춤 추천 문제 추가", value=False, key="select_recommendation")

    # 이 함수는 UI를 직접 출력하지 않고, 아래 메인 로직에서 처리합니다.

    # AI 생성 로직 (함수 내부에서는 변수만 준비)
    if st.session_state.generation_requested:
        
        # 입력 값들을 Session State에서 다시 가져옵니다
        current_d_mode = st.session_state.domain_mode_select
        current_mode = st.session_state.get("ai_mode", st.session_state.get("manual_mode", "단일 지문 (기본)"))
        
        # 직접 입력 모드일 때 지문 내용 결합
        if current_d_mode == '직접 입력':
            if current_mode == '단일 지문':
                current_manual_passage = st.session_state.get("manual_passage_input_col_main", "") # 메인 컬럼에서 입력된 값 사용
                # domain/topic은 사이드바에서 설정된 값 그대로 사용
                current_domain = st.session_state.get('manual_domain_select', '사용자 지정')
                current_topic = "사용자 입력 지문"
            else: # 주제 통합 (가) + (나)
                passage_a = st.session_state.get("manual_passage_input_a", "")
                passage_b = st.session_state.get("manual_passage_input_b", "")
                current_manual_passage = f"[가] 지문:\n{passage_a}\n\n[나] 지문:\n{passage_b}" 
                
                # 직접 입력 통합 지문 시 영역 설정값 사용
                dom_a = st.session_state.get('manual_dom_a', '사용자 지정')
                dom_b = st.session_state.get('manual_dom_b', '사용자 지정')
                current_domain = f"({dom_a}) + ({dom_b})"
                current_topic = "사용자 입력 통합 지문"
                
            
        else: # AI 생성 모드
            current_manual_passage = "" # AI 생성 모드일 때는 지문 생성을 모델에게 맡김
            
            # AI 생성 모드의 영역/주제 설정값 사용
            current_topic = st.session_state.get("topic_input", "주제 입력")
            if current_mode == "단일 지문 (기본)":
                 current_domain = st.session_state.get("domain_select", "사용자 지정")
            else:
                 dom_a = st.session_state.get('dom_a', '인문')
                 dom_b = st.session_state.get('dom_b', '철학')
                 current_domain = f"{dom_a} + {dom_b}"

        current_difficulty = st.session_state.get("difficulty_select", "사용자 지정")
            
        # 문제 개수 및 체크박스 상태 로드
        count_t2 = st.session_state.get("t2", 0)
        count_t3 = st.session_state.get("t3", 0)
        count_t4 = st.session_state.get("t4", 0)
        count_t5 = st.session_state.get("t5", 0)
        count_t6 = st.session_state.get("t6", 0)
        count_t7 = st.session_state.get("t7", 0)
        
        select_t1 = st.session_state.get("select_t1", False)
        select_t2 = st.session_state.get("select_t2", False)
        select_t3 = st.session_state.get("select_t3", False)
        select_t4 = st.session_state.get("select_t4", False)
        select_t5 = st.session_state.get("select_t5", False)
        select_t6 = st.session_state.get("select_t6", False)
        select_t7 = st.session_state.get("select_t7", False)
        use_summary = st.session_state.get("select_summary", False)
        use_recommendation = st.session_state.get("select_recommendation", False)
        
        
        # 2. 유효성 검사 (API 키, 필수 입력값)
        if current_d_mode == 'AI 생성' and current_mode == "단일 지문 (기본)" and not current_topic:
            st.warning("⚠️ AI 생성 모드에서는 주제를 입력해주세요!")
            clear_generation_status()
        elif current_d_mode == '직접 입력' and not current_manual_passage.strip():
            st.warning("⚠️ 직접 입력 모드에서는 지문을 입력해주세요!")
            clear_generation_status()
        elif "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY:
            st.error("⚠️ Streamlit Secrets에 API 키를 설정해주세요!")
            clear_generation_status()
        elif not any([select_t1, select_t2, select_t3, select_t4, select_t5, select_t6, select_t7]) and not use_recommendation:
            st.warning("⚠️ 유형을 최소 하나 이상 선택해주세요.")
            clear_generation_status()
        else:
            status = st.empty()
            status.info(f"⚡ [{current_domain}] 영역의 특성을 반영하여 출제 중입니다... (약 20~40초)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                generation_config = genai.types.GenerationConfig(
                    temperature=0.1, top_p=0.8, top_k=40, max_output_tokens=40000,
                )
                
                # 3. 지문 생성 및 구성 로직 분기 (프롬프트 구성)
                passage_instruction = ""
                summary_passage_inst = "" 
                summary_answer_inst = "" 
                manual_passage_content = ""

                
                if current_d_mode == '직접 입력':
                    
                    # --- 직접 입력 지문 포맷팅: Python에서 처리 (지문 잘림 문제 해결) ---
                    if current_mode == "단일 지문":
                        # 사용자의 입력 텍스트를 두 번 이상의 줄 바꿈('\n\n' 이상)을 기준으로 분리
                        paragraphs = [p.strip() for p in current_manual_passage.split('\n\n') if p.strip()]
                        manual_passage_content_temp = ""
                        
                        for p in paragraphs:
                            if use_summary:
                                # 문단 요약 칸 추가
                                manual_passage_content_temp += f"<p>{p}</p><div class='summary-blank'>📝 문단 요약 : </div>\n"
                            else:
                                manual_passage_content_temp += f"<p>{p}</p>\n"
                        
                        manual_passage_content = f'<div class="passage">{manual_passage_content_temp}</div>'
                        
                        if use_summary:
                            summary_answer_inst = """
                            - 정답지 맨 앞부분에 **[지문 문단별 핵심 요약 정답]** 섹션을 만드시오.
                            - 각 문단의 요약 정답을 <div class='summary-answer'> 태그 안에 작성하시오.
                            """
                        
                        # 지문 분석 강제 지시 (AI에게 포맷팅된 지문을 넘기지 않고 원본 텍스트를 넘겨 분석만 요청)
                        passage_instruction = f"""
                        2. [분석 대상 지문]:
                        - **[최중요 지시]**: 아래에 [사용자 제공 지문]을 첨부하니, **이 지문만을 분석하여 문제를 생성하시오.**
                        - **[금지]**: **지문을 다시 출력하거나, 지문의 내용 이외의 정보를 임의로 지어내어 문제나 해설에 포함하지 마시오.**
                        - **[지시 사항]**: 문제 생성은 3. 문제 출제 섹션부터 HTML 형식으로 출력하시오.
                        
                        **[반드시 포함할 내용]**: 1. 핵심 주장 요약 (서술형)의 모범 답안과, 문단별 요약 요청이 있을 경우 그 정답을 **정답 및 해설 섹션**에 **절대로 누락 없이** 포함할 것.
                        
                        [사용자 제공 지문]:
                        {current_manual_passage} 
                        """
                        
                    elif current_mode == "주제 통합 (가) + (나)":
                        # 지문 분석 강제 지시
                        passage_instruction = f"""
                        2. [분석 대상 지문 (가) + (나)]:
                        - **[최중요 지시]**: 아래에 [사용자 제공 지문]을 첨부하니, **이 지문만을 분석하여 문제를 생성하시오.**
                        - **[금지]**: **지문을 다시 출력하거나, 지문의 내용 이외의 정보를 임의로 지어내어 문제나 해설에 포함하지 마시오.**
                        - **[지시 사항]**: 문제 생성은 3. 문제 출제 섹션부터 HTML 형식으로 출력하시오.
                        
                        **[반드시 포함할 내용]**: 1. (가),(나) 요약 및 연관성 서술 (서술형)의 모범 답안을 **정답 및 해설 섹션**에 **절대로 누락 없이** 포함할 것.

                        [사용자 제공 지문]:
                        {current_manual_passage} 
                        """
                        
                        # 지문 포맷팅: (가), (나) 라벨과 <div class="passage">를 Python에서 수동으로 생성 (AI 요청 삭제)
                        passage_a_text = st.session_state.get("manual_passage_input_a", "")
                        passage_b_text = st.session_state.get("manual_passage_input_b", "")
                        
                        formatted_passage = ""
                        
                        # (가) 지문 포맷팅
                        if passage_a_text:
                            paragraphs_a = [p.strip() for p in passage_a_text.split('\n\n') if p.strip()]
                            formatted_text_a = "".join([f"<p>{p}</p>" for p in paragraphs_a])
                            
                            formatted_passage += f"""
                            <div class="passage">
                            <span class="passage-label">(가)</span><br>
                            {formatted_text_a}
                            </div>
                            """
                        
                        # (나) 지문 포맷팅
                        if passage_b_text:
                            paragraphs_b = [p.strip() for p in passage_b_text.split('\n\n') if p.strip()]
                            formatted_text_b = "".join([f"<p>{p}</p>" for p in paragraphs_b])
                            
                            formatted_passage += f"""
                            <div class="passage">
                            <span class="passage-label">(나)</span><br>
                            {formatted_text_b}
                            </div>
                            """
                        
                        # 메인 출력에 사용될 내용
                        manual_passage_content = formatted_passage
                        
                        
                else: # AI 생성 모드
                    # **[수정 반영] 난이도 가이드 조건문 추가**
                    if current_difficulty == "최상(LEET급)" or current_difficulty == "상":
                        difficulty_guide = f"""
                        - **[난이도]**: {current_difficulty} 난이도
                        - **[문체]**: 학술 논문이나 전문 서적의 건조하고 현학적인 문체 사용.
                        - **[요구사항]**: 정보 밀도를 극한으로 높이고, 다층적 논리 구조(반박, 절충 등)를 포함할 것. 각 문단은 잡다한 설명 없이 핵심 정보로만 꽉 채워 **4~6문장 내외로 밀도 있게 압축**하시오.
                        """
                    else:
                        # 난이도 '하' 또는 '중' 일 때 (중학생 수준)
                        difficulty_guide = f"""
                        - **[난이도]**: {current_difficulty} 난이도 (중학생 수준)
                        - **[문체]**: 교과서나 일반 상식 수준의 쉽고 친절한 설명 문체 사용.
                        - **[요구사항]**: 문장 구조는 단순하고 명료해야 하며, 전문 용어는 반드시 쉽게 풀어 설명할 것. 한 문단은 **6~8문장 내외**로 작성하여 이해하기 쉽게 충분한 설명을 제공하시오. 지문 길이는 1500자 내외로 유지.
                        """
                    # **[수정 끝]**
                    
                    if use_summary:
                        summary_passage_inst = "<p> 태그로 문단이 끝날 때마다 <div class='summary-blank'>📝 문단 요약 : </div> 태그를 삽입하시오."
                        summary_answer_inst = """
                        - 정답지 맨 앞부분에 **[지문 문단별 핵심 요약 정답]** 섹션을 만드시오.
                        - 각 문단의 요약 정답을 <div class='summary-answer'> 태그 안에 작성하시오.
                        """
                    
                    if current_mode == "단일 지문 (기본)":
                        passage_instruction = f"""
                        2. [단일 지문 작성]:
                        - 분량: **2000자 내외의 장문**. <div class="passage"> 사용.
                        - **반드시 5개 이상의 문단으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                        {summary_passage_inst}
                        - 주제: {current_topic} ({current_domain})
                        {difficulty_guide}
                        """
                    else:
                        passage_instruction = f"""
                        2. [주제 통합 지문 작성 ((가) + (나))]:
                        - 수능 국어 융합 지문 스타일로 작성.
                        - **[독립성 필수] (가)와 (나)는 서로 독립된 글이어야 함. (나) 글에서 '(가)에 따르면' 등의 표현으로 앞 글을 직접 언급하지 말 것.**
                        
                        - **(가) 글**:
                            <div class="passage">
                            <span class="passage-label">(가)</span><br>
                            {st.session_state.topic_a_input} ({st.session_state.dom_a}) 심층 지문 (1200자 내외).
                            **반드시 4문단 이상으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                            {summary_passage_inst}
                            </div>
                        
                        - **(나) 글**:
                            <div class="passage">
                            <span class="passage-label">(나)</span><br>
                            {st.session_state.topic_b_input} ({st.session_state.dom_b}) 심층 지문 (1200자 내외).
                            **반드시 4문단 이상으로 구성하고, 각 문단은 <p> 태그로 구분할 것.**
                            {summary_passage_inst}
                            </div>
                        
                        {difficulty_guide}
                        """
                        # (Part 1/2에서 이어짐)

                # 4. 문제 요청 리스트 구성
                reqs = []
                
                label_type1 = "1. 핵심 주장 요약 (서술형)" if current_mode == "단일 지문 (기본)" or current_mode == "단일 지문" else "1. (가),(나) 요약 및 연관성 서술"
                if select_t1:
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>{label_type1}</h3>
                        <div class="question-box">
                            <b>1. 이 글의 핵심 주장과 내용을 요약하고, 논리적 흐름을 서술하시오. (300자 내외)</b>
                            <div class="write-box"></div>
                        </div>
                    </div>
                    """)

                if select_t2 and count_t2 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>내용 일치 O/X ({count_t2}문항)</h3>
                        - [유형2] 내용 일치 O/X {count_t2}문제 (문장 끝에 (O/X) 표시 필수, 매력적인 오답 유도). 
                        **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t3 and count_t3 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>핵심 빈칸 채우기 ({count_t3}문항)</h3>
                        - [유형3] 핵심 빈칸 채우기 {count_t3}문제. **각 문항은 문장 안에 <span class='blank'></span> 태그를 삽입하여 출제할 것.** **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t4 and count_t4 > 0: 
                        reqs.append(f"""
                    <div class="type-box">
                        <h3>변형 문장 정오판단 ({count_t4}문항)</h3>
                        - [유형4] 변형 문장 정오판단 {count_t4}문제 (문장 끝에 (O/X) 표시 필수, 함정 선지). 
                        **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b> 태그를 사용하여 출제할 것.**
                    </div>
                    """)

                if select_t5 and count_t5 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (일치/불일치) ({count_t5}문항)</h3>
                        - [유형5] 객관식 일치/불일치 {count_t5}문제 (지문 재구성 필요). 
                        **선지 항목은 <div>태그로 감싸서 출력하고 <br> 태그를 사용하지 말 것.**
                        **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b>과 선지 목록(<div class='choices'>)을 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t6 and count_t6 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (추론) ({count_t6}문항)</h3>
                        - [유형6] 객관식 추론 {count_t6}문제 (비판적 사고 요구). 
                        **선지 항목은 <div>태그로 감싸서 출력하고 <br> 태그를 사용하지 말 것.**
                        **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b>과 선지 목록(<div class='choices'>)을 사용하여 출제할 것.**
                    </div>
                    """)
                    
                if select_t7 and count_t7 > 0: 
                    reqs.append(f"""
                    <div class="type-box">
                        <h3>객관식 (보기 적용 3점) ({count_t7}문항)</h3>
                        - [유형7] 보기 적용 고난도 {count_t7}문제 (3점, 킬러 문항). 
                        **<보기> 내용은 반드시 <div class="example-box"> 태그 안에 삽입하고, 선지는 <div class='choices'>를 사용하며 <div>로 항목을 감쌀 것.** **모든 문제는 <div class='question-box'> 안에 번호. <b>문제 발문</b>을 사용하여 출제할 것.**
                    </div>
                    """)


                if use_recommendation:
                    # **[수정 반영] 추천 문제가 누락되지 않도록 강하게 요청하는 지시 추가**
                    rec_prompt = f"""
                    <div class="type-box bonus-box">
                        <h3>🌟 영역 맞춤 추천 문제</h3>
                        <div class="question-box">
                            <b>다음은 {current_domain} 영역의 심화 추천 문제입니다. 반드시 5개 선지의 객관식 문제 1개를 생성하고 정답(번호)을 제시하시오.</b><br><br>
                            <div class="choices">
                                <div>① 보기1</div>
                                <div>② 보기2</div>
                                <div>③ 보기3</div>
                                <div>④ 보기4</div>
                                <div>⑤ 보기5</div>
                            </div>
                            <p style='display: none;'>정답: (정답 번호)</p> </div>
                    </div>
                    """
                    reqs.append(rec_prompt)
                
                # --- 객관식 해설 규칙 텍스트 (비문학용) ---
                # **[오류 회피를 위해 빈 문자열로 대체]**
                objective_rule_text_nonfiction = ''
                # ------------------------------------------------------------------------------------------------
                
                # 5. 최종 프롬프트 구성 및 AI 호출
                
                # **[핵심 수정] f-string 내부에서 '\n'.join(reqs) 사용을 피하기 위해 미리 문자열로 합칩니다.**
                reqs_content = "\n".join(reqs)

                # 1. 프롬프트 시작 부분 (제목/시간 출력 금지 강화)
                prompt_start = f"""
                당신은 대한민국 최고의 수능 국어 출제 위원(평가원장급)입니다.
                난이도: {current_difficulty} (최상위권 변별력 필수)
                
                **[지시사항: HTML <body> 내용만 작성. <html>, <head> 금지]**
                
                **1. [최중요 지시]: 제목(h1, h2), 시간 박스(<div class="time-box">), 그리고 지문 본문은** **절대로 출력하지 마시오.** **출력은 3. 문제 출제 섹션부터 시작하시오.**

                {passage_instruction}
                {summary_passage_inst}
                
                3. 문제 출제 (유형별 묶음):
                - **[핵심]** 문제 유형을 **<div class="type-box">**로 묶고, 그 안에 **'유형 제목(<h3>)'**과 **'해당 유형의 모든 문제들'**을 넣으시오.
                - 전체 문제 번호는 1번부터 연속되게 매기시오.
                {reqs_content}
                
                [태그 및 레이아웃 규칙 (엄수)]
                - **문제의 발문(질문) 부분만 <b> 태그로 굵게.** (선지는 굵게 X)
                - **[중요] 객관식 문제의 발문(질문) 바로 뒤에는 <br><br> 태그를 사용하여 선지와의 간격을 넓히시오.**
                - **[중요] 모든 문제는 각각 <div class="question-box"> 태그로 감싸시오.**
                - 선지 부분은 반드시 <div class="choices">로 감쌀 것.
                - **선지 항목은 반드시 <div>로 감싸서 출력하고 <br> 태그는 사용하지 마시오.**
                - [유형1] 밑 <div class="write-box"></div>.
                - [유형3] 빈칸은 반드시 <span class='blank'></span> 태그를 사용.
                - [유형7] 및 보기는 <div class="example-box">.
                
                [지시사항 5: 정답 및 해설]
                - **문서의 맨 마지막에 딱 한 번만 <div class="answer-sheet"> 태그를 사용하여 정답지를 작성하시오.**
                {summary_answer_inst}

                
                """
                prompt_answer_ox = ""
                total_ox_count = count_t2 + count_t4 # 유형 2와 유형 4의 총 개수
                
                if total_ox_count > 0:
                    # 정오판단 문제는 정답(O/X)과 해설(오답의 경우 틀린 이유)이 모두 필요
                    prompt_answer_ox = f"""
                    <h4>정오판단 문제 정답 및 해설 ({total_ox_count}문항)</h4><br>
                    [지시]: {total_ox_count}문항의 정답과 해설을 작성.
                    - **[필수]** 정답은 반드시 **'O' 또는 'X'** 기호로 명확하게 표기할 것.
                    - **[핵심]** 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 충분히 간격을 확보할 것.
                    - **[해설]** **오답(X)인 경우**, **왜 틀렸는지** 지문에 근거하여 그 **틀린 이유**를 명확하게 설명할 것.
                    <br><br>
                    """

                prompt_answer_blank = ""
                count_t3 = st.session_state.get("t3", 0) # 유형 3의 개수
                
                if count_t3 > 0:
                    prompt_answer_blank = f"""
                    <h4>빈칸 채우기 문제 정답 및 해설 ({count_t3}문항)</h4><br>
                    [지시]: {count_t3}문항의 정답과 해설을 작성.
                    - **[필수]** 각 빈칸의 정답(핵심어)과 해설을 **번호별로 명확하게 분리**하여 제시할 것.
                    - **[핵심]** 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 충분히 간격을 확보할 것.
                    <br><br>
                    """
                # 2. 객관식 해설 부분 (조건부 연결)
                prompt_answer_obj = ""
                total_objective_count = count_t5 + count_t6 + count_t7
                
                if total_objective_count > 0:
                    # **오류 방지 위해 rule_text를 빈 문자열로 사용**
                    rule_text = objective_rule_text_nonfiction
                    count_text = f"<h4>객관식 정답 및 해설 ({total_objective_count}문항)</h4><br>[지시]: {total_objective_count}문항의 정답(번호) 및 상세 해설을 작성. 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 **[최중요] 정답뿐만 아니라 오답 선지 각각의 틀린 이유를 명확하게 설명하고, 반드시 모든 선지의 정오(正誤) 판별 이유를 명시**할 것.<br><br>"
                    prompt_answer_obj = rule_text + count_text
                
                # 3. 프롬프트 최종 마침 부분
                prompt_end = """
                </div>
                """
                
                # 최종 prompt 결합
                prompt = prompt_start + prompt_answer_ox + prompt_answer_blank + prompt_answer_obj + prompt_end
                
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                # 6. 결과 처리 및 출력
                clean_content = response.text.replace("```html", "").replace("```", "").replace("##", "").strip()
                
                # **[핵심 수정] full_html과 clean_content를 별도로 생성 및 저장**
                
                full_html = HTML_HEAD # HTML 헤드 시작
                
                # -----------------------------------------------------------
                # AI 생성 모드일 경우: Python이 헤더/지문 수동 생성
                # -----------------------------------------------------------
                if current_d_mode == 'AI 생성':
                    
                    # 1. 제목/시간 박스를 수동으로 생성
                    html_header_manual = f"<h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>"
                    html_header_manual += f"<div class='time-box'> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div>"
                    full_html += html_header_manual
                    
                    # 2. AI가 생성한 '지문'을 clean_content에서 추출하여 추가
                    passage_match = re.search(r'<div class="passage">.*?<\/div>', clean_content, re.DOTALL)
                    if passage_match:
                        extracted_passage = passage_match.group(0)
                        full_html += extracted_passage
                        # clean_content에서 지문 부분을 제거
                        clean_content = clean_content.replace(extracted_passage, "", 1)
                        
                    # 3. AI 응답 내부에 포함되었을 수 있는 제목/시간/지문 태그를 다시 한번 제거하여 중복 방지
                    clean_content = re.sub(r'<h1>.*?<\/h1>.*?<h2>.*?<\/h2>.*?<div class="time-box">.*?<\/div>|<div class="passage">.*?<\/div>', '', clean_content, flags=re.DOTALL) 
                    
                # -----------------------------------------------------------
                # 직접 입력 모드일 경우: Python이 제목/시간/지문 수동 생성
                # -----------------------------------------------------------
                elif current_d_mode == '직접 입력':
                    
                    # 1. 제목/시간 박스를 수동으로 생성
                    html_header_manual = f"<h1>사계국어 비문학 스펙트럼</h1><h2>[{current_domain} 영역: {current_topic}]</h2>"
                    html_header_manual += f"<div class='time-box'> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div>"
                    full_html += html_header_manual
                    
                    # 2. 지문 본문 (manual_passage_content에 저장된 포맷팅된 지문)
                    full_html += manual_passage_content
                    
                    # 3. AI가 생성한 문제 내용 중 불필요한 헤더 부분을 제거
                    # 프롬프트 지시 강화로 인해 지문만 제거하는 것으로 충분해졌습니다.
                    clean_content = re.sub(r'2\. \[분석 대상 지문\].*?\[사용자 제공 지문\].*?{re.escape(current_manual_passage)}.*?(?=\[지시 사항\])', '', clean_content, 1, re.DOTALL)
                    
                    # AI 응답 내부에 포함되었을 수 있는 제목/시간/지문 태그를 다시 한번 제거하여 중복 방지
                    clean_content = re.sub(r'<h1>.*?<\/h1>.*?<h2>.*?<\/h2>.*?<div class="time-box">.*?<\/div>|<div class="passage">.*?<\/div>', '', clean_content, flags=re.DOTALL)
                
                
                # 지문 아래에 나머지 문제 내용 및 정답지 추가
                full_html += clean_content
                full_html += HTML_TAIL # HTML 꼬리말 추가

                
                if len(clean_content) < 100 and not current_manual_passage:
                    st.error("⚠️ 생성 오류: AI가 내용을 충분히 생성하지 못했습니다. **다시 생성하기** 버튼을 눌러주세요.")
                    clear_generation_status()
                else:
                    # **[수정] 생성된 결과를 Session State에 저장**
                    st.session_state.generated_result = {
                        # AI가 생성한 응답의 HTML 포맷 전체
                        "full_html": full_html, 
                        # DOCX 파싱 시 사용하지 않는, AI가 생성한 순수 문제/해설 블록 (사용되지는 않음)
                        "clean_content": clean_content, 
                        "domain": current_domain,
                        "topic": current_topic,
                        "type": "non_fiction"
                    }
                    status.success(f"✅ 생성 완료! (사용 모델: {model_name})")
                    clear_generation_status()


            except Exception as e:
                status.error(f"오류 발생: {e}")
                clear_generation_status()


# ==========================================
# 📖 문학 문제 제작 함수
# ==========================================

def fiction_app():
    
    # **[수정] NameError 방지를 위해 global 명시**
    global GOOGLE_API_KEY
    
    # --------------------------------------------------------------------------
    # [설정값 정의]
    # --------------------------------------------------------------------------
    # 이 함수는 UI를 직접 출력하지 않고, 사이드바와 메인 콘텐츠의 세부 로직만 담당합니다.

    # 1. 입력 설정 (사이드바)
    with st.sidebar:
        st.header("1️⃣ 분석 정보 입력")
        # key 충돌 방지를 위해 fiction_ 접두사를 사용합니다.
        work_name = st.text_input("작품명", placeholder="예: 호질(虎叱) 또는 홍길동전", key="fiction_work_name_input")
        author_name = st.text_input("작가명", placeholder="예: 박지원 또는 허균", key="fiction_author_name_input")
        st.markdown("---")
        
        st.header("2️⃣ 출제 유형 및 개수 선택")
        
        # 유형 1: 어휘 문제 (단답형)
        st.subheader("📝 유형 1. 어휘 문제 (단답형)")
        count_t1 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t1")
        
        # 유형 2: 서술형 심화 문제 (개수 선택)
        st.subheader("✍️ 유형 2. 서술형 심화 문제")
        count_t2 = st.number_input("문항 수 선택 (최대 20)", min_value=0, max_value=20, value=10, key="fiction_c_t2")
        
        # 유형 3: 객관식 문제 (개수 선택)
        st.subheader("🔢 유형 3. 객관식 문제")
        count_t3 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=5, key="fiction_c_t3")

        st.markdown("---")
        st.caption("✅ **단일 분석 콘텐츠 (출제 여부 선택)**")

        # 유형 4: 주요 등장인물 정리 (출제 여부)
        select_t4 = st.checkbox("유형 4. 주요 등장인물 정리 (표)", key="fiction_select_t4")
        
        # 유형 5: 소설 속 상황 요약 (출제 여부)
        select_t5 = st.checkbox("유형 5. 소설 속 상황 요약", key="fiction_select_t5")
        
        # 유형 6: 인물 관계도 및 갈등 작성 (출제 여부)
        select_t6 = st.checkbox("유형 6. 인물 관계도 및 갈등", key="fiction_select_t6")
        
        # 유형 7: 핵심 갈등 구조 및 심리 정리 (출제 여부)
        select_t7 = st.checkbox("유형 7. 핵심 갈등 구조 및 심리", key="fiction_select_t7")
        
        st.markdown("---")
        st.header("3️⃣ 유형 8. 사용자 지정 문제")
        
        # 유형 8: 사용자 지정 문제 (제목 및 개수 입력)
        count_t8 = st.number_input("문항 수 선택 (최대 10)", min_value=0, max_value=10, value=0, key="fiction_c_t8")
        if count_t8 > 0:
            custom_title_t8 = st.text_input("유형 8 제목 및 문제 형식", 
                                             placeholder="예: 비평 관점 적용 문제 (객관식 5개 선지)", 
                                             key="fiction_title_t8")
        else:
            custom_title_t8 = ""
        
        
        # 메인 생성 버튼은 아래 메인 실행부에서 처리됨
        # if st.button("🚀 문학 분석 자료 생성 요청", key="fiction_run_btn"): ...

    # --------------------------------------------------------------------------
    # [AI 생성 및 출력 메인 로직]
    # --------------------------------------------------------------------------

    if st.session_state.generation_requested:
        
        # Session state에서 값들을 가져옵니다.
        current_work_name = st.session_state.fiction_work_name_input
        current_author_name = st.session_state.fiction_author_name_input
        # 메인 컬럼에서 입력된 텍스트를 가져옴
        current_novel_text = st.session_state.fiction_novel_text_input_area 
        
        current_count_t1 = st.session_state.fiction_c_t1
        current_count_t2 = st.session_state.fiction_c_t2
        current_count_t3 = st.session_state.fiction_c_t3
        current_count_t8 = st.session_state.fiction_c_t8
        current_title_t8 = st.session_state.get("fiction_title_t8", "")
        
        select_t4 = st.session_state.get("fiction_select_t4", False)
        select_t5 = st.session_state.get("fiction_select_t5", False)
        select_t6 = st.session_state.get("fiction_select_t6", False)
        select_t7 = st.session_state.get("fiction_select_t7", False)
        
        if not current_novel_text or not current_work_name:
            st.warning("⚠️ 작품명과 소설 텍스트를 모두 입력해주세요!")
            clear_generation_status()
        elif "DUMMY_API_KEY_FOR_LOCAL_TEST" in GOOGLE_API_KEY:
            st.error("⚠️ Streamlit Secrets에 API 키를 설정해주세요!")
            clear_generation_status()
        else:
            status = st.empty()
            status.info(f"⚡문학 분석 콘텐츠를 생성 중입니다... (약 30초 소요)")
            
            try:
                model_name = get_best_model()
                genai.configure(api_key=GOOGLE_API_KEY)
                model = genai.GenerativeModel(model_name)
                
                generation_config = genai.types.GenerationConfig(
                    temperature=0.2, top_p=0.8, max_output_tokens=40000,
                )
                
                # --------------------------------------------------
                # [핵심 프롬프트 구성]
                # --------------------------------------------------
                reqs = []
                current_question_number = 1 # 문제 번호 카운터

                # 1. 유형 1: 어휘 문제 (단답형)
                if current_count_t1 > 0:
                    req_type1 = f"""
                    <div class='type-box'>
                    <h4>유형 1. 어휘 문제 (단답형 {current_count_t1}문항)</h4>
                    [지시]: 소설 내 고난도 한자어 및 고어 {current_count_t1}개를 선정하여 **'번호. 어휘(한자)의 뜻은 무엇인가?' 형식으로 한 줄에 출력**하도록 문제 발문을 작성할 것. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b> <div class='long-blank-line'></div>** 태그를 사용하여 각 문제를 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type1)
                
                # 2. 유형 2: 서술형 심화 문제
                if current_count_t2 > 0:
                    req_type2 = f"""
                    <div class='type-box'>
                    <h4>유형 2. 서술형 심화 문제 (총 {current_count_t2}문항)</h4>
                    [지시]: 작가의 의도, 상징적 의미, 인물의 모순적 행위, **등장인물의 내면 심리 변화**를 묻는 서술형 문제 {current_count_t2}개를 작성. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b><br><br> <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>** 태그를 사용하여 두 줄 밑줄을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type2)

                # 3. 유형 3: 객관식 문제
                if current_count_t3 > 0:
                    req_type3 = f"""
                    <div class='type-box'>
                    <h4>유형 3. 객관식 문제 (총 {current_count_t3}문항)</h4>
                    [지시]: 주제, 서술상 특징, 인물 이해 등 종합 이해도를 묻는 객관식 {current_count_t3}문항을 작성. **문제 발문에는 유형 정보를 포함하지 말 것.** **선지 항목은 반드시 <div>태그로 감싸서 출력**하고, **각 선지 항목 뒤에 <br> 태그를 사용하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>** 후 문제와 5개의 선지(①~⑤)를 **<div class='choices'>** 태그를 사용하여 명확히 분리할 것.
                    </div>
                    """
                    reqs.append(req_type3)

                # 4. 유형 4: 주요 등장인물 정리
                if select_t4:
                    req_type4 = """
                    <div class='type-box'>
                    <h4>유형 4. 주요 등장인물 정리</h4>
                    [지시]: 주요 인물 5명을 분석하여 다음 4개 컬럼으로 구성된 **빈칸 표**를 작성하시오.
                    [출력]: **<div class='question-box'>** 안에 <b>주요 등장인물 정리 (학생 작성)</b><br> 다음 형식의 HTML 표(class="analysis-table")를 작성할 것. **내용은 모두 비워두고 헤딩과 5개의 빈 행(class="blank-row")만 남길 것.** (컬럼: 인물명, 지문 내 호칭/역할, 작중 역할 (기능), 심리 및 비판 의도)
                    </div>
                    """
                    reqs.append(req_type4)

                # 5. 유형 5: 소설 속 상황 요약
                if select_t5:
                    req_type5 = f"""
                    <div class='type-box'>
                    <h4>유형 5. 소설 속 상황 요약</h4>
                    <b>분석 텍스트의 배경, 핵심 사건, 주요 갈등의 표면적 계기를 4문장 이내로 간결하게 요약하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type5)

                # 6. 유형 6: 인물 관계도 및 갈등 작성
                if select_t6:
                    req_type6 = f"""
                    <div class='type-box'>
                    <h4>유형 6. 인물 관계도 및 갈등 작성</h4>
                    <b>주요 인물을 중심으로, 인물 간의 관계와 갈등 요소를 화살표와 용어를 사용하여 구조적으로 설명하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type6)

                # 7. 유형 7: 핵심 갈등 구조 및 심리 정리
                if select_t7:
                    req_type7 = f"""
                    <div class='type-box'>
                    <h4>유형 7. 핵심 갈등 구조 및 심리 정리</h4>
                    <b>1) 갈등 양상(성격)과 2) 작가가 궁극적으로 풍자하려는 대상 및 주제 의식을 명확히 서술하시오.</b>
                    [출력]: <div class='answer-line-gap'></div> <div class='answer-line-gap'></div>
                    </div>
                    """
                    reqs.append(req_type7)

                # 8. 유형 8: 사용자 지정 문제
                if current_count_t8 > 0:
                    req_type8 = f"""
                    <div class='type-box'>
                    <h4>유형 8. {current_title_t8} (총 {current_count_t8}문항)</h4>
                    [지시]: **유형 8 제목({current_title_t8})에 명시된 형식과 목표**에 따라 {current_count_t8}문항을 생성하시오. **문제 발문에는 유형 정보를 포함하지 말 것.**
                    [출력]: **<div class='question-box'>** 안에 **번호. <b>문제 발문</b>**을 출력하고, 유형 제목에 객관식(5개 선지)이 명시되었다면 **<div class='choices'>**를 사용하여 선지를 구성할 것. 객관식이 아니라면 **<div class='write-box'></div>**를 사용하여 답안 공간을 확보할 것.
                    </div>
                    """
                    reqs.append(req_type8)
                
                # **[핵심 수정] f-string 외부에서 reqs 리스트를 문자열로 합칩니다.**
                reqs_content = "\n".join(reqs)

                # 지문 및 작품 정보 구성
                passage_instruction = f"""
                <div class="passage">
                    <b>[분석 텍스트]</b><br>
                    {current_novel_text}
                </div>
                <div class="source-info">
                    {current_work_name} - {current_author_name}
                </div>
                """
                
                # --- 객관식 해설 규칙 텍스트 (문학용) ---
                # **[오류 회피를 위해 빈 문자열로 대체]**
                objective_rule_text_fiction = ''
                # ------------------------------------------------------------------------------------------------

                # 1. 프롬프트 시작 부분 (정답지 시작 태그까지)
                prompt_start = f"""
                당신은 수능/LEET급의 최상위권 변별력을 목표로 하는 국어 문학 평가원 출제 위원입니다.
                [출제 목표] 단순 암기나 사실 확인을 배제하고, 고도의 추론, 비판적 분석, 관점 비교를 요구하는 킬러 문항을 출제해야 합니다. 모든 문제는 최상위권 변별에 초점을 맞추어 논리적 함정을 포함하십시오.

                입력된 [소설 텍스트]를 분석하여 아래 지시된 유형들을 **선택된 순서와 개수**에 따라 정확한 태그로 생성하세요.

                작품명: {current_work_name} / 작가: {current_author_name}
                
                **[지시사항: HTML <body> 내용만 작성. <html>, <head> 금지]**
                
                1. 제목: <h1>사계국어 문학 분석 스펙트럼</h1>
                
                2. 지문 제시:
                {passage_instruction}
                
                3. 분석 콘텐츠 생성 (선택된 유형만 순서 및 태그 엄수):
                {reqs_content}
                
                ---
                
                4. 정답 및 해설 작성 (문서의 맨 마지막):
                <div class="answer-sheet">
                    <h3>✅ 정답 및 해설</h3>
                    
                    """

                # 2. 정답 및 해설 콘텐츠 (조건부 연결 - f-string 오류 해결)
                prompt_answer_content = ""
                
                if current_count_t1 > 0:
                    prompt_answer_content += f"<h4>유형 1. 어휘 문제 정답 및 풀이 ({current_count_t1}문항)</h4><br>[지시]: {current_count_t1}문항의 정답과 뜻풀이를 모두 작성. 각 문제의 해설은 줄 바꿈(<br>)하여 구분할 것.<br><br>"

                if current_count_t2 > 0:
                    prompt_answer_content += f"<h4>유형 2. 서술형 심화 문제 모범 답안 ({current_count_t2}문항)</h4><br>[지시]: {current_count_t2}문항의 모범 답안을 상세하게 작성하되, **각 문제의 모범 답안이 끝날 때마다 <br><br><br> 태그를 사용하여 충분히 간격을 확보하여 분리할 것.**<br><br>"

                if current_count_t3 > 0:
                    # **오류 방지 위해 rule_text를 빈 문자열로 사용**
                    rule_text = objective_rule_text_fiction
                    count_text = f"<h4>유형 3. 객관식 문제 정답 및 해설 ({current_count_t3}문항)</h4><br>[지시]: {current_count_t3}문항의 정답(번호) 및 상세 해설을 작성. 각 문제 해설 사이에 <br><br><br> 태그를 사용하여 **[최중요] 정답뿐만 아니라 오답 선지 각각의 틀린 이유를 명확하게 설명하고, 반드시 모든 선지의 정오(正誤) 판별 이유를 명시**할 것.<br><br>"
                    
                    rule_block = rule_text + count_text
                    
                    prompt_answer_content += f"<h4>유형 3. 객관식 문제 정답 및 해설 ({current_count_t3}문항)</h4><br>[지시]: {rule_block}"
                
                if select_t4:
                    prompt_answer_content += "<h4>유형 4. 주요 등장인물 정리 모범 답안</h4><br>[지시]: 유형 4에서 요구한 표 형식에 맞춰 모범 답안을 작성하여 제시.<br><br>"

                if select_t5:
                    prompt_answer_content += "<h4>유형 5. 소설 속 상황 요약 모범 답안</h4><br>[지시]: 유형 5의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if select_t6:
                    prompt_answer_content += "<h4>유형 6. 인물 관계도 및 갈등 모범 답안</h4><br>[지시]: 유형 6의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if select_t7:
                    prompt_answer_content += "<h4>유형 7. 핵심 갈등 구조 및 심리 모범 답안</h4><br>[지시]: 유형 7의 질문에 대한 모범적인 분석 내용을 작성하여 제시.<br><br>"

                if current_count_t8 > 0:
                    prompt_answer_content += f"<h4>유형 8. {current_title_t8} 모범 답안 ({current_count_t8}문항)</h4><br>[지시]: 유형 8({current_title_t8})의 모범 답안을 상세하게 작성. 각 문제의 모범 답안이 끝날 때마다 **<br><br><br> 태그를 사용하여 충분히 간격을 확보하여 분리할 것.**<br><br>"
                
                # 3. 프롬프트 최종 마침 부분
                prompt_end = """
                </div>
                """
                
                # 최종 prompt 결합
                prompt = prompt_start + prompt_answer_content + prompt_end
                
                
                response = model.generate_content(prompt, generation_config=generation_config)
                
                clean_content = response.text.replace("```html", "").replace("```", "").replace("##", "").strip()
                
                # -----------------------------------------------------------
                # Header 및 Passage 추출 (수동 생성)
                # -----------------------------------------------------------
                html_header_manual = f"<h1>사계국어 문학 분석 스펙트럼</h1><h2>[작품명: {current_work_name} / 작가: {current_author_name}]</h2>"
                html_header_manual += f"<div class='time-box'> ⏱️ 실제 소요 시간: <span class='time-blank'></span> 분 </div>"
                
                # 지문 본문
                passage_html_manual = f"""
                <div class="passage">
                    <b>[분석 텍스트]</b><br>
                    {current_novel_text}
                </div>
                <div class="source-info">
                    {current_work_name} - {current_author_name}
                </div>
                """
                
                full_html = HTML_HEAD + html_header_manual + passage_html_manual + clean_content + HTML_TAIL
                
                # clean_content는 AI의 순수 응답 내용 (문제 + 해설)이므로, 문제 번호 등을 제거
                clean_content_for_parsing = re.sub(r'<h1>.*?<\/div>.*?<div class="time-box">.*?<\/div>|2\. \[.*?지문\]:.*?지시\]:.*?지문은 다시 출력하지 마시오\.', '', clean_content, 1, re.DOTALL)
                
                if len(clean_content) < 100 and not current_novel_text:
                    st.error(f"⚠️ 생성 오류: AI가 내용을 충분히 생성하지 못했습니다. (생성 길이: {len(clean_content)}). **다시 생성하기** 버튼을 눌러주세요.")
                    clear_generation_status()
                else:
                    # **[수정] 생성된 결과를 Session State에 저장**
                    st.session_state.generated_result = {
                        "full_html": full_html,
                        # DOCX 파싱 시 사용하지 않는, AI가 생성한 순수 문제/해설 블록 (사용되지는 않음)
                        "clean_content": clean_content_for_parsing, 
                        "domain": current_work_name,
                        "topic": current_author_name,
                        "type": "fiction"
                    }
                    st.success(f"✅ 분석 학습지 생성 완료! (사용 모델: {model_name})")
                    clear_generation_status()


            except Exception as e:
                st.error(f"오류 발생: {e}. API 키와 입력값을 확인해주세요.")
                clear_generation_status()


# ==========================================
# 🚀 메인 애플리케이션 실행
# ==========================================

# **[수정] 다운로드 버튼 및 결과 출력 함수**
def display_results():
    """Session State에 저장된 결과를 기반으로 HTML 렌더링 및 다운로드 버튼을 표시합니다."""
    
    result = st.session_state.generated_result
    if result is None:
        return

    # 결과 변수 로드
    full_html = result["full_html"]
    # clean_content는 현재 사용되지 않음. DOCX 파싱에는 full_html 사용
    current_topic_doc = result["topic"]
    current_domain_doc = result["domain"]
    app_type = result["type"]

    st.markdown("---")
    st.subheader(f"📊 생성 결과")
    
    # --- [재생성 버튼 및 다운로드 추가] ---
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # 버튼을 누르면 request_generation 함수가 실행되고 Session State가 초기화되며 앱이 재실행됨
        st.button("🔄 다시 생성하기 (같은 내용으로 재요청)", on_click=request_generation)
    
    # 파일 이름 설정
    if app_type == "non_fiction":
        html_file_name = f"사계국어_모의고사.html"
        docx_file_name = f"{current_domain_doc.replace(' ', '_')}_모의고사.docx"
    else: # fiction
        html_file_name = f"{current_domain_doc}_분석_학습지.html"
        docx_file_name = f"{current_domain_doc}_분석_학습지.docx"
        
    with col2:
        st.download_button("📥 시험지 다운로드 (HTML)", full_html, html_file_name, "text/html")
    
    with col3:
        # DOCX 파일 생성 (Session State에 저장된 full_html 사용)
        # 다운로드 버튼 클릭 시 Streamlit이 이 함수를 호출하여 BytesIO 스트림을 가져감
        docx_file = create_docx(full_html, docx_file_name, current_topic_doc, is_fiction=(app_type=="fiction"))
        st.download_button(
            label="📄 워드 파일 다운로드 (.docx)",
            data=docx_file,
            file_name=docx_file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    # ------------------------------------

    st.components.v1.html(full_html, height=800, scrolling=True)
# **[수정 완료]**

# 메인 제목
st.title("📚 사계국어 AI 모의고사 제작 시스템")
st.markdown("---")

# 1. 메인 콘텐츠 분할을 위한 컬럼 설정
col_select, col_input = st.columns([1.5, 3]) 

# 1.1. 유형 선택 (왼쪽 컬럼)
with col_select:
    problem_type = st.radio(
        "출제할 문제 유형을 선택해주세요:",
        ["⚡ 비문학 문제 제작", "📖 문학 문제 제작"],
        key="app_mode",
        index=0 
    )

# 1.2. 지문 입력창 및 제목 출력 (오른쪽 컬럼)
with col_input:
    current_app_mode = st.session_state.get('app_mode')

    if current_app_mode == "⚡ 비문학 문제 제작":
        # 머리말을 컬럼 맨 위에 출력
        st.header("⚡ 비문학 모의평가 출제")
        
        current_d_mode = st.session_state.get('domain_mode_select', 'AI 생성')
        current_manual_mode = st.session_state.get("manual_mode", "단일 지문")

        if current_d_mode == '직접 입력':
            if current_manual_mode == "단일 지문":
                st.text_area("분석할 지문 텍스트 (문단 구분은 **빈 줄**로 해주세요)", height=300, key="manual_passage_input_col_main",
                             placeholder="[비문학 - 단일 지문]의 내용을 여기에 붙여넣어 주세요. (엔터 두 번으로 문단 구분)")
            elif current_manual_mode == "주제 통합 (가) + (나)":
                st.caption("사이드바에서 지문 구성 및 주제 설정을 완료해주세요.")
                
                # (가)와 (나) 지문을 나란히 표시
                col_a_input, col_b_input = st.columns(2)
                with col_a_input:
                    st.text_area("🅰️ (가) 지문 텍스트 (문단 구분은 빈 줄)", height=300, key="manual_passage_input_a",
                                 placeholder="(가) 지문의 내용을 입력하세요. (엔터 두 번으로 문단 구분)")
                with col_b_input:
                    st.text_area("🅱️ (나) 지문 텍스트 (문단 구분은 빈 줄)", height=300, key="manual_passage_input_b",
                                 placeholder="(나) 지문의 내용을 입력하세요. (엔터 두 번으로 문단 구분)")
        else:
            # AI 생성 모드일 때 메시지 출력
            st.caption("지문 입력 방식이 'AI 생성'으로 설정되어 있습니다. 사이드바 설정을 완료하고 아래 '모의평가 출제하기' 버튼을 눌러주세요.")
            st.markdown("<div style='height: 150px;'></div>", unsafe_allow_html=True) # 겹침 방지용 빈 공간 추가


    elif current_app_mode == "📖 문학 문제 제작":
        # 머리말 및 입력창 출력
        st.header("📖 문학 심층 분석 콘텐츠 제작")
        st.subheader("📖 분석할 소설 텍스트 입력")
        
        # 문학 영역일 경우, 소설 텍스트를 입력받음
        st.text_area("소설 텍스트 (발췌분도 가능)", height=300, 
                     placeholder="[문학] 분석할 소설 텍스트 전체(또는 발췌분)를 여기에 붙여넣어 주세요.", 
                     key="fiction_novel_text_input_area")
        

    # 3. 메인 실행 버튼 (오른쪽 컬럼 맨 아래에 배치)
    if current_app_mode == "⚡ 비문학 문제 제작" and st.button("🚀 모의평가 출제하기 (클릭)", key="non_fiction_run_btn_col"):
        request_generation()
    elif current_app_mode == "📖 문학 문제 제작" and st.button("🚀 문학 분석 자료 생성 요청", key="fiction_run_btn_col"):
        request_generation()


st.markdown("---") # 메인 콘텐츠 분할선

# 2. 선택에 따른 함수 실행 (메인 콘텐츠 영역 아래에서 실행)
if problem_type == "⚡ 비문학 문제 제작":
    non_fiction_app()
elif problem_type == "📖 문학 문제 제작":
    fiction_app()

# **[수정] 생성 결과가 Session State에 있으면 표시**
display_results()
