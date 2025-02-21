import asyncio
import streamlit as st
import pandas as pd

from utils import (
    init_session_state,
    display_interviewers,
    extract_text_from_pdfs,
    handle_file_upload,
    handle_interviewer_creation,
    handle_feedback_submission,
    handle_question_generation,
    save_conversation_history,
    display_conversation_history,
)
import interviewer_workflow
import question_workflow
import conversation_workflow

from langchain_core.runnables import RunnableConfig
from states import ConversationStatus
from interview_workflow import run_interview_workflow

# 사용자 입력을 위한 전역 변수


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
    # 면접관 정보를 session_state에 저장
    st.session_state.interviewers = st.session_state.graph.get_state(
        st.session_state.config
    ).values["interviewers"]


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


async def run_interview_workflow():
    config = RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )
    st.session_state.graph = conversation_workflow.create_graph()
    session = st.session_state.interview_session

    if session:
        if session.is_completed:
            end_interview(session)
            return

        if st.session_state.current_interviewer_idx >= len(
            session.interviewer_sessions
        ):
            session.status = ConversationStatus.COMPLETED
            end_interview(session)
            return

        current_session = session.interviewer_sessions[
            st.session_state.current_interviewer_idx
        ]
        current_question = current_session.conversations[
            st.session_state.current_question_idx
        ]

        display_current_question(current_session, current_question)

        if st.session_state.get("submit", False):
            await process_user_input(session, current_session, current_question, config)


def end_interview(session):
    st.success("면접이 종료되었습니다.")
    display_conversation_history(session)
    st.rerun()


def display_current_question(current_session, current_question):

    # 사용자 응답 입력을 위한 폼
    with st.form(key="answer_form"):
        with st.container():
            st.markdown(f"**면접관:** {current_session.interviewer.name}")
            st.markdown(f"**질문:** {current_question.question_text}")
        if "user_input" not in st.session_state:
            st.session_state["user_input"] = ""

        st.text_area(
            "답변을 입력하세요:",
            key="user_input",
            value=st.session_state["user_input"],
            height=68,
        )

        # 제출 버튼
        submit_button = st.form_submit_button(label="제출")

    # 제출 버튼이 클릭되었을 때 처리
    if submit_button:
        st.session_state["submit"] = True


async def process_user_input(session, current_session, current_question, config):
    interviewer_length = len(session.interviewer_sessions)
    inputs = {
        "session": session,
        "user_input": st.session_state["user_input"],
        "interviewer_idx": st.session_state.current_interviewer_idx,
        "question_idx": st.session_state.current_question_idx,
        "max_question_length": interviewer_length * 3 * 2,
    }
    with st.spinner("답변 분석 중..."):
        await st.session_state.graph.ainvoke(inputs, config)

    save_conversation_history(current_session, current_question)
    update_question_index(session, current_session)


def update_question_index(session, current_session):
    st.session_state.current_question_idx += 1
    if st.session_state.current_question_idx >= len(current_session.conversations):
        st.session_state.current_question_idx = 0
        st.session_state.current_interviewer_idx += 1
        if st.session_state.current_interviewer_idx >= len(
            session.interviewer_sessions
        ):
            session.status = ConversationStatus.COMPLETED
            st.success("면접이 종료되었습니다.")
            st.rerun()


def setup_sidebar():
    """사이드바 설정"""
    with st.sidebar:
        st.markdown("## PDF 업로드")
        handle_file_upload()

        # 토글 상태를 세션 상태에 저장
        if "show_settings" not in st.session_state:
            st.session_state.show_settings = True  # 초기 상태를 True로 설정

        # 면접관 설정 및 피드백 토글
        st.session_state.show_settings = st.checkbox(
            "면접관 설정 및 피드백 보기", value=st.session_state.show_settings
        )

        # Initialize variables
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

        # 면접결과 평가 버튼 추가
        evaluate_results_btn = st.button("면접결과 평가")

    return (
        interviewer_btn,
        submit_feedback,
        jd_container,
        feedback_container,
        job_description,
        max_interviewer,
        feedback_input,
        evaluate_results_btn,
    )


async def main():
    """인터뷰 에이전트를 실행하는 메인 함수."""
    init_session_state()
    st.markdown(
        "<h1 style='text-align: center;'>면접 에이전트</h1>", unsafe_allow_html=True
    )

    (
        interviewer_btn,
        submit_feedback,
        jd_container,
        feedback_container,
        job_description,
        max_interviewer,
        feedback_input,
        evaluate_results_btn,
    ) = setup_sidebar()

    first_result_container = st.empty()
    interviewer_info_container = st.empty()  # 면접관 정보를 표시할 컨테이너

    if interviewer_btn:
        handle_interviewer_creation(job_description, max_interviewer)
        # 면접관 정보를 표시
        display_interviewers(st.session_state.interviewers, interviewer_info_container)

    if submit_feedback:
        jd_container.empty()
        feedback_container.empty()
        first_result_container.empty()
        interviewer_info_container.empty()  # 면접관 정보 컨테이너 비우기
        handle_feedback_submission(feedback_input, interviewer_info_container)
        # 피드백 제출 후 자동으로 면접 질문 생성
        await handle_question_generation()

    if evaluate_results_btn:
        # 평가 프로세스 구현 필요.
        print(st.session_state.interview_session)

    if "interview_session" in st.session_state and st.session_state.interview_session:
        interviewer_info_container.empty()  # 면접 시작 시 면접관 정보 비우기
        st.session_state.show_settings = False  # 면접 시작 시 토글 닫기
        await run_interview_workflow()
    else:
        st.warning("면접 세션이 초기화되지 않았습니다. 먼저 질문을 생성하세요.")


if __name__ == "__main__":
    asyncio.run(main())