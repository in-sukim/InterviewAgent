import streamlit as st
import tempfile
import os
import pymupdf4llm
import uuid


def init_session_state():
    """Streamlit 세션 상태 초기화"""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    if "resume" not in st.session_state:
        st.session_state.resume = ""
    if "graph" not in st.session_state:
        st.session_state.graph = None
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    if "interview_session" not in st.session_state:
        st.session_state.interview_session = None
    if "answer" not in st.session_state:
        st.session_state.answer = ""
    if "current_interviewer_idx" not in st.session_state:
        st.session_state.current_interviewer_idx = 0
    if "current_question_idx" not in st.session_state:
        st.session_state.current_question_idx = 0
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = False


def process_files_and_extract_text():
    """파일 업로드 및 PDF 텍스트 추출을 처리합니다."""
    pdffiles = st.file_uploader(
        "여기에 PDF 파일을 업로드하세요:", type="pdf", accept_multiple_files=True
    )
    if pdffiles:
        new_files = [
            file
            for file in pdffiles
            if file not in st.session_state.get("uploaded_files", [])
        ]
        if new_files:
            st.session_state["uploaded_files"] = (
                st.session_state.get("uploaded_files", []) + new_files
            )
            for file in new_files:
                try:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".pdf"
                    ) as temp_file:
                        temp_file.write(file.read())
                        temp_file_path = temp_file.name
                    md_text = pymupdf4llm.to_markdown(temp_file_path)
                    st.session_state["resume"] = (
                        st.session_state.get("resume", "") + md_text
                    )
                    os.remove(temp_file_path)
                except Exception as e:
                    st.error(f"Error processing file {file.name}: {e}")


def setup_sidebar():
    """사이드바 설정"""
    with st.sidebar:
        st.markdown("## PDF 업로드")
        process_files_and_extract_text()

        if "show_settings" not in st.session_state:
            st.session_state.show_settings = True

        st.session_state.show_settings = st.checkbox(
            "면접관 설정 및 피드백 보기", value=st.session_state.show_settings
        )

        interviewer_btn = None
        submit_feedback = None
        jd_container = None
        feedback_container = None
        job_description = ""
        max_interviewer = 2
        feedback_input = ""

        if st.session_state.show_settings:
            with st.expander("면접관 설정 및 피드백"):
                jd_container = st.empty()
                with jd_container.form(key="job_description_form"):
                    job_description = st.text_input("채용 공고 내용", "")
                    max_interviewer = st.number_input(
                        "면접관 수", min_value=1, max_value=4, value=2
                    )
                    interviewer_btn = st.form_submit_button("면접관 생성")

                feedback_container = st.empty()
                with feedback_container.form(key="feedback_form"):
                    feedback_input = st.text_input(
                        "피드백 (없을 경우 빈칸 제출)", value=None
                    )
                    submit_feedback = st.form_submit_button("제출")

    return (
        interviewer_btn,
        submit_feedback,
        jd_container,
        feedback_container,
        job_description,
        max_interviewer,
        feedback_input,
    )


def display_interviewers(interviewers, container):
    """List[Interviewer] 타입의 면접관 목록을 입력받아 HTML 형식으로 출력.
    interviewers: List[Interviewer]
        name: str
        affiliation: str
        position_experience: str
        main_tasks: str
        description: str
    container: 표시 컨테이너
    """
    # 컨테이너 비우기
    container.empty()
    # HTML 콘텐츠 생성
    html_content = ""
    for interviewer in interviewers:
        html_content += f"""
        <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <strong>이름</strong>: {interviewer.name}<br>
            <strong>소속</strong>: {interviewer.affiliation}<br>
            <strong>직책 경험</strong>: {interviewer.position_experience}<br>
            <strong>주요 업무</strong>: {interviewer.main_tasks}<br>
            <strong>설명</strong>: {interviewer.description}
        </div>
        """

    # HTML 콘텐츠 렌더링
    container.markdown(html_content, unsafe_allow_html=True)
