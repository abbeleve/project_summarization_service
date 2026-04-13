from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, String, Text, ForeignKey, CheckConstraint, DateTime, func, JSON, text
from sqlalchemy.dialects.postgresql import UUID as UUIDType, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

class Base(DeclarativeBase):
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
        nullable=False
    )

class Staff(Base):
    __tablename__ = 'Staff'
    surname: Mapped[str] = mapped_column(String(25), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    patronymic: Mapped[Optional[str]] = mapped_column(String(25))
    email: Mapped[str] = mapped_column(String(70), unique=True)
    login: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)

    celery_tasks: Mapped[List["CeleryTask"]] = relationship(
        "CeleryTask",
        back_populates="employee",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'surname': self.surname,
            'name': self.name,
            'patronymic': self.patronymic,
            'email': self.email,
            'login': self.login
        }


class Transcript(Base):
    __tablename__ = 'Transcripts'
    employee_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    parts_transcriptions: Mapped[List["PartsTranscription"]] = relationship(
        "PartsTranscription",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )
    summaries: Mapped[List["Summary"]] = relationship(
        "Summary",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )

    chat_messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'employee_id': str(self.employee_id),
            'title': self.title,
            'text': self.text,
            'created_at': self.created_at.isoformat()
        }

class ChatMessage(Base):
    __tablename__ = 'ChatMessages'
    
    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), 
        nullable=False,
        comment="user или assistant"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="chat_messages"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat()
        }

