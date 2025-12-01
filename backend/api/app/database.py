import os
import psycopg2
from dotenv import load_dotenv
import bcrypt


class DataBaseManager:
    def __init__(self, user, password, host, port, dbname):
        self.connection =  psycopg2.connect(user=user,
                                  password=password,
                                  host=host,
                                  port=port,
                                  database=dbname)
        self.cursor = self.connection.cursor()

    def execute_query(self, query, params=None):
        self.cursor.execute(query, params)
        if query.strip().upper().startswith('SELECT'):
            return self.cursor.fetchall()
        else:
            self.connection.commit()

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
db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'dbname': os.getenv('DB_NAME')
}

def init_db():
    """Инициализация базы данных (создание таблиц)"""
    db = DataBaseManager(**db_config)
    try:
        db.create_tables()

        users = db.select_staff()
        if not users:
            db.insert_staff(
                surname="Иванов",
                name="Иван",
                patronymic="Иванович",
                email="test@example.com",
                login="test",
                password="test"  # Хэшируется автоматически
            )
            print("✅ Created test user")
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
    finally:
        db.disconnect_db()

def get_db():
    """Генератор для зависимостей FastAPI"""
    db = DataBaseManager(**db_config)
    try:
        yield db
    finally:
        db.disconnect_db()