import os
from dotenv import load_dotenv
import streamlit as st

from langchain_openai import ChatOpenAI
from states import (
    GenerateInterviewerState,
    InterviewerSet,
    Conversation,
    InterviewerSession,
    InterviewSession,
    ConversationStatus,
)
from prompts import interviewer_persona_instructions

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph
from langchain_core.runnables import RunnableConfig

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# 모델 설정
llm = ChatOpenAI(model="gpt-4o")


# 면접관 생성 함수
def create_interviewer(state: GenerateInterviewerState):
    """면접관 페르소나 생성 함수"""
    jd = state["jd"]
    max_interviewer = state["max_interviewer"]
    feedback = state.get("feedback", "")

    # llm 구조화된 출력 형식 적용
    structured_llm = llm.with_structured_output(InterviewerSet)

    # 면접관 페르소나 생성 프롬프트 생성
    system_message = interviewer_persona_instructions.format(
        job_description=jd, user_feedback=feedback, max_interviewer=max_interviewer
    )

    # llm 호출하여 면접관 페르소나 생성
    interviewers = structured_llm.invoke(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content="Generate the interviewers personas.")]
    )
    # 면접관 목록 반환
    return {"interviewers": interviewers.interviewers}


# 사용자 피드백 노드
def user_feedback(state: GenerateInterviewerState):
    """사용자 피드백 노드"""
    pass


def should_continue(state: GenerateInterviewerState):
    """워크플로우의 다음 단계를 결정하는 함수"""
    human_interviewers_feedback = state.get("feedback", None)
    if human_interviewers_feedback:
        return "create_interviewer"
    return END


def create_graph():
    """면접관 생성 워크플로우 그래프 생성"""
    # Pass the class type instead of the instance
    builder = StateGraph(GenerateInterviewerState)

    # 노드 추가
    builder.add_node("create_interviewer", create_interviewer)
    builder.add_node("user_feedback", user_feedback)

    # 엣지 연결
    builder.add_edge(START, "create_interviewer")
    builder.add_edge("create_interviewer", "user_feedback")

    # 조건부 엣지 추가
    builder.add_conditional_edges(
        "user_feedback", should_continue, ["create_interviewer", END]
    )

    # 메모리 생성
    memory = MemorySaver()

    # 그래프 컴파일
    return builder.compile(interrupt_before=["user_feedback"], checkpointer=memory)


def create_interviewer_sessions(interviewers, questions):
    interviewer_sessions = []
    for interviewer in interviewers:
        interviewer_questions = [
            q for q in questions if q.interviewer_name == interviewer.name
        ]
        conversations = [
            Conversation(question_text=question.question, purpose=question.purpose)
            for q in interviewer_questions
            for question in q.questions
        ]
        session = InterviewerSession(
            interviewer=interviewer,
            conversations=conversations,
            status=ConversationStatus.WAITING,
        )
        interviewer_sessions.append(session)
    return InterviewSession(
        interviewer_sessions=interviewer_sessions, status=ConversationStatus.WAITING
    )


def handle_interviewer_creation(job_description, max_interviewer):
    st.session_state.graph = create_graph()
    config = RunnableConfig(
        recursion_limit=10, configurable=st.session_state.config["configurable"]
    )
    inputs = {"jd": job_description, "max_interviewer": max_interviewer}
    st.session_state.graph.invoke(inputs, config)
    st.success("면접관 생성 완료!")
    st.session_state.interviewers = st.session_state.graph.get_state(
        st.session_state.config
    ).values["interviewers"]