class PartsTranscription(Base):
    __tablename__ = 'PartsTranscription'
    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[int] = mapped_column(nullable=False)
    end_time: Mapped[int] = mapped_column(nullable=False)

    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="parts_transcriptions"
    )
    annotations: Mapped[List["Annotation"]] = relationship(
        "Annotation",
        back_populates="part",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("end_time > start_time"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'text': self.text,
            'start_time': self.start_time,
            'end_time': self.end_time,
        }


class Annotation(Base):
    __tablename__ = 'Annotations'
    part_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('PartsTranscription.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    start_char: Mapped[int] = mapped_column(nullable=False)
    end_char: Mapped[int] = mapped_column(nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    part: Mapped["PartsTranscription"] = relationship(
        "PartsTranscription",
        back_populates="annotations"
    )

    __table_args__ = (
        CheckConstraint("end_char > start_char"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'part_id': str(self.part_id),
            'employee_id': str(self.employee_id),
            'start_char': self.start_char,
            'end_char': self.end_char,
            'color': self.color,
            'note': self.note,
        }


class Summary(Base):
    __tablename__ = 'Summaries'
    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list
    )

    meeting_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="summaries"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'text': self.text,
            'key_points': self.key_points if self.key_points else []
        }


class ScheduledMeeting(Base):
    """
    Модель для хранения запланированных совещаний.
    """
    __tablename__ = 'scheduled_meetings'

    user_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    meeting_url: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="google, microsoft, zoom"
    )
    bot_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="Meeting Notetaker"
    )
    scheduled_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending"  # pending, processing, recording, completed, failed, cancelled
    )
    meeting_bot_task_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID задачи Celery для meeting-bot (join)"
    )
    ml_task_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID задачи Celery для ML пайплайна (транскрибация)"
    )
    recording_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="URL записи из S3/MinIO"
    )
    result_transcript_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        comment="ID созданной транскрипции после обработки"
    )
    # Model preferences for ML pipeline
    transcribe_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="v3_ctc"
    )
    diarization_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        default="pyannote/speaker-diarization-community-1"
    )
    diarize_lib: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="pyannote"
    )
    transcribe_lib: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="gigaam"
    )
    llm_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="gemini-2.5-flash"
    )
    noise_suppression: Mapped[Optional[bool]] = mapped_column(
        nullable=True,
        default=False
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    user: Mapped["Staff"] = relationship(
        "Staff",
        foreign_keys=[user_id]
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'meeting_url': self.meeting_url,
            'provider': self.provider,
            'bot_name': self.bot_name,
            'scheduled_at': self.scheduled_at.isoformat(),
            'status': self.status,
            'meeting_bot_task_id': self.meeting_bot_task_id,
            'recording_url': self.recording_url,
            'result_transcript_id': str(self.result_transcript_id) if self.result_transcript_id else None,
            'transcribe_model': self.transcribe_model,
            'diarization_model': self.diarization_model,
            'diarize_lib': self.diarize_lib,
            'transcribe_lib': self.transcribe_lib,
            'llm_model': self.llm_model,
            'noise_suppression': self.noise_suppression,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class CeleryTask(Base):
    """
    Модель для хранения статуса задач Celery.
    """
    __tablename__ = 'celery_tasks'
    
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='SET NULL'),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"  # pending, processing, completed, failed
    )
    step: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True  # transcription, summarization, db_save, rag_index
    )
    progress: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True  # {"percent": 50, "step": "transcription"}
    )
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True  # {"transcript_id": 123}
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    employee: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        back_populates="celery_tasks"
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'status': self.status,
            'step': self.step,
            'progress': self.progress,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class DataBaseManager:
    def __init__(self, user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"), dbname=os.getenv("DB_NAME")):
        if not all([user, password, host, port, dbname]):
            raise ValueError("Не все параметры подключения к БД предоставлены")

        connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
        self.engine = create_engine(connection_string, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        self.create_tables()

    def create_tables(self):
        try:
            Base.metadata.create_all(self.engine)
            return True
        except SQLAlchemyError as e:
            print(f"Ошибка при создании таблиц: {e}")
            return False

    def drop_all_tables(self):
        try:
            Base.metadata.drop_all(self.engine)
            return True
        except SQLAlchemyError as e:
            print(f"Ошибка при удалении таблиц: {e}")
            return False

    @contextmanager
    def session_scope(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    def insert_staff(self, surname: str, name: str, patronymic: Optional[str],
                     email: str, login: str, password: str) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                hashed_password = self.hash_password(password)
                staff = Staff(
                    surname=surname,
                    name=name,
                    patronymic=patronymic,
                    email=email,
                    login=login,
                    password=hashed_password
                )
                session.add(staff)
                session.flush()
                return staff.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании сотрудника: {e}")
                return None

    def select_staff_by_id(self, staff_id: UUID) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                staff = session.get(Staff, staff_id)
                return staff.to_dict() if staff else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении сотрудника: {e}")
                return None

    def select_staff(self) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                staff_list = session.query(Staff).all()
                return [staff.to_dict() for staff in staff_list]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении списка сотрудников: {e}")
                return []

    def update_staff(self, staff_id: UUID, **kwargs) -> bool:
        with self.session_scope() as session:
            try:
                staff = session.get(Staff, staff_id)
                if not staff:
                    return False

                for key, value in kwargs.items():
                    if hasattr(staff, key) and key not in ['id', 'password']:
                        setattr(staff, key, value)

                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении сотрудника: {e}")
                return False

    def update_staff_password(self, staff_id: UUID, new_password: str) -> bool:
        with self.session_scope() as session:
            try:
                staff = session.get(Staff, staff_id)
                if not staff:
                    return False

                staff.password = self.hash_password(new_password)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении пароля: {e}")
                return False

    def delete_staff(self, staff_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                staff = session.get(Staff, staff_id)
                if not staff:
                    return False

                session.delete(staff)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении сотрудника: {e}")
                return False

    def authentication(self, login: str, password: str) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                staff = session.query(Staff).filter(Staff.login == login).first()
                if staff and self.verify_password(password, staff.password):
                    return staff.id
                return None
            except SQLAlchemyError as e:
                print(f"Ошибка при аутентификации: {e}")
                return None

    def select_staff_by_various_parameters(self, **filters) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                query = session.query(Staff)
                if 'surname' in filters:
                    query = query.filter(Staff.surname.ilike(f"%{filters['surname']}%"))
                if 'name' in filters:
                    query = query.filter(Staff.name.ilike(f"%{filters['name']}%"))
                if 'login' in filters:
                    query = query.filter(Staff.login.ilike(f"%{filters['login']}%"))
                if 'email' in filters:
                    query = query.filter(Staff.email.ilike(f"%{filters['email']}%"))
                staff_list = query.all()
                return [staff.to_dict() for staff in staff_list]
            except SQLAlchemyError as e:
                print(f"Ошибка при поиске сотрудников: {e}")
                return []


    def insert_transcripts(self, text: str, title: Optional[str] = None, employee_id: Optional[UUID] = None) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                # Конвертируем строку в UUID если нужно
                if employee_id and isinstance(employee_id, str):
                    from uuid import UUID
                    employee_id = UUID(employee_id)
                
                transcript = Transcript(
                    title=title,
                    text=text,
                    employee_id=employee_id
                )
                session.add(transcript)
                session.flush()
                return transcript.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании транскрипции: {e}")
                return None

    def select_transcripts_by_id(self, transcript_id: UUID) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                return transcript.to_dict() if transcript else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении транскрипции: {e}")
                return None

    def select_transcripts(self) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                query = session.query(Transcript)
                transcripts = query.all()
                return [t.to_dict() for t in transcripts]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении списка транскрипций: {e}")
                return []

    def update_transcripts(self, transcript_id: UUID, **kwargs) -> bool:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return False

                for key, value in kwargs.items():
                    if hasattr(transcript, key) and key not in ['id']:
                        setattr(transcript, key, value)

                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении транскрипции: {e}")
                return False

    def delete_transcripts(self, transcript_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return False

                session.delete(transcript)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении транскрипции: {e}")
                return False


    def insert_parts_transcription(self, transcript_id: UUID, text: str,
                                  start_time: int, end_time: int) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                part = PartsTranscription(
                    transcript_id=transcript_id,
                    text=text,
                    start_time=start_time,
                    end_time=end_time
                )
                session.add(part)
                session.flush()
                return part.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании части транскрипции: {e}")
                return None

    def select_parts_transcription_by_id(self, part_id: UUID) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                part_transcript = session.get(PartsTranscription, part_id)
                return part_transcript.to_dict() if part_transcript else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции: {e}")
                return None

    def select_parts_transcription(self) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                query = session.query(PartsTranscription)
                parts_transcripts = query.all()
                return [p_t.to_dict() for p_t in parts_transcripts]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции: {e}")
                return []

    def select_parts_transcription_by_transcript_id(self, transcript_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                parts = session.query(PartsTranscription).filter(
                    PartsTranscription.transcript_id == transcript_id
                ).order_by(PartsTranscription.start_time).all()

                return [part.to_dict() for part in parts]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции: {e}")
                return []

    def update_parts_transcription(self, part_id: UUID, **kwargs) -> bool:
        with self.session_scope() as session:
            try:
                part = session.get(PartsTranscription, part_id)
                if not part:
                    return False

                for key, value in kwargs.items():
                    if hasattr(part, key) and key not in ['id']:
                        setattr(part, key, value)

                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении части транскрипции: {e}")
                return False

    def delete_parts_transcription(self, part_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                part = session.get(PartsTranscription, part_id)
                if not part:
                    return False

                session.delete(part)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении части транскрипции: {e}")
                return False


    # ===== Annotations CRUD =====

    def insert_annotation(self, part_id: UUID, employee_id: UUID, 
                         start_char: int, end_char: int,
                         color: Optional[str] = None, 
                         note: Optional[str] = None) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                annotation = Annotation(
                    part_id=part_id,
                    employee_id=employee_id,
                    start_char=start_char,
                    end_char=end_char,
                    color=color,
                    note=note
                )
                session.add(annotation)
                session.flush()
                return annotation.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании аннотации: {e}")
                return None

    def select_annotations_by_part_id(self, part_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                annotations = session.query(Annotation).filter(
                    Annotation.part_id == part_id
                ).all()
                return [ann.to_dict() for ann in annotations]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении аннотаций: {e}")
                return []

    def select_annotations_by_employee_id(self, employee_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                annotations = session.query(Annotation).filter(
                    Annotation.employee_id == employee_id
                ).all()
                return [ann.to_dict() for ann in annotations]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении аннотаций пользователя: {e}")
                return []

    def select_annotations_by_transcript_and_employee(self, transcript_id: UUID, employee_id: UUID) -> List[Dict[str, Any]]:
        """Получить все аннотации пользователя для конкретной транскрипции (один SQL запрос)"""
        with self.session_scope() as session:
            try:
                annotations = (
                    session.query(Annotation)
                    .join(PartsTranscription, Annotation.part_id == PartsTranscription.id)
                    .filter(
                        PartsTranscription.transcript_id == transcript_id,
                        Annotation.employee_id == employee_id
                    )
                    .order_by(PartsTranscription.start_time, Annotation.start_char)
                    .all()
                )
                return [ann.to_dict() for ann in annotations]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении аннотаций транскрипции: {e}")
                return []

    def update_annotation(self, annotation_id: UUID, **kwargs) -> bool:
        with self.session_scope() as session:
            try:
                annotation = session.get(Annotation, annotation_id)
                if not annotation:
                    return False

                for key, value in kwargs.items():
                    if hasattr(annotation, key) and key not in ['id', 'part_id', 'employee_id']:
                        setattr(annotation, key, value)

                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении аннотации: {e}")
                return False

    def delete_annotation(self, annotation_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                annotation = session.get(Annotation, annotation_id)
                if not annotation:
                    return False

                session.delete(annotation)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении аннотации: {e}")
                return False


    def insert_summaries(self,
                        transcript_id: UUID,
                        text: str, 
                        key_points: Optional[List[str]] = None,
                        meeting_type: Optional[str] = None) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                summary = Summary(
                    transcript_id=transcript_id,
                    text=text,
                    key_points=key_points or [],
                    meeting_type=meeting_type
                )
                session.add(summary)
                session.flush()
                return summary.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании резюме: {e}")
                return None

    def select_summaries_by_id(self, summary_id: UUID) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                summary = session.get(Summary, summary_id)
                return summary.to_dict() if summary else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции: {e}")
                return None

    def select_summaries(self) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                query = session.query(Summary)
                summaries = query.all()
                return [s.to_dict() for s in summaries]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции: {e}")
                return []

    def select_summaries_by_transcript_id(self, transcript_id: UUID) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                summary = session.query(Summary).filter(
                    Summary.transcript_id == transcript_id
                ).first()

                if summary:
                    return {
                        'id': str(summary.id),
                        'transcript_id': str(summary.transcript_id),
                        'text': summary.text,
                        'key_points': summary.key_points if summary.key_points else [],
                        'meeting_type': summary.meeting_type
                    }
                return None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении резюме: {e}")
                return None

    def update_summaries(self, summary_id: UUID, transcript_id: UUID, text: str, key_points: Optional[List[str]] = None) -> bool:
        with self.session_scope() as session:
            try:
                summary = session.get(Summary, summary_id)
                if not summary:
                    return False

                summary.transcript_id = transcript_id
                summary.text = text
                if key_points is not None:
                    summary.key_points = key_points
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении резюме: {e}")
                return False

    def delete_summaries(self, summary_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                summary = session.get(Summary, summary_id)
                if not summary:
                    return False

                session.delete(summary)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении резюме: {e}")
                return False
            
    def insert_chat_message(self, transcript_id: UUID, role: str, content: str) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                message = ChatMessage(
                    transcript_id=transcript_id,
                    role=role,
                    content=content
                )
                session.add(message)
                session.flush()
                return message.id
            except SQLAlchemyError as e:
                print(f"Ошибка при сохранении сообщения чата: {e}")
                return None
            
    def select_chat_messages_by_transcript_id(self, transcript_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                messages = session.query(ChatMessage)\
                    .filter(ChatMessage.transcript_id == transcript_id)\
                    .order_by(ChatMessage.created_at)\
                    .all()
                return [msg.to_dict() for msg in messages]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении истории чата: {e}")
                return []

    # === Методы для работы с задачами Celery ===

    def insert_celery_task(
        self,
        task_id: str,
        user_id: UUID,
        status: str = "pending"
    ) -> Optional[str]:
        """
        Создаёт новую задачу Celery в БД.
        
        Args:
            task_id: ID задачи Celery (UUID string)
            user_id: ID пользователя
            status: Начальный статус (pending, processing, completed, failed)
        
        Returns:
            task_id если успешно, None иначе
        """
        from uuid import UUID as UUID_obj
        
        with self.session_scope() as session:
            try:
                # Преобразуем строку task_id в UUID для CeleryTask
                # Celery использует строку, но мы храним как UUID
                celery_task = CeleryTask(
                    id=UUID_obj(task_id),
                    user_id=user_id,
                    status=status,
                    step=None,
                    progress=None,
                    result=None,
                    error=None
                )
                session.add(celery_task)
                session.flush()
                return task_id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании задачи Celery: {e}")
                return None

    def update_celery_task_status(
        self,
        task_id: str,
        status: str,
        progress: Dict[str, Any] = None
    ) -> bool:
        """
        Обновляет статус задачи Celery.
        
        Args:
            task_id: ID задачи Celery
            status: Новый статус
            progress: Прогресс выполнения {"step": "...", "percent": 50}
        
        Returns:
            True если успешно, False иначе
        """
        from uuid import UUID as UUID_obj
        
        with self.session_scope() as session:
            try:
                task = session.get(CeleryTask, UUID_obj(task_id))
                if not task:
                    return False

                task.status = status
                if progress:
                    task.step = progress.get("step")
                    # Сериализуем прогресс для JSONB (конвертируем UUID в строки)
                    task.progress = self._serialize_for_json(progress)

                if status == "completed":
                    # Сериализуем результат для JSONB
                    task.result = self._serialize_for_json(progress)
                elif status == "failed":
                    task.error = progress.get("error") if progress else None

                session.flush()
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении задачи Celery: {e}")
                return False

    @staticmethod
    def _serialize_for_json(obj: Any) -> Any:
        """Конвертирует UUID и другие не-JSON сериализуемые объекты в строки."""
        from uuid import UUID
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: DataBaseManager._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DataBaseManager._serialize_for_json(item) for item in obj]
        return obj

    def get_celery_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о задаче Celery.
        
        Args:
            task_id: ID задачи Celery
        
        Returns:
            Словарь с информацией о задаче или None
        """
        from uuid import UUID as UUID_obj
        
        with self.session_scope() as session:
            try:
                task = session.get(CeleryTask, UUID_obj(task_id))
                if task:
                    return task.to_dict()
                return None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении задачи Celery: {e}")
                return None

    def get_user_celery_tasks(self, user_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получает список задач Celery пользователя.

        Args:
            user_id: ID пользователя
            limit: Максимальное количество задач

        Returns:
            Список задач
        """
        with self.session_scope() as session:
            try:
                tasks = session.query(CeleryTask)\
                    .filter(CeleryTask.user_id == user_id)\
                    .order_by(CeleryTask.created_at.desc())\
                    .limit(limit)\
                    .all()
                return [task.to_dict() for task in tasks]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении задач Celery: {e}")
                return []

    # === Методы для работы с запланированными совещаниями ===

    def insert_scheduled_meeting(
        self,
        user_id: UUID,
        meeting_url: str,
        provider: str,
        scheduled_at: datetime,
        bot_name: Optional[str] = "Meeting Notetaker",
        transcribe_model: Optional[str] = "v3_ctc",
        diarization_model: Optional[str] = "pyannote/speaker-diarization-community-1",
        diarize_lib: Optional[str] = "pyannote",
        transcribe_lib: Optional[str] = "gigaam",
        llm_model: Optional[str] = "gemini-2.5-flash",
        noise_suppression: Optional[bool] = False
    ) -> Optional[UUID]:
        """
        Создаёт новую запись запланированного совещания.

        Args:
            user_id: ID пользователя
            meeting_url: Ссылка на совещание
            provider: Платформа (google, microsoft, zoom)
            scheduled_at: Время начала
            bot_name: Имя бота
            transcribe_model: Модель транскрибации
            diarization_model: Модель диаризации
            diarize_lib: Библиотека диаризации
            transcribe_lib: Библиотека транскрибации
            llm_model: Модель LLM для суммаризации
            noise_suppression: Использовать шумоподавление

        Returns:
            ID созданной записи или None
        """
        with self.session_scope() as session:
            try:
                scheduled = ScheduledMeeting(
                    user_id=user_id,
                    meeting_url=meeting_url,
                    provider=provider,
                    scheduled_at=scheduled_at,
                    bot_name=bot_name,
                    status="pending",
                    transcribe_model=transcribe_model,
                    diarization_model=diarization_model,
                    diarize_lib=diarize_lib,
                    transcribe_lib=transcribe_lib,
                    llm_model=llm_model,
                    noise_suppression=noise_suppression
                )
                session.add(scheduled)
                session.flush()
                return scheduled.id
            except SQLAlchemyError as e:
                print(f"Ошибка при создании запланированного совещания: {e}")
                return None

    def select_scheduled_meeting(self, meeting_id: UUID) -> Optional[Dict[str, Any]]:
        """Получить информацию о запланированном совещании."""
        with self.session_scope() as session:
            try:
                meeting = session.get(ScheduledMeeting, meeting_id)
                return meeting.to_dict() if meeting else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении запланированного совещания: {e}")
                return None

    def select_user_scheduled_meetings(self, user_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить список запланированных совещаний пользователя."""
        with self.session_scope() as session:
            try:
                meetings = session.query(ScheduledMeeting)\
                    .filter(ScheduledMeeting.user_id == user_id)\
                    .order_by(ScheduledMeeting.scheduled_at.desc())\
                    .limit(limit)\
                    .all()
                return [m.to_dict() for m in meetings]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении списка запланированных совещаний: {e}")
                return []

    def select_due_scheduled_meetings(self, grace_period_minutes: int = 2) -> List[Dict[str, Any]]:
        """
        Получить все совещания, которые должны начаться в ближайшее время.
        Ищет совещания у которых scheduled_at <= now() + grace_period и status = 'pending'.
        """
        from datetime import timedelta

        with self.session_scope() as session:
            try:
                cutoff_time = datetime.utcnow() + timedelta(minutes=grace_period_minutes)
                meetings = session.query(ScheduledMeeting)\
                    .filter(
                        ScheduledMeeting.status == "pending",
                        ScheduledMeeting.scheduled_at <= cutoff_time
                    )\
                    .order_by(ScheduledMeeting.scheduled_at.asc())\
                    .all()
                return [m.to_dict() for m in meetings]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении due совещаний: {e}")
                return []

    def update_scheduled_meeting(self, meeting_id: UUID, **kwargs) -> bool:
        """
        Обновить запись запланированного совещания.
        Можно обновить: status, meeting_bot_task_id, recording_url, result_transcript_id, error
        """
        with self.session_scope() as session:
            try:
                meeting = session.get(ScheduledMeeting, meeting_id)
                if not meeting:
                    return False

                for key, value in kwargs.items():
                    if hasattr(meeting, key) and key not in ['id', 'user_id', 'meeting_url', 'provider', 'scheduled_at']:
                        setattr(meeting, key, value)

                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении запланированного совещания: {e}")
                return False

    def delete_scheduled_meeting(self, meeting_id: UUID) -> bool:
        """Удалить запись запланированного совещания."""
        with self.session_scope() as session:
            try:
                meeting = session.get(ScheduledMeeting, meeting_id)
                if not meeting:
                    return False
                session.delete(meeting)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении запланированного совещания: {e}")
                return False