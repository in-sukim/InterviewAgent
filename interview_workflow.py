import streamlit as st
from langchain_core.runnables import RunnableConfig
import conversation_workflow
from utils import (
    save_conversation_history,
    display_conversation_history,
)
from states import ConversationStatus


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
    with st.container():
        st.markdown(f"### 면접관: {current_session.interviewer.name}")
        st.markdown(f"**질문:** {current_question.question_text}")

        with st.form(key="answer_form"):
            if "user_input" not in st.session_state:
                st.session_state["user_input"] = ""

            st.markdown(
                """
                <style>
                .stTextArea {
                    max-width: 500px;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            st.text_area(
                "답변을 입력하세요:",
                key="user_input",
                value=st.session_state["user_input"],
                height=68,
            )

            submit_button = st.form_submit_button(label="제출")

        if submit_button:
            st.session_state["submit"] = True


async def process_user_input(session, current_session, current_question, config):
    inputs = {
        "session": session,
        "user_input": st.session_state["user_input"],
        "interviewer_idx": st.session_state.current_interviewer_idx,
        "question_idx": st.session_state.current_question_idx,
        "max_question_length": 10,
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
