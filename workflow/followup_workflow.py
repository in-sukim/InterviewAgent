import os

from states import (
    InterviewSession,
    Conversation,
    InterviewState,
    InterviewerSession,
    FollowupState,
)
from prompts import followup_prompt

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, END, StateGraph


openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=openai_api_key)


def init_interview_session(interviewers, questions):
    """면접 세션을 초기화합니다.
    interviewers: List[Interviewer]
        name: str
        position_experience: str
        main_tasks: str
        description: str

    questions: List[InterviewQuestionSet]
        interviewer_name: str
        questions: List[InterviewQuestion]
    """
    interviewer_sessions = []

    for interviewer in interviewers:
        # questions가 InterviewQuestionSet 객체의 리스트인지 확인
        question_set = next(
            (
                qs
                for qs in questions["all_questions"]
                if qs.interviewer_name == interviewer.name
            ),
            None,
        )
        if question_set:
            conversations = [
                Conversation(question_text=q.question, purpose=q.purpose)
                for q in question_set.questions
            ]
            interviewer_session = InterviewerSession(
                interviewer=interviewer, conversations=conversations
            )
            interviewer_sessions.append(interviewer_session)

    # InterviewSession이 올바른 구조로 초기화되었는지 확인
    if not interviewer_sessions:
        raise ValueError("유효한 면접관 세션을 생성할 수 없습니다.")

    session = InterviewSession(interviewer_sessions=interviewer_sessions)
    return session


def generate_followup_question(
    session: InterviewSession,
    interviewer_idx: int,
    question_idx: int,
    max_question_length: int,
):
    """추가질문 판별 함수
    session: InterviewSession
        interviewer_sessions: List[InterviewerSession]
            interviewer: Interviewer
            conversations: List[Conversation]
            status: ConversationStatus
    interviewer_idx: 현재 면접관 인덱스
    question_idx: 현재 질문 인덱스
    max_question_length: 최대 추가 질문 수
    """
    interviewer = session.interviewer_sessions[interviewer_idx]
    conversation = interviewer.conversations[question_idx]

    if conversation.followup_count >= max_question_length:
        return
    response = invoke_llm_for_followup(interviewer, conversation)

    if response.NEED_FOLLOWUP:
        followup_question = response.FOLLOWUP_QUESTION
        purpose = response.EVALUATION
        followup_conversation = Conversation(
            question_text=followup_question, purpose=purpose
        )
        conversation.insert_after(followup_question, purpose)
        interviewer.add_conversation(followup_conversation, index=question_idx + 1)
        conversation.followup_count += 1
    else:
        evaluation = response.EVALUATION
        conversation.purpose = evaluation


def invoke_llm_for_followup(interviewer, conversation):
    """추가질문 판별 함수
    interviewer: InterviewerSession
        interviewer: Interviewer
        conversations: List[Conversation]
        status: ConversationStatus
    conversation: Conversation
    """
    structured_llm = llm.with_structured_output(FollowupState)
    system_prompt = followup_prompt.format(
        interviewer_name=interviewer.interviewer.name,
        position_experience=interviewer.interviewer.position_experience,
        question=conversation.question_text,
        answer=conversation.answer,
    )

    return structured_llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content="answer analysis and response"),
        ]
    )


# 함수를 처리하도록 process_answer 업데이트
def process_answer(state: InterviewState) -> dict:
    """사용자의 답변을 처리합니다.
    session: InterviewSession
    user_input: Optional[str]
    interviewer_idx: int
    question_idx: int
    max_question_length: int
    config: Dict[str, Any]
    """
    session = state["session"]
    user_input = state["user_input"]
    interviewer_idx = state["interviewer_idx"]
    question_idx = state["question_idx"]
    max_question_length = state["max_question_length"]
    current_session = session.interviewer_sessions[interviewer_idx]
    if current_session and not current_session.is_completed:
        conversation = current_session.conversations[question_idx]
        if conversation:
            conversation.answer = user_input
            generate_followup_question(
                session,
                interviewer_idx,
                question_idx,
                max_question_length,
            )
    return {"session": session}


def should_continue(state: InterviewState) -> dict:
    """워크플로우의 다음 단계를 결정합니다.
    session: InterviewSession
    user_input: Optional[str]
    interviewer_idx: int
    question_idx: int
    max_question_length: int
    config: Dict[str, Any]
    """
    session = state["session"]
    interviewer_idx = state["interviewer_idx"]
    max_question_length = state["max_question_length"]

    conversations = session.interviewer_sessions[interviewer_idx].conversations
    conversation_length = len(conversations)

    if conversation_length >= max_question_length or session.is_completed:
        return {"next_step": END}

    return {"next_step": "process_answer"}


def create_graph() -> StateGraph:
    """면접 워크플로우 그래프를 생성합니다."""
    workflow = StateGraph(InterviewState)

    workflow.add_node("should_continue", should_continue)
    workflow.add_node("process_answer", process_answer)

    workflow.add_edge(START, "should_continue")

    workflow.add_conditional_edges(
        "should_continue",
        lambda state: state["next_step"],  # 반환된 dict에서 "next_step" 키 사용
        {"process_answer": "process_answer", END: END},
    )
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
