from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, String, Text, ForeignKey, CheckConstraint, DateTime, func, JSON, text
from sqlalchemy.dialects.postgresql import UUID as UUIDType, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta, timezone
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

# Шифрование чувствительных данных (API токены и т.п.)
try:
    from cryptography.fernet import Fernet
    _CRYPTO_KEY = os.getenv("CRM_ENCRYPTION_KEY")
    if _CRYPTO_KEY:
        _CIPHER = Fernet(_CRYPTO_KEY.encode() if isinstance(_CRYPTO_KEY, str) else _CRYPTO_KEY)
    else:
        _CIPHER = None
except ImportError:
    _CIPHER = None


def encrypt_token(plain_token: str) -> str:
    """Шифрует API токен. Без ключа возвращает как есть (fallback)."""
    if _CIPHER is None:
        return plain_token
    return _CIPHER.encrypt(plain_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Расшифровывает API токен. Без ключа возвращает как есть."""
    if _CIPHER is None:
        return encrypted_token
    return _CIPHER.decrypt(encrypted_token.encode()).decode()

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
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="user",
        comment="Роль пользователя: user или admin"
    )
    avatar_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Ключ объекта в MinIO (avatars/{user_id})"
    )
    weeek_api_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Зашифрованный API токен Weeek для интеграции CRM"
    )

    celery_tasks: Mapped[List["CeleryTask"]] = relationship(
        "CeleryTask",
        back_populates="employee",
        cascade="all, delete-orphan"
    )
    transcript_accesses: Mapped[List["TranscriptAccess"]] = relationship(
        "TranscriptAccess",
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
            'login': self.login,
            'role': self.role,
            'avatar_key': self.avatar_key,
            # weeek_api_token НЕ включён — never expose via API
        }


class Transcript(Base):
    __tablename__ = 'Transcripts'
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    recording_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="URL аудиофайла в MinIO/S3 для воспроизведения в плеере"
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
    access_list: Mapped[List["TranscriptAccess"]] = relationship(
        "TranscriptAccess",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'title': self.title,
            'text': self.text,
            'created_at': self.created_at.isoformat(),
            'recording_url': self.recording_url
        }

class ChatMessage(Base):
    __tablename__ = 'ChatMessages'

    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
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
            'employee_id': str(self.employee_id),
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.isoformat()
        }


class TranscriptAccess(Base):
    __tablename__ = 'TranscriptAccess'

    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="shared",
        comment="owner, shared"
    )
    granted_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="access_list"
    )
    employee: Mapped["Staff"] = relationship(
        "Staff",
        back_populates="transcript_accesses"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'employee_id': str(self.employee_id),
            'role': self.role,
            'granted_at': self.granted_at.isoformat()
        }

class PartsTranscription(Base):
    __tablename__ = 'PartsTranscription'
    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    employee_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment="Идентифицированный спикер (Staff ID)"
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
            'employee_id': str(self.employee_id) if self.employee_id else None,
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
    meeting_tasks: Mapped[List["MeetingTask"]] = relationship(
        "MeetingTask",
        back_populates="summary",
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'text': self.text,
            'key_points': self.key_points if self.key_points else [],
        }


class MeetingTask(Base):
    """
    Индивидуальная задача (action item) из совещания.
    Каждая задача имеет свой статус отправки в CRM.
    """
    __tablename__ = 'MeetingTasks'

    summary_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Summaries.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assignee: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Ответственный (может быть отредактирован пользователем)"
    )
    deadline: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Дедлайн (может быть отредактирован пользователем)"
    )
    sent_to_crm: Mapped[bool] = mapped_column(
        nullable=False, default=False,
        comment="Отправлено ли в CRM"
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время отправки в CRM"
    )
    crm_task_id: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="ID задачи в Weeek (ответ от CRM)"
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    summary: Mapped["Summary"] = relationship(
        "Summary",
        back_populates="meeting_tasks"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'summary_id': str(self.summary_id),
            'description': self.description,
            'assignee': self.assignee,
            'deadline': self.deadline,
            'sent_to_crm': self.sent_to_crm,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'crm_task_id': self.crm_task_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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
    title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Название совещания, задаётся пользователем"
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
        default="v3_e2e_rnnt"
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
        default="deepseek/deepseek-v4-flash"
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
            'title': self.title,
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


class ProcessingMetrics(Base):
    """
    Модель для хранения метрик обработки аудиофайлов (аналитика).

    Собирается после каждого вызова ASR (whisper или gigaam)
    для последующей агрегации в админ-панели.
    """
    __tablename__ = 'ProcessingMetrics'

    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="ID транскрипции"
    )
    user_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="ID пользователя, запустившего обработку"
    )
    audio_duration_sec: Mapped[float] = mapped_column(
        nullable=False,
        comment="Длительность аудиофайла в секундах"
    )
    transcribe_lib: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="whisper или gigaam"
    )
    transcribe_model: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Модель ASR, например v3_e2e_rnnt, base, large-v3"
    )
    processing_duration_ms: Mapped[int] = mapped_column(
        nullable=False,
        comment="Время выполнения ASR в миллисекундах (ntp-скорректированное)"
    )
    diarize_lib: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Библиотека диаризации, например pyannote"
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Размер аудиофайла в байтах"
    )
    noise_suppression: Mapped[Optional[bool]] = mapped_column(
        nullable=True,
        comment="Было ли применено шумоподавление"
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Время создания записи метрики"
    )

    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        foreign_keys=[transcript_id]
    )
    user: Mapped["Staff"] = relationship(
        "Staff",
        foreign_keys=[user_id]
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'transcript_id': str(self.transcript_id),
            'user_id': str(self.user_id),
            'audio_duration_sec': self.audio_duration_sec,
            'transcribe_lib': self.transcribe_lib,
            'transcribe_model': self.transcribe_model,
            'processing_duration_ms': self.processing_duration_ms,
            'diarize_lib': self.diarize_lib,
            'file_size_bytes': self.file_size_bytes,
            'noise_suppression': self.noise_suppression,
            'created_at': self.created_at.isoformat()
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
                     email: str, login: str, password: str,
                     role: str = "user") -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                hashed_password = self.hash_password(password)
                staff = Staff(
                    surname=surname,
                    name=name,
                    patronymic=patronymic,
                    email=email,
                    login=login,
                    password=hashed_password,
                    role=role
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
                    text=text
                )
                session.add(transcript)
                session.flush()
                
                # Теперь создаем запись о владении в TranscriptAccess
                if employee_id:
                    access = TranscriptAccess(
                        transcript_id=transcript.id,
                        employee_id=employee_id,
                        role="owner"
                    )
                    session.add(access)
                
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

    def insert_transcript_access(self, transcript_id: UUID, employee_id: UUID, role: str = "shared") -> bool:
        with self.session_scope() as session:
            try:
                # Проверяем, нет ли уже такого доступа
                exists = session.query(TranscriptAccess).filter(
                    TranscriptAccess.transcript_id == transcript_id,
                    TranscriptAccess.employee_id == employee_id
                ).first()
                if exists:
                    # Если доступ уже есть, обновляем роль (например, с shared на owner, если нужно)
                    exists.role = role
                    return True

                access = TranscriptAccess(
                    transcript_id=transcript_id,
                    employee_id=employee_id,
                    role=role
                )
                session.add(access)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при предоставлении доступа к транскрипции: {e}")
                return False

    def check_transcript_access(self, transcript_id: UUID, employee_id: UUID, required_role: Optional[str] = None) -> bool:
        with self.session_scope() as session:
            try:
                access = session.query(TranscriptAccess).filter(
                    TranscriptAccess.transcript_id == transcript_id,
                    TranscriptAccess.employee_id == employee_id
                ).first()
                
                if not access:
                    return False
                
                if required_role:
                    return access.role == required_role or access.role == "owner"
                
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при проверке доступа: {e}")
                return False

    def select_transcripts_for_employee(self, employee_id: UUID, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                # Получаем все транскрипции, к которым пользователь имеет любой доступ
                query = session.query(Transcript).join(
                    TranscriptAccess, Transcript.id == TranscriptAccess.transcript_id
                ).filter(
                    TranscriptAccess.employee_id == employee_id
                )

                if start_date:
                    query = query.filter(Transcript.created_at >= start_date)
                if end_date:
                    query = query.filter(Transcript.created_at <= end_date)

                query = query.order_by(Transcript.created_at.desc())

                transcripts = query.all()

                return [t.to_dict() for t in transcripts]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении списка доступных транскрипций: {e}")
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

    def remove_transcript_access(self, transcript_id: UUID, employee_id: UUID) -> bool:
        with self.session_scope() as session:
            try:
                access = session.query(TranscriptAccess).filter(
                    TranscriptAccess.transcript_id == transcript_id,
                    TranscriptAccess.employee_id == employee_id
                ).first()
                if not access:
                    return False

                session.delete(access)
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при удалении доступа к транскрипции: {e}")
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
                    meeting_type=meeting_type,
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
                        'meeting_type': summary.meeting_type,
                    }
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

    # ===== MeetingTask (задачи для CRM) =====

    def bulk_insert_meeting_tasks(
        self,
        summary_id: UUID,
        tasks_data: List[Dict[str, str]],
    ) -> int:
        """
        Массовая вставка задач в MeetingTasks.

        Args:
            summary_id: ID суммаризации
            tasks_data: список {description, assignee, deadline}

        Returns:
            Количество вставленных задач
        """
        count = 0
        with self.session_scope() as session:
            try:
                summary = session.get(Summary, summary_id)
                if not summary:
                    return 0

                for task in tasks_data:
                    mt = MeetingTask(
                        summary_id=summary_id,
                        description=task.get("description", ""),
                        assignee=task.get("assignee", ""),
                        deadline=task.get("deadline", ""),
                    )
                    session.add(mt)
                    count += 1

                session.flush()
                return count
            except SQLAlchemyError as e:
                print(f"Ошибка при массовой вставке задач: {e}")
                return 0

    def select_meeting_tasks_by_summary_id(
        self, summary_id: UUID
    ) -> List[Dict[str, Any]]:
        """Возвращает список задач для суммаризации."""
        with self.session_scope() as session:
            try:
                tasks = (
                    session.query(MeetingTask)
                    .filter(MeetingTask.summary_id == summary_id)
                    .order_by(MeetingTask.created_at)
                    .all()
                )
                return [t.to_dict() for t in tasks]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении задач: {e}")
                return []

    def select_meeting_task_by_id(self, task_id: UUID) -> Optional[Dict[str, Any]]:
        """Возвращает задачу по ID."""
        with self.session_scope() as session:
            try:
                task = session.get(MeetingTask, task_id)
                return task.to_dict() if task else None
            except SQLAlchemyError as e:
                print(f"Ошибка при получении задачи: {e}")
                return None

    def update_meeting_task(
        self,
        task_id: UUID,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        deadline: Optional[str] = None,
    ) -> bool:
        """Обновляет поля задачи (без отправки в CRM)."""
        with self.session_scope() as session:
            try:
                task = session.get(MeetingTask, task_id)
                if not task:
                    return False
                if description is not None:
                    task.description = description
                if assignee is not None:
                    task.assignee = assignee
                if deadline is not None:
                    task.deadline = deadline
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при обновлении задачи: {e}")
                return False

    def mark_meeting_task_sent(
        self,
        task_id: UUID,
        crm_task_id: Optional[str] = None,
    ) -> bool:
        """Помечает задачу как отправленную в CRM."""
        with self.session_scope() as session:
            try:
                task = session.get(MeetingTask, task_id)
                if not task:
                    return False
                if task.sent_to_crm:
                    return True  # уже отправлено
                task.sent_to_crm = True
                task.sent_at = datetime.now(timezone.utc)
                if crm_task_id is not None:
                    task.crm_task_id = crm_task_id
                return True
            except SQLAlchemyError as e:
                print(f"Ошибка при отметке задачи отправленной: {e}")
                return False

    def select_unsent_meeting_tasks(
        self, summary_id: UUID
    ) -> List[Dict[str, Any]]:
        """Возвращает неотправленные задачи для суммаризации."""
        with self.session_scope() as session:
            try:
                tasks = (
                    session.query(MeetingTask)
                    .filter(
                        MeetingTask.summary_id == summary_id,
                        MeetingTask.sent_to_crm == False,
                    )
                    .order_by(MeetingTask.created_at)
                    .all()
                )
                return [t.to_dict() for t in tasks]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении неотправленных задач: {e}")
                return []

    def insert_chat_message(self, transcript_id: UUID, employee_id: UUID, role: str, content: str) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                message = ChatMessage(
                    transcript_id=transcript_id,
                    employee_id=employee_id,
                    role=role,
                    content=content
                )
                session.add(message)
                session.flush()
                return message.id
            except SQLAlchemyError as e:
                print(f"Ошибка при сохранении сообщения чата: {e}")
                return None

    def select_chat_messages_by_transcript_id(self, transcript_id: UUID, employee_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                messages = session.query(ChatMessage)\
                    .filter(
                        ChatMessage.transcript_id == transcript_id,
                        ChatMessage.employee_id == employee_id
                    )\
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
        title: Optional[str] = None,
        bot_name: Optional[str] = "Meeting Notetaker",
        transcribe_model: Optional[str] = "v3_e2e_rnnt",
        diarization_model: Optional[str] = "pyannote/speaker-diarization-community-1",
        diarize_lib: Optional[str] = "pyannote",
        transcribe_lib: Optional[str] = "gigaam",
        llm_model: Optional[str] = "deepseek/deepseek-v4-flash",
        noise_suppression: Optional[bool] = False
    ) -> Optional[UUID]:
        """
        Создаёт новую запись запланированного совещания.

        Args:
            user_id: ID пользователя
            meeting_url: Ссылка на совещание
            provider: Платформа (google, microsoft, zoom)
            scheduled_at: Время начала
            title: Название совещания
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
                    title=title,
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

    # ── Processing Metrics ──────────────────────────────────────────

    def insert_processing_metrics(
        self,
        transcript_id: UUID,
        user_id: UUID,
        audio_duration_sec: float,
        transcribe_lib: str,
        processing_duration_ms: int,
        transcribe_model: Optional[str] = None,
        diarize_lib: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        noise_suppression: Optional[bool] = None,
    ) -> Optional[UUID]:
        """Сохранить метрики обработки аудиофайла."""
        with self.session_scope() as session:
            try:
                metric = ProcessingMetrics(
                    transcript_id=transcript_id,
                    user_id=user_id,
                    audio_duration_sec=audio_duration_sec,
                    transcribe_lib=transcribe_lib,
                    transcribe_model=transcribe_model,
                    processing_duration_ms=processing_duration_ms,
                    diarize_lib=diarize_lib,
                    file_size_bytes=file_size_bytes,
                    noise_suppression=noise_suppression,
                )
                session.add(metric)
                session.flush()
                return metric.id
            except SQLAlchemyError as e:
                print(f"Ошибка при сохранении метрик обработки: {e}")
                return None

    def get_analytics(self) -> Dict[str, Any]:
        """
        Агрегированные данные для админ-панели (аналитика).

        Возвращает:
          - user_activity: общая/активная статистика по пользователям и транскриптам
          - asr_performance: среднее время обработки на час аудио (whisper / gigaam)
          - daily_breakdown: статистика по дням (за последние 30 дней)
        """
        with self.session_scope() as session:
            try:
                session.execute(text("SET TIME ZONE 'Asia/Irkutsk'"))
                now = func.now()

                # ── User activity ──
                total_users = session.query(func.count(Staff.id)).scalar() or 0

                # Активные пользователи (создавшие хотя бы один транскрипт за период)
                def active_users_since(days: int) -> int:
                    cutoff = func.now() - text(f"INTERVAL '{days} days'")
                    return (
                        session.query(func.count(func.distinct(TranscriptAccess.employee_id)))
                        .join(Transcript, TranscriptAccess.transcript_id == Transcript.id)
                        .filter(Transcript.created_at >= cutoff)
                        .scalar()
                    ) or 0

                active_users_7d = active_users_since(7)
                active_users_30d = active_users_since(30)

                total_transcripts = session.query(func.count(Transcript.id)).scalar() or 0

                def transcripts_since(days: int) -> int:
                    cutoff = func.now() - text(f"INTERVAL '{days} days'")
                    return (
                        session.query(func.count(Transcript.id))
                        .filter(Transcript.created_at >= cutoff)
                        .scalar()
                    ) or 0

                transcripts_7d = transcripts_since(7)
                transcripts_30d = transcripts_since(30)

                # ── ASR performance (per model) ──
                def asr_stats(lib: str) -> Dict[str, Any]:
                    rows = (
                        session.query(
                            ProcessingMetrics.processing_duration_ms,
                            ProcessingMetrics.audio_duration_sec,
                        )
                        .filter(ProcessingMetrics.transcribe_lib == lib)
                        .all()
                    )
                    count = len(rows)
                    total_audio_sec = sum(r.audio_duration_sec for r in rows)
                    total_audio_hours = total_audio_sec / 3600.0 if total_audio_sec else 0.0
                    # Per-file: processing_duration_ms / (audio_duration_sec / 3600)
                    # = сколько мс заняла обработка часа этого файла
                    normalized = [
                        r.processing_duration_ms / (r.audio_duration_sec / 3600.0)
                        for r in rows if r.audio_duration_sec > 0
                    ]
                    avg_per_hour_ms = sum(normalized) / len(normalized) if normalized else 0.0
                    return {
                        "total_processed": count,
                        "total_audio_hours": round(total_audio_hours, 2),
                        "avg_processing_time_per_hour_ms": round(avg_per_hour_ms, 2),
                    }

                whisper_stats = asr_stats("whisper")
                gigaam_stats = asr_stats("gigaam")

                # ── Daily breakdown (last 30 days) ──
                cutoff_30d = func.now() - text("INTERVAL '30 days'")
                daily_rows = (
                    session.query(
                        func.date(Transcript.created_at).label("date"),
                        func.count(func.distinct(TranscriptAccess.employee_id)).label("active_users"),
                        func.count(Transcript.id).label("transcripts"),
                    )
                    .outerjoin(TranscriptAccess, TranscriptAccess.transcript_id == Transcript.id)
                    .filter(Transcript.created_at >= cutoff_30d)
                    .group_by(func.date(Transcript.created_at))
                    .order_by(func.date(Transcript.created_at))
                    .all()
                )

                daily_breakdown = [
                    {
                        "date": str(row.date),
                        "active_users": row.active_users,
                        "transcripts": row.transcripts,
                    }
                    for row in daily_rows
                ]

                # ── Processing breakdowns (hour / day / month) ──
                # Hourly: last 24 hours (padded to always show 24 slots)
                cutoff_24h = func.now() - text("INTERVAL '24 hours'")
                hourly_rows = (
                    session.query(
                        func.date_trunc('hour', ProcessingMetrics.created_at).label("bucket"),
                        func.count(ProcessingMetrics.id).label("processing_count"),
                    )
                    .filter(ProcessingMetrics.created_at >= cutoff_24h)
                    .group_by(func.date_trunc('hour', ProcessingMetrics.created_at))
                    .order_by(func.date_trunc('hour', ProcessingMetrics.created_at))
                    .all()
                )
                _hour_map = {}
                for row in hourly_rows:
                    key = row.bucket.strftime("%Y-%m-%d %H:00") if hasattr(row.bucket, 'strftime') else str(row.bucket)
                    _hour_map[key] = row.processing_count
                # Pad to 24 hours
                _tz_irkt = timezone(timedelta(hours=8))
                _now_irkt = datetime.now(_tz_irkt).replace(minute=0, second=0, microsecond=0)
                hourly_processing = []
                for _i in range(23, -1, -1):  # oldest first
                    _slot = _now_irkt - timedelta(hours=_i)
                    _key = _slot.strftime("%Y-%m-%d %H:00")
                    hourly_processing.append({"hour": _key, "count": _hour_map.get(_key, 0)})

                # Daily (ProcessingMetrics): last 30 days
                daily_processing_rows = (
                    session.query(
                        func.date(ProcessingMetrics.created_at).label("date"),
                        func.count(ProcessingMetrics.id).label("processing_count"),
                    )
                    .filter(ProcessingMetrics.created_at >= cutoff_30d)
                    .group_by(func.date(ProcessingMetrics.created_at))
                    .order_by(func.date(ProcessingMetrics.created_at))
                    .all()
                )
                _day_map = {str(r.date): r.processing_count for r in daily_processing_rows}
                daily_processing = []
                for _i in range(29, -1, -1):  # oldest first
                    _slot = (_now_irkt - timedelta(days=_i)).strftime("%Y-%m-%d")
                    daily_processing.append({"date": _slot, "count": _day_map.get(_slot, 0)})

                # Monthly: last 12 months
                cutoff_12m = func.now() - text("INTERVAL '12 months'")
                monthly_rows = (
                    session.query(
                        func.date_trunc('month', ProcessingMetrics.created_at).label("bucket"),
                        func.count(ProcessingMetrics.id).label("processing_count"),
                    )
                    .filter(ProcessingMetrics.created_at >= cutoff_12m)
                    .group_by(func.date_trunc('month', ProcessingMetrics.created_at))
                    .order_by(func.date_trunc('month', ProcessingMetrics.created_at))
                    .all()
                )
                monthly_processing = [
                    {"month": row.bucket.strftime("%Y-%m") if hasattr(row.bucket, 'strftime') else str(row.bucket), "count": row.processing_count}
                    for row in monthly_rows
                ]

                # ── Weekly: last 12 weeks (3 months) ──
                cutoff_3m = func.now() - text("INTERVAL '3 months'")
                weekly_rows = (
                    session.query(
                        func.date_trunc('week', ProcessingMetrics.created_at).label("bucket"),
                        func.count(ProcessingMetrics.id).label("processing_count"),
                    )
                    .filter(ProcessingMetrics.created_at >= cutoff_3m)
                    .group_by(func.date_trunc('week', ProcessingMetrics.created_at))
                    .order_by(func.date_trunc('week', ProcessingMetrics.created_at))
                    .all()
                )
                weekly_processing = [
                    {"week": row.bucket.strftime("%Y-%m-%d") if hasattr(row.bucket, 'strftime') else str(row.bucket), "count": row.processing_count}
                    for row in weekly_rows
                ]

                # ── Hourly load (0-23, last 7 days) ──
                cutoff_7d = func.now() - text("INTERVAL '7 days'")
                load_rows = (
                    session.query(
                        func.extract('hour', ProcessingMetrics.created_at).label("hour"),
                        func.count(ProcessingMetrics.id).label("count"),
                        func.coalesce(func.avg(ProcessingMetrics.processing_duration_ms), 0).label("avg_ms"),
                    )
                    .filter(ProcessingMetrics.created_at >= cutoff_7d)
                    .group_by(func.extract('hour', ProcessingMetrics.created_at))
                    .order_by(func.extract('hour', ProcessingMetrics.created_at))
                    .all()
                )
                load_by_hour = {int(r.hour): {"count": r.count, "avg_ms": round(float(r.avg_ms))} for r in load_rows}
                hourly_load = [
                    {
                        "hour": f"{h:02d}:00",
                        "count": load_by_hour.get(h, {}).get("count", 0),
                        "avg_ms": load_by_hour.get(h, {}).get("avg_ms", 0),
                    }
                    for h in range(24)
                ]

                return {
                    "user_activity": {
                        "total_users": total_users,
                        "active_users_7d": active_users_7d,
                        "active_users_30d": active_users_30d,
                        "total_transcripts": total_transcripts,
                        "transcripts_7d": transcripts_7d,
                        "transcripts_30d": transcripts_30d,
                    },
                    "asr_performance": {
                        "whisper": whisper_stats,
                        "gigaam": gigaam_stats,
                    },
                    "daily_breakdown": daily_breakdown,
                    "hourly_processing": hourly_processing,
                    "daily_processing": daily_processing,
                    "weekly_processing": weekly_processing,
                    "monthly_processing": monthly_processing,
                    "hourly_load": hourly_load,
                }
            except SQLAlchemyError as e:
                print(f"Ошибка при получении аналитики: {e}")
                return {
                    "user_activity": {},
                    "asr_performance": {},
                    "daily_breakdown": [],
                    "hourly_processing": [],
                    "daily_processing": [],
                    "weekly_processing": [],
                    "monthly_processing": [],
                    "hourly_load": [],
                }