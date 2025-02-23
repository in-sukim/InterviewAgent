import streamlit as st
from langchain_core.runnables import RunnableConfig
import workflow.followup_workflow as followup_workflow
from utils import (
    display_conversation_history,
)
from states import ConversationStatus


def run_interview_workflow(container):
    # 설정 초기화
    config = RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )
    # 그래프 생성
    st.session_state.graph = followup_workflow.create_graph()
    # 현재 인터뷰 세션 가져오기
    session = st.session_state.interview_session

    if not session:
        return

    # 인덱스 범위 체크
    if not is_valid_index(session):
        complete_session(session, container)
        return

    # 현재 세션과 질문 가져오기
    current_session = session.interviewer_sessions[
        st.session_state.current_interviewer_idx
    ]
    current_question = current_session.conversations[
        st.session_state.current_question_idx
    ]

    # 컨테이너를 사용하여 현재 질문 표시
    analyze_button = display_current_question(
        current_session, current_question, container
    )

    # 사용자가 제출 버튼을 클릭했는지 확인
    if analyze_button:
        process_user_input(session, config, container)
        update_question_index(session, current_session)
        display_current_question(current_session, current_question, container)
        st.rerun()

    # 모든 세션이 완료되었는지 확인
    if all(
        s.status == ConversationStatus.COMPLETED for s in session.interviewer_sessions
    ):
        complete_session(session, container)


# 현재 질문을 화면에 표시하는 함수
def display_current_question(current_session, current_question, container):
    with container:
        with st.form(
            key=f"form_{st.session_state.current_interviewer_idx}_{st.session_state.current_question_idx}",
            clear_on_submit=True,
        ):
            st.markdown(f"**면접관:** {current_session.interviewer.name}")
            st.markdown(f"**질문:** {current_question.question_text}")

            answer = st.text_area(
                "답변을 입력하세요:",
                key=f"answer_{st.session_state.current_interviewer_idx}_{st.session_state.current_question_idx}",
                height=68,
            )
            st.session_state["answer"] = answer

            analyze_button = st.form_submit_button(label="답변분석")

        if analyze_button:
            st.session_state["analyze"] = True

    return analyze_button


# 사용자의 입력을 처리하는 비동기 함수
def process_user_input(session, config, container):
    inputs = {
        "session": session,
        "user_input": st.session_state["answer"],
        "interviewer_idx": st.session_state.current_interviewer_idx,
        "question_idx": st.session_state.current_question_idx,
        "max_question_length": 10,
    }
    with st.spinner("답변 분석 중..."):
        st.session_state.graph.invoke(inputs, config)


# 질문 인덱스를 업데이트하는 함수
def update_question_index(session, current_session):
    st.session_state.current_question_idx += 1
    if st.session_state.current_question_idx >= len(current_session.conversations):
        st.session_state.current_question_idx = 0
        st.session_state.current_interviewer_idx += 1
        # 현재 세션을 완료로 표시
        current_session.status = ConversationStatus.COMPLETED
        if st.session_state.current_interviewer_idx >= len(
            session.interviewer_sessions
        ):
            session.status = ConversationStatus.COMPLETED
            end_interview(session)


def complete_session(session, container):
    """세션을 완료 상태로 설정하고 인터뷰를 종료합니다."""
    if session.status != ConversationStatus.COMPLETED:
        session.status = ConversationStatus.COMPLETED
        container.empty()  # 컨테이너 비우기
        end_interview(session)


# 인터뷰가 완료되었을 때 호출되는 함수
def end_interview(session):
    if session.status == ConversationStatus.COMPLETED:
        st.session_state.conversation_history = True


def is_valid_index(session):
    """현재 인덱스가 유효한지 확인합니다."""
    return 0 <= st.session_state.current_interviewer_idx < len(
        session.interviewer_sessions
    ) and 0 <= st.session_state.current_question_idx < len(
        session.interviewer_sessions[
            st.session_state.current_interviewer_idx
        ].conversations
    )
