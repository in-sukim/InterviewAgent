from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Optional, Dict, Any
from typing_extensions import TypedDict


# 면접관 정보
class Interviewer(BaseModel):
    """면접관 정보 클래스"""

    # 소속 정보
    affiliation: str = Field(description="Primary affiliation of the interviewee")
    # 이름
    name: str = Field(description="Name of the interviewee")
    # 직책
    position_experience: str = Field(
        description="Position and experience of the interviewee"
    )
    # 주요 업무
    main_tasks: str = Field(description="Main tasks of the interviewee")
    # 중점, 우려 사항 및 동기에 대한 설명
    description: str = Field(
        description="Description of the interviewee's focus, concerns, and motivations"
    )

    # 면접관 인적 정보 문자열로 반환하는 속성
    @property
    def persona(self) -> str:
        return f"Name: {self.name}, Position: {self.position_experience}, Affiliation: {self.affiliation}, Main Tasks: {self.main_tasks}, Description: {self.description}"


# 면접관 집합
class InterviewerSet(BaseModel):
    """면접관 집합 클래스"""

    # 면접관 목록
    interviewers: List[Interviewer] = Field(
        description="Comprehensive list of interviewers"
    )


# 면접관 생성 상태
class GenerateInterviewerState(TypedDict):
    """면접관 생성 상태 클래스"""

    # JD(Job Description)
    jd: str
    # 최대 면접관 수
    max_interviewer: int
    # 사용자 피드백
    feedback: str
    # 면접관 목록
    interviewers: List[Interviewer]
    # 이력서
    resume: str


# 면접 질문 클래스
class InterviewQuestion(BaseModel):
    question: str = Field(description="The question being asked to the interviewee")
    purpose: str = Field(description="The purpose of the question")


# 면접 질문 집합
class InterviewQuestionSet(BaseModel):
    """면접 질문 집합 클래스"""

    # 면접관 이름
    interviewer_name: str = Field(
        description="Name of the Interviewer asking the question"
    )
    # 면접 질문 목록
    questions: List[InterviewQuestion] = Field(
        description="A list of interview questions from all interviewers"
    )


# 면접 질문 생성 상태
class GenerateQuestionsState(TypedDict):
    """면접 질문 생성 상태 클래스"""

    interviewers: List[Interviewer]
    resume: str
    interview_questions: Optional[List[InterviewQuestionSet]]


# 대화 상태 Enum
class ConversationStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# 단일 대화(질문-답변) 관리
class Conversation(BaseModel):
    question_text: str = Field(
        description="The question being asked to the interviewee"
    )
    purpose: str = Field(description="The purpose of the question")
    answer: Optional[str] = None
    next_conversation: Optional["Conversation"] = None
    followup_count: int = 0  # Track the number of follow-up questions

    def insert_after(self, new_question_text: str, new_purpose: str):
        """Insert a new question after the current one."""
        new_conversation = Conversation(
            question_text=new_question_text, purpose=new_purpose
        )
        new_conversation.next_conversation = self.next_conversation
        self.next_conversation = new_conversation

    def delete_next(self):
        """Delete the next conversation node."""
        if self.next_conversation:
            self.next_conversation = self.next_conversation.next_conversation

    def has_cycle(self) -> bool:
        """Check if there is a cycle in the linked list."""
        slow = self
        fast = self.next_conversation
        while fast and fast.next_conversation:
            if slow == fast:
                return True
            slow = slow.next_conversation
            fast = fast.next_conversation.next_conversation
        return False


# 면접관별 대화 세션
class InterviewerSession(BaseModel):
    interviewer: Interviewer
    conversations: List[Conversation] = []
    status: ConversationStatus = ConversationStatus.WAITING
    current_conversation: Optional[Conversation] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.conversations:
            # Initialize the linked list structure
            for i in range(len(self.conversations) - 1):
                self.conversations[i].next_conversation = self.conversations[i + 1]
            self.current_conversation = self.conversations[
                0
            ]  # Set the first conversation as current

    @property
    def is_completed(self) -> bool:
        return self.status == ConversationStatus.COMPLETED

    def advance_to_next_question(self):
        if self.current_conversation and self.current_conversation.next_conversation:
            self.current_conversation = self.current_conversation.next_conversation
        else:
            self.status = ConversationStatus.COMPLETED

    def check_for_cycles(self) -> bool:
        """Check if any conversation in the session has a cycle."""
        for conversation in self.conversations:
            if conversation.has_cycle():
                return True
        return False

    def add_conversation(self, conversation: Conversation, index: Optional[int] = None):
        """Add a new conversation to the session at a specific index."""
        if index is None or index >= len(self.conversations):
            # 기본적으로 리스트의 끝에 추가
            if not self.conversations:
                self.conversations.append(conversation)
                self.current_conversation = conversation
            else:
                self.conversations[-1].next_conversation = conversation
                self.conversations.append(conversation)
        else:
            # 특정 인덱스에 삽입
            self.conversations.insert(index, conversation)
            if index > 0:
                self.conversations[index - 1].next_conversation = conversation
            conversation.next_conversation = (
                self.conversations[index + 1]
                if index + 1 < len(self.conversations)
                else None
            )


# 전체 면접 세션
class InterviewSession(BaseModel):
    interviewer_sessions: List[InterviewerSession]
    current_interviewer_idx: int = 0
    status: ConversationStatus = ConversationStatus.WAITING

    @property
    def current_session(self) -> Optional[InterviewerSession]:
        if 0 <= self.current_interviewer_idx < len(self.interviewer_sessions):
            return self.interviewer_sessions[self.current_interviewer_idx]
        return None

    @property
    def is_completed(self) -> bool:
        return all(session.is_completed for session in self.interviewer_sessions)


# 면접 상태 관리
class InterviewState(TypedDict):
    session: InterviewSession
    user_input: Optional[str]
    interviewer_idx: int
    question_idx: int
    max_question_length: int
    config: Dict[str, Any]
