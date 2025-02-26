import os
import re
import streamlit as st

from prompts import evaluate_prompt
from langchain_openai import ChatOpenAI

openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def preprocess_evaluation(evaluation_text):
    """평가 텍스트에서 숫자 앞에 줄 바꿈을 추가합니다.
    evaluation_text: str
    """
    # 정규 표현식을 사용하여 숫자 앞에 줄 바꿈 추가
    return re.sub(r"(?<!\n)(\d+)", r"\n\1", evaluation_text)


def display_conversation_history(session):
    """면접이 종료된 후 대화 내용을 보기 좋게 출력합니다.
    session: InterviewSession
        interviewer_sessions: List[InterviewerSession]
            interviewer: Interviewer
            conversations: List[Conversation]
            status: ConversationStatus
    """
    with st.container(border=True):
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
                    # 평가 텍스트 전처리
                    evaluation_text = (
                        conversation.purpose if conversation.purpose else "평가 없음"
                    )
                    processed_evaluation = preprocess_evaluation(evaluation_text)
                    st.markdown(f"**평가:** {processed_evaluation}")
                    st.markdown("---")  # 구분선 추가


def convert_conversation_to_xml(interviewer_sessions):
    """면접관별 질문, 답변, 평가를 XML 형식으로 변환합니다.
    interviewer_sessions: List[InterviewerSession]
        interviewer: Interviewer
        conversations: List[Conversation]
        status: ConversationStatus
    """
    xml_output = "<InterviewSessions>\n"

    for interviewer_index, interviewer_session in enumerate(
        interviewer_sessions, start=1
    ):
        xml_output += f"  <Interviewer id='{interviewer_index}' name='{interviewer_session.interviewer.name}'>\n"
        for conversation_index, conversation in enumerate(
            interviewer_session.conversations, start=1
        ):
            question_label = (
                "Follow-up" if conversation.purpose == "Follow-up" else "Question"
            )
            xml_output += "    <Conversation>\n"
            xml_output += f"      <Number>{conversation_index}</Number>\n"
            xml_output += f"      <{question_label}>{conversation.question_text}</{question_label}>\n"
            xml_output += f"      <Answer>{conversation.answer if conversation.answer else 'No answer'}</Answer>\n"
            xml_output += f"      <Evaluation>{conversation.purpose if conversation.purpose else 'No evaluation'}</Evaluation>\n"
            xml_output += "    </Conversation>\n"
        xml_output += "  </Interviewer>\n"

    xml_output += "</InterviewSessions>"
    return xml_output


async def evaluate_conversation(conversation):
    """면접 세션을 평가하고 평가 결과를 반환합니다.
    conversation: str
    """
    messages = [
        {"role": "system", "content": evaluate_prompt},
        {"role": "user", "content": conversation},
    ]
    result = await llm.ainvoke(messages)
    return result.content
