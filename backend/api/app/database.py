import os
import psycopg2
from dotenv import load_dotenv
import bcrypt
import time
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class DataBaseManager:
    def __init__(self, user, password, host, port, dbname, max_retries=10, retry_delay=5):
        """Инициализация с повторными попытками подключения"""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        for attempt in range(self.max_retries):
            try:
                self.connection = psycopg2.connect(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    database=dbname,
                    connect_timeout=10
                )
                self.cursor = self.connection.cursor()
                logger.info(f"✅ Успешное подключение к БД {host}:{port}")
                return
            except psycopg2.OperationalError as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"⚠️ Попытка {attempt + 1}/{self.max_retries}: "
                                  f"Не удалось подключиться к БД: {e}. Повтор через {self.retry_delay} сек...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ Не удалось подключиться к БД после {self.max_retries} попыток: {e}")
                    raise

    def execute_query(self, query, params=None):
        try:
            self.cursor.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                return self.cursor.fetchall()
            else:
                self.connection.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения запроса: {e}")
            self.connection.rollback()
            raise

    def disconnect_db(self):
        self.cursor.close()
        self.connection.close()

    def create_tables(self):
        query = '''
        CREATE TABLE IF NOT EXISTS Staff (
            ID SERIAL PRIMARY KEY,
            Surname VARCHAR(25) NOT NULL,
            Name VARCHAR(20) NOT NULL,
            Patronymic VARCHAR(25),
            Email VARCHAR(70) UNIQUE CHECK (Email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
            Login VARCHAR(30) UNIQUE NOT NULL,
            Password VARCHAR(100) NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Transcripts (
            ID SERIAL PRIMARY KEY,
            OriginalText TEXT NOT NULL,
            CleanText TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS PartsTranscription (
            ID SERIAL PRIMARY KEY,
            EmployeeID INTEGER NULL REFERENCES Staff(ID) ON DELETE SET NULL,
            TranscriptID INTEGER REFERENCES Transcripts(ID) ON DELETE CASCADE,
            Text TEXT NOT NULL,
            StartTime INTEGER NOT NULL,
            EndTime INTEGER NOT NULL CHECK(EndTime > StartTime)
        );

        CREATE TABLE IF NOT EXISTS Summaries (
            ID SERIAL PRIMARY KEY,
            TranscriptID INTEGER REFERENCES Transcripts(ID) ON DELETE CASCADE,
            Text TEXT NOT NULL
        )
        '''
        return self.execute_query(query)

    @staticmethod
    def hash_password(password):
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')

    @staticmethod
    def verify_password(password, hashed_password):
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

    def authentication(self, login, password):
        query = "SELECT ID, Password FROM Staff WHERE Login = %s"
        result = self.execute_query(query, (login,))

        if not result:
            return None

        employee_id, hashed_password = result[0]

        if self.verify_password(password, hashed_password):
            return employee_id
        else:
            return None

    def update_staff_password(self, employee_id, new_password):
        hashed_password = self.hash_password(new_password)
        query = "UPDATE Staff SET Password = %s WHERE ID = %s"
        return self.execute_query(query, (hashed_password, employee_id))

    def drop_table(self, name_table):
        query = f"DROP TABLE IF EXISTS {name_table} CASCADE"
        return self.execute_query(query)

    def select_staff(self):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff"
        return self.execute_query(query)

    def select_staff_by_id(self, employee_id):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff WHERE ID = %s"
        return self.execute_query(query, (employee_id,))

    def select_staff_by_surname(self, surname):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff WHERE Surname = %s"
        return self.execute_query(query, (surname,))

    def select_staff_by_name(self, name):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff WHERE Name = %s"
        return self.execute_query(query, (name,))

    def select_staff_by_login(self, login):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff WHERE Login = %s"
        return self.execute_query(query, (login,))

    def select_staff_by_email(self, email):
        query = "SELECT ID, Surname, Name, Patronymic, Email, Login FROM Staff WHERE Email = %s"
        return self.execute_query(query, (email,))

    def insert_staff(self, surname, name, patronymic, email, login, password):
        hashed_password = self.hash_password(password)
        query = """
        INSERT INTO Staff (Surname, Name, Patronymic, Email, Login, Password)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (surname, name, patronymic, email, login, hashed_password))

    def update_staff(self, employee_id, surname, name, patronymic, email, login):
        query = """
        UPDATE Staff
        SET Surname = %s,
            Name = %s,
            Patronymic = %s,
            Email = %s,
            Login = %s
        WHERE ID = %s
        """
        return self.execute_query(query, (surname, name, patronymic, email, login, employee_id))

    def delete_staff(self, employee_id):
        query = "DELETE FROM Staff WHERE ID = %s"
        return self.execute_query(query, (employee_id,))

    def select_transcripts(self):
        query = "SELECT * FROM Transcripts"
        return self.execute_query(query)

    def select_transcripts_by_id(self, transcript_id):
        query = "SELECT * FROM Transcripts WHERE ID = %s"
        return self.execute_query(query, (transcript_id,))

    def insert_transcripts(self, original_text, clean_text):
        query = """
        INSERT INTO Transcripts (OriginalText, CleanText)
        VALUES (%s, %s)
        """
        return self.execute_query(query, (original_text, clean_text))

    def update_transcripts(self, transcript_id, original_text, clean_text):
        query = """
        UPDATE Transcripts
        SET OriginalText = %s,
            CleanText = %s
        WHERE ID = %s
        """
        return self.execute_query(query, (original_text, clean_text, transcript_id))

    def delete_transcripts(self,transcript_id):
        query = "DELETE FROM Transcripts WHERE ID = %s"
        return self.execute_query(query, (transcript_id,))

    def select_parts_transcription(self):
        query = "SELECT * FROM PartsTranscription"
        return self.execute_query(query)

    def select_parts_transcription_by_id(self, part_id):
        query = "SELECT * FROM PartsTranscription WHERE ID = %s"
        return self.execute_query(query, (part_id,))

    def select_parts_transcription_by_employee_id(self, employee_id):
        query = "SELECT * FROM PartsTranscription WHERE EmployeeID = %s"
        return self.execute_query(query, (employee_id,))

    def select_parts_transcription_by_transcript_id(self, transcript_id):
        query = "SELECT * FROM PartsTranscription WHERE TranscriptID = %s"
        return self.execute_query(query, (transcript_id,))

    def insert_parts_transcription(self, employee_id, transcript_id, text, start_time, end_time):
        query = """
        INSERT INTO PartsTranscription (EmployeeID, TranscriptID, Text, StartTime, EndTime)
        VALUES (%s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (employee_id, transcript_id, text, start_time, end_time))

    def update_parts_transcription(self, part_id, employee_id, transcript_id, text, start_time, end_time):
        query = """
        UPDATE PartsTranscription
        SET EmployeeID = %s,
            TranscriptID = %s,
            Text = %s,
            StartTime = %s,
            EndTime = %s
        WHERE ID = %s
        """
        return self.execute_query(query, (employee_id, transcript_id, text, start_time, end_time, part_id))

    def delete_parts_transcription(self, part_id):
        query = "DELETE FROM PartsTranscription WHERE ID = %s"
        return self.execute_query(query, (part_id,))

    def select_summaries(self):
        query = "SELECT * FROM Summaries"
        return self.execute_query(query)

    def select_summaries_by_id(self, summary_id):
        query = "SELECT * FROM Summaries WHERE ID = %s"
        return self.execute_query(query, (summary_id,))

    def select_summaries_by_transcript_id(self, transcript_id):
        query = "SELECT * FROM Summaries WHERE TranscriptID = %s"
        return self.execute_query(query, (transcript_id,))

    def insert_summaries(self, transcript_id, text):
        query = """
        INSERT INTO Summaries (TranscriptID, Text)
        VALUES (%s, %s)
        """
        return self.execute_query(query, (transcript_id, text))

    def update_summaries(self, summary_id, transcript_id, text):
        query = """
        UPDATE Summaries
        SET TranscriptID = %s,
            Text = %s
        WHERE ID = %s
        """
        return self.execute_query(query, (transcript_id, text, summary_id))

    def delete_summaries(self, summary_id):
        query = "DELETE FROM Summaries WHERE ID = %s"
        return self.execute_query(query, (summary_id,))

# Получение параметров подключения из переменных окружения
load_dotenv()

db_config = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'meeting_analyzer'),
    'max_retries': int(os.getenv('DB_MAX_RETRIES', '10')),
    'retry_delay': int(os.getenv('DB_RETRY_DELAY', '5'))
}

def init_db():
    """Инициализация базы данных (создание таблиц) с повторными попытками"""
    logger.info("🔄 Инициализация базы данных...")
    db = None
    try:
        db = DataBaseManager(**db_config)
        db.create_tables()

        # Создаем тестового пользователя, если нет пользователей
        users = db.select_staff()
        if not users:
            db.insert_staff(
                surname="Иванов",
                name="Иван",
                patronymic="Иванович",
                email="test@example.com",
                login="test",
                password="test"
            )
            logger.info("✅ Создан тестовый пользователь: test/test")
        
        logger.info("✅ Таблицы базы данных созданы успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise
    finally:
        if db:
            db.disconnect_db()

def get_db():
    """Генератор для зависимостей FastAPI"""
    db = DataBaseManager(**db_config)
    try:
        yield db
    finally:
        db.disconnect_db()