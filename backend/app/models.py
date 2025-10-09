from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


attempt_mistake_tags = Table(
    "attempt_mistake_tags",
    Base.metadata,
    Column("attempt_id", ForeignKey("attempts.id"), primary_key=True),
    Column("mistake_tag_id", ForeignKey("mistake_tags.id"), primary_key=True),
)


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=False)

    attempts = relationship("Attempt", back_populates="student")


class Subtopic(Base):
    __tablename__ = "subtopics"

    id = Column(Integer, primary_key=True, autoincrement=False)
    subject_id = Column(Integer, nullable=False)
    subject_name = Column(String, nullable=False)
    topic_name = Column(String, nullable=False)
    name = Column(String, nullable=False)

    questions = relationship("Question", back_populates="subtopic")
    attempts = relationship("Attempt", back_populates="subtopic")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=False)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    text = Column(Text)
    image_url = Column(String)

    subtopic = relationship("Subtopic", back_populates="questions")
    attempts = relationship("Attempt", back_populates="question")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    subtopic_id = Column(Integer, ForeignKey("subtopics.id"), nullable=False)
    answer_text = Column(Text)
    mark = Column(Float, nullable=False, default=0)
    mark_awarded = Column(Float, nullable=False, default=0)
    student_score = Column(Float, nullable=True)

    student = relationship("Student", back_populates="attempts")
    question = relationship("Question", back_populates="attempts")
    subtopic = relationship("Subtopic", back_populates="attempts")
    tags = relationship("MistakeTag", secondary=attempt_mistake_tags, back_populates="attempts")


class MistakeTag(Base):
    __tablename__ = "mistake_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)

    attempts = relationship("Attempt", secondary=attempt_mistake_tags, back_populates="tags")
