from random import randint, choice
from faker import Faker
import random
import string


def gen_fake_data(db):
    fake = Faker("ru_RU")

    staff_ids = []
    length = 12
    for i in range(10):
        surname = fake.last_name()
        name = fake.first_name()
        patronymic = fake.middle_name()
        email = fake.unique.email()
        login = f"user_{i}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        staff_id = db.insert_staff(
            surname=surname,
            name=name,
            patronymic=patronymic,
            email=email,
            login=login,
            password=password
        )
        staff_ids.append(staff_id)


    transcript_ids = []
    for i in range(10):
        original_text = fake.text(max_nb_chars=500)
        clean_text = " ".join(original_text.split())  # немного «очищенный» текст
        employee_id = choice(staff_ids)
        tr_id = db.insert_transcripts(original_text, clean_text, employee_id=employee_id)
        transcript_ids.append(tr_id)


    for i in range(10):
        tr_id = choice(transcript_ids)
        transcript = db.select_transcripts_by_id(tr_id)
        text = transcript["clean_text"]
        words = text.split()
        if len(words) > 20:
            start_index = randint(0, len(words) - 20)
            part_text = " ".join(words[start_index:start_index + randint(10, 20)])
        else:
            part_text = text
        start_time = randint(0, 300)
        end_time = start_time + randint(5, 30)
        part_id = db.insert_parts_transcription(
            transcript_id=tr_id,
            text=part_text,
            start_time=start_time,
            end_time=end_time
        )


    for i in range(10):
        tr_id = choice(transcript_ids)
        summary_text = fake.text(max_nb_chars=200)
        s_id = db.insert_summaries(
            transcript_id=tr_id,
            text=summary_text
        )
