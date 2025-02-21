import streamlit as st
import tempfile
import os
import pymupdf4llm
import uuid
from langchain_core.runnables import RunnableConfig
import interviewer_workflow
import question_workflow
import conversation_workflow


def init_session_state():
    """Streamlit 세션 상태 초기화"""
    if "graph" not in st.session_state:
        st.session_state.graph = None
    if "interview_session" not in st.session_state:
        st.session_state.interview_session = None
    if "config" not in st.session_state:
        st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    if "resume" not in st.session_state:
        st.session_state.resume = ""
    if "current_interviewer_idx" not in st.session_state:
        st.session_state.current_interviewer_idx = 0
    if "current_question_idx" not in st.session_state:
        st.session_state.current_question_idx = 0
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []


# PDF 파일 텍스트 추출
def extract_text_from_pdfs(pdffiles):
    """PDF 파일 텍스트 추출"""
    new_files = [
        file for file in pdffiles if file not in st.session_state["uploaded_files"]
    ]
    if new_files:
        st.session_state["uploaded_files"].extend(new_files)
        for file in new_files:
            process_pdf_file(file)


def process_pdf_file(file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file.read())
            temp_file_path = temp_file.name
        md_text = pymupdf4llm.to_markdown(temp_file_path)
        st.session_state["resume"] += md_text
        os.remove(temp_file_path)
    except Exception as e:
        st.error(f"Error processing file {file.name}: {e}")


def display_interviewers(interviewers, container):
    """List[Interviewer] 타입의 면접관 목록을 입력받아 HTML 형식으로 출력"""
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


# 사용자 입력 처리 및 채팅 메시지 업데이트
def handle_input():
    """사용자 입력 처리 및 채팅 메시지 업데이트"""
    if "questions" in st.session_state:
        current_index = st.session_state["current_question_index"]
        if current_index < len(st.session_state["questions"]):
            current_question = st.session_state["questions"][current_index]
            user_input = st.session_state.get(f"answer_{current_index}", "")
            if user_input:
                st.session_state["messages"].append(
                    {
                        "interviewer": current_question.interviewer_name,
                        "question": current_question.question,
                        "answer": user_input,
                    }
                )
                st.session_state["current_question_index"] += 1


def display_questions(questions, container=None):
    """List[InterviewQuestion] 타입의 면접 질문 목록을 입력받아 HTML 형식으로 출력"""
    if container is None:
        container = st

    # 모든 HTML 콘텐츠 누적
    html_content = ""
    for question in questions:
        html_content += f"""
        <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <strong>면접관</strong>: {question.interviewer_name}<br>
            <strong>질문</strong>: {question.question}<br>
            <strong>목적</strong>: {question.purpose}
        </div>
        """

    # 한 번에 모든 콘텐츠 렌더링
    container.markdown(html_content, unsafe_allow_html=True)


def handle_file_upload():
    """파일 업로드 및 PDF에서 텍스트 추출 처리."""
    pdffiles = st.file_uploader(
        "여기에 PDF 파일을 업로드하세요:", type="pdf", accept_multiple_files=True
    )
    if pdffiles:
        extract_text_from_pdfs(pdffiles)


def handle_interviewer_creation(job_description, max_interviewer):
    """채용 공고와 최대 면접관 수에 따라 면접관 생성."""
    st.session_state.graph = interviewer_workflow.create_graph()
    config = RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )
    inputs = {"jd": job_description, "max_interviewer": max_interviewer}
    st.session_state.graph.invoke(inputs, config)
    st.success("면접관 생성 완료!")
    display_interviewers(
        st.session_state.graph.get_state(st.session_state.config).values[
            "interviewers"
        ],
        st,
    )


def handle_feedback_submission(feedback_input, container):
    """피드백 제출 및 면접관 상태 업데이트."""
    config = RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )
    st.session_state.graph.update_state(
        config, {"feedback": feedback_input}, as_node="user_feedback"
    )
    st.session_state.graph.invoke(None, config)
    display_interviewers(
        st.session_state.graph.get_state(config).values["interviewers"], container
    )


async def handle_question_generation():
    """각 면접관에 대한 면접 질문 생성."""
    interviewers = st.session_state.graph.get_state(st.session_state.config).values[
        "interviewers"
    ]
    questions = await question_workflow.generate_questions_for_interviewers(
        interviewers, st.session_state.resume
    )
    st.session_state.interview_session = conversation_workflow.init_interview_session(
        interviewers, questions
    )


def save_conversation_history(current_session, current_question):
    if "conversation_history" not in st.session_state:
        st.session_state["conversation_history"] = []
    st.session_state["conversation_history"].append(
        {
            "interviewer": current_session.interviewer.name,
            "question": current_question.question_text,
            "answer": st.session_state["user_input"],
        }
    )


def display_conversation_history(session):
    """면접이 종료된 후 대화 내용을 보기 좋게 출력합니다."""
    st.markdown("#### 전체 대화 내용")

    for interviewer_session in session.interviewer_sessions:
        with st.expander(f"면접관: {interviewer_session.interviewer.name}"):
            for conversation in interviewer_session.conversations:
                question_label = (
                    "추가 질문" if conversation.purpose == "Follow-up" else "질문"
                )
                st.markdown(f"**{question_label}:** {conversation.question_text}")
                st.markdown(
                    f"**답변:** {conversation.answer if conversation.answer else '답변 없음'}"
                )
                st.markdown("---")  # 구분선 추가
