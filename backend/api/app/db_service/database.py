from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, String, Text, ForeignKey, CheckConstraint, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import UUID as UUIDType, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
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

    parts_transcriptions: Mapped[List["PartsTranscription"]] = relationship(
        "PartsTranscription",
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
    employee_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Staff.id', ondelete='SET NULL'),
        nullable=True
    )
    transcript_id: Mapped[UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey('Transcripts.id', ondelete='CASCADE'),
        nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[int] = mapped_column(nullable=False)
    end_time: Mapped[int] = mapped_column(nullable=False)

    employee: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        back_populates="parts_transcriptions"
    )
    transcript: Mapped["Transcript"] = relationship(
        "Transcript",
        back_populates="parts_transcriptions"
    )

    __table_args__ = (
        CheckConstraint("end_time > start_time"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': str(self.id),
            'employee_id': str(self.employee_id) if self.employee_id else None,
            'transcript_id': str(self.transcript_id),
            'text': self.text,
            'start_time': self.start_time,
            'end_time': self.end_time,
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


    def insert_transcripts(self, text: str, title: Optional[str] = None) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = Transcript(
                    title=title,
                    text=text
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


    def insert_parts_transcription(self, employee_id: Optional[UUID], transcript_id: UUID, text: str,
                                  start_time: int, end_time: int) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                if employee_id:
                    staff = session.get(Staff, employee_id)
                    if not staff:
                        return None

                part = PartsTranscription(
                    employee_id=employee_id,
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

    def select_parts_transcription_by_employee_id(self, employee_id: UUID) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            try:
                parts = session.query(PartsTranscription).filter(PartsTranscription.employee_id == employee_id).all()
                return [part.to_dict() for part in parts]
            except SQLAlchemyError as e:
                print(f"Ошибка при получении частей транскрипции сотрудника: {e}")
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


    def insert_summaries(self, transcript_id: UUID, text: str, key_points: Optional[List[str]] = None) -> Optional[UUID]:
        with self.session_scope() as session:
            try:
                transcript = session.get(Transcript, transcript_id)
                if not transcript:
                    return None

                summary = Summary(
                    transcript_id=transcript_id,
                    text=text,
                    key_points=key_points or []
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
                        'key_points': summary.key_points if summary.key_points else [] 
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