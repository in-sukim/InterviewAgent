import os
import asyncio
from typing import List, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from states import InterviewQuestionSet
from prompts import interviewer_question_message

# OpenAI API 키 설정
openai_api_key = os.getenv("OPENAI_API_KEY")

# LLM 설정
llm = ChatOpenAI(model="gpt-4o")


# 면접관의 질문 생성 함수
async def generate_questions_for_interviewer(
    interviewer: Dict, resume: str
) -> InterviewQuestionSet:
    """Dict 타입의 면접관 정보와 이력서를 입력받아 면접관의 질문 생성
    interviewer: Dict
        name: str
        position_experience: str
        main_tasks: str
        description: str
    resume: str
    """
    # 면접관 페르소나 생성 프롬프트 생성
    system_message = interviewer_question_message.format(
        interviewer_name=interviewer.name,
        interviewer_position_experience=interviewer.position_experience,
        interviewer_main_tasks=interviewer.main_tasks,
        interviewer_description=interviewer.description,
        resume=resume,
    )

    # 구조화된 LLM 설정
    structured_llm = llm.with_structured_output(InterviewQuestionSet)
    interviewer_questions = await structured_llm.ainvoke(
        [SystemMessage(content=system_message)]
        + [
            HumanMessage(
                content="Generate relevant interview questions based on your persona and the candidate's resume."
            )
        ]
    )

    # InterviewQuestionSet에 면접관 이름과 질문 목록을 포함하여 반환
    return InterviewQuestionSet(
        interviewer_name=interviewer.name, questions=interviewer_questions.questions
    )


# 모든 면접관의 질문 생성 함수
async def generate_questions_for_interviewers(
    interviewers: List[Dict], resume: str
) -> Dict:
    """List[Dict] 타입의 면접관 목록과 이력서를 입력받아 모든 면접관의 질문 생성
    interviewers: List[Dict]
        name: str
        position_experience: str
        main_tasks: str
        description: str
    resume: str
    """
    tasks = [
        generate_questions_for_interviewer(interviewer, resume)
        for interviewer in interviewers
    ]
    all_questions = await asyncio.gather(*tasks)
    return {"all_questions": all_questions}
