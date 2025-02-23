import asyncio
import streamlit as st

from utils import (
    init_session_state,
    display_interviewers,
    setup_sidebar,
)
import workflow.interviewer_workflow as interviewer_workflow
import workflow.question_workflow as question_workflow
import workflow.followup_workflow as followup_workflow
import workflow.interview_workflow as interview_workflow
import workflow.evaluate_workflow as evaluate_workflow
from langchain_core.runnables import RunnableConfig

from states import ConversationStatus


def create_runnable_config():
    """재사용 가능한 RunnableConfig 생성."""
    return RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )


def handle_interviewer_creation(job_description, max_interviewer):
    """채용 공고와 최대 면접관 수에 따라 면접관 생성."""
    # 면접관 생성 그래프 생성
    st.session_state.graph = interviewer_workflow.create_graph()
    # 실행 설정 생성
    config = create_runnable_config()
    # 면접관 생성 입력 정보
    inputs = {"jd": job_description, "max_interviewer": max_interviewer}
    # 면접관 생성
    st.session_state.graph.invoke(inputs, config)
    st.success("면접관 생성 완료!")
    # 면접관 정보 저장
    st.session_state.interviewers = st.session_state.graph.get_state(
        st.session_state.config
    ).values["interviewers"]


def handle_feedback_submission(feedback_input, container):
    """피드백 제출 및 면접관 상태 업데이트."""
    # 실행 설정 생성
    config = create_runnable_config()
    # 피드백 제출
    st.session_state.graph.update_state(
        config, {"feedback": feedback_input}, as_node="user_feedback"
    )
    # 면접관 상태 업데이트
    st.session_state.graph.invoke(None, config)
    # 면접관 정보 표시
    display_interviewers(
        st.session_state.graph.get_state(config).values["interviewers"], container
    )


async def handle_question_generation():
    """각 면접관에 대한 면접 질문 생성."""
    interviewers = st.session_state.graph.get_state(st.session_state.config).values[
        "interviewers"
    ]
    # 면접 질문 생성
    questions = await question_workflow.generate_questions_for_interviewers(
        interviewers, st.session_state.resume
    )
    # 면접 세션 초기화
    st.session_state.interview_session = followup_workflow.init_interview_session(
        interviewers, questions
    )


async def main():
    """인터뷰 에이전트를 실행하는 메인 함수."""
    init_session_state()
    st.markdown(
        "<h1 style='text-align: center;'>면접 에이전트</h1>", unsafe_allow_html=True
    )

    # 사이드바 설정
    (
        interviewer_btn,
        submit_feedback,
        jd_container,
        feedback_container,
        job_description,
        max_interviewer,
        feedback_input,
    ) = setup_sidebar()

    # 결과 평가 컨테이너
    first_result_container = st.empty()
    # 면접관 정보 컨테이너
    interviewer_info_container = st.empty()

    # 면접관 생성 버튼이 눌렸을 때 처리
    if interviewer_btn:
        interviewer_workflow.handle_interviewer_creation(
            job_description, max_interviewer
        )
        display_interviewers(st.session_state.interviewers, interviewer_info_container)
    # 피드백 제출 버튼이 눌렸을 때 처리
    if submit_feedback:
        jd_container.empty()
        feedback_container.empty()
        first_result_container.empty()
        interviewer_info_container.empty()

        handle_feedback_submission(feedback_input, interviewer_info_container)
        await handle_question_generation()

    question_answer_container = st.empty()
    # 면접 세션이 초기화된 경우
    if "interview_session" in st.session_state and st.session_state.interview_session:
        interviewer_info_container.empty()
        st.session_state.show_settings = False
        interview_workflow.run_interview_workflow(question_answer_container)
    else:
        # 면접 세션이 초기화되지 않은 경우 경고 메시지 표시
        st.warning("면접 세션이 초기화되지 않았습니다. 먼저 질문을 생성하세요.")

    # 모든 면접 질문에 답 했을 때 컨테이너 표시
    if st.session_state.conversation_history:
        interview_workflow.display_conversation_history(
            st.session_state.interview_session
        )
        all_conversation = evaluate_workflow.convert_conversation_to_xml(
            st.session_state.interview_session.interviewer_sessions
        )
        with st.spinner("평가 중..."):
            evaluation = await evaluate_workflow.evaluate_conversation(all_conversation)
            st.expander("종합 평가 결과", expanded=False).markdown(evaluation)


if __name__ == "__main__":
    asyncio.run(main())
