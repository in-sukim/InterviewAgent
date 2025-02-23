from langchain_openai import ChatOpenAI
import os
import asyncio
from prompts import evaluate_prompt

openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def convert_conversation_to_xml(interviewer_sessions):
    """면접관별 질문, 답변, 평가를 XML 형식으로 변환합니다."""
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
    """면접 세션을 평가하고 평가 결과를 반환합니다."""
    messages = [
        {"role": "system", "content": evaluate_prompt},
        {"role": "user", "content": conversation},
    ]
    result = await llm.ainvoke(messages)
    return result.content
