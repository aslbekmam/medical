import sqlite3
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path(__file__).with_name("medical_clinic.sqlite3")


def get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id_patient INTEGER PRIMARY KEY AUTOINCREMENT,
            medical_card_number TEXT,
            fio TEXT,
            birth_date TEXT,
            gender TEXT CHECK (gender IN ('M', 'Ж')),
            address TEXT,
            phone TEXT,
            email TEXT,
            passport_series TEXT,
            passport_number TEXT,
            insurance_policy_number TEXT,
            insurance_type TEXT CHECK (insurance_type IN ('ОМС', 'ДМС', 'Платно')),
            insurance_company TEXT,
            registration_date TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id_doctor INTEGER PRIMARY KEY AUTOINCREMENT,
            fio TEXT,
            specialization TEXT,
            license_number TEXT,
            phone TEXT,
            email TEXT,
            office_number TEXT,
            hire_date TEXT,
            consultation_price NUMERIC,
            is_active INTEGER CHECK (is_active IN (0, 1)),
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS service_pricelist (
            id_service INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT,
            service_category TEXT,
            price_oms NUMERIC,
            price_dms NUMERIC,
            price_paid NUMERIC,
            duration_minutes INTEGER,
            is_active INTEGER CHECK (is_active IN (0, 1)),
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP)
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id_appointment INTEGER PRIMARY KEY AUTOINCREMENT,
            id_patient INTEGER,
            id_doctor INTEGER,
            appointment_date TEXT,
            appointment_time TEXT,
            appointment_type TEXT CHECK (appointment_type IN ('Первичный', 'Повторный', 'Профилактический')),
            status TEXT CHECK (status IN ('Запланирован', 'На приеме', 'Завершен', 'Не явился', 'Отменен')),
            price NUMERIC,
            notes TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_patient) REFERENCES patients(id_patient),
            FOREIGN KEY (id_doctor) REFERENCES doctors(id_doctor)
        );

        CREATE TABLE IF NOT EXISTS medical_records (
            id_record INTEGER PRIMARY KEY AUTOINCREMENT,
            id_appointment INTEGER,
            id_patient INTEGER,
            id_doctor INTEGER,
            record_date TEXT,
            complaints TEXT,
            examination TEXT,
            diagnosis_icd10 TEXT,
            diagnosis_description TEXT,
            treatment_plan TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_patient) REFERENCES patients(id_patient),
            FOREIGN KEY (id_doctor) REFERENCES doctors(id_doctor),
            FOREIGN KEY (id_appointment) REFERENCES appointments(id_appointment)
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id_prescription INTEGER PRIMARY KEY AUTOINCREMENT,
            id_record INTEGER,
            id_patient INTEGER,
            id_doctor INTEGER,
            prescription_date TEXT,
            medication_name TEXT,
            dosage TEXT,
            duration_days INTEGER,
            instructions TEXT,
            is_active INTEGER CHECK (is_active IN (0, 1)),
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_record) REFERENCES medical_records(id_record),
            FOREIGN KEY (id_patient) REFERENCES patients(id_patient),
            FOREIGN KEY (id_doctor) REFERENCES doctors(id_doctor)
        );

        CREATE TABLE IF NOT EXISTS lab_orders (
            id_lab_order INTEGER PRIMARY KEY AUTOINCREMENT,
            id_record INTEGER,
            id_patient INTEGER,
            id_doctor INTEGER,
            order_date TEXT,
            test_name TEXT,
            status TEXT CHECK (status IN ('Назначен', 'Выполнен', 'Отменен')),
            result_date TEXT,
            result_text TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_record) REFERENCES medical_records(id_record),
            FOREIGN KEY (id_patient) REFERENCES patients(id_patient),
            FOREIGN KEY (id_doctor) REFERENCES doctors(id_doctor)
        );

        CREATE TABLE IF NOT EXISTS payments (
            id_payment INTEGER PRIMARY KEY AUTOINCREMENT,
            id_appointment INTEGER,
            id_service INTEGER,
            payment_date TEXT,
            amount NUMERIC,
            payment_method TEXT CHECK (payment_method IN ('Наличные', 'Карта', 'По полису')),
            payment_status TEXT CHECK (payment_status IN ('Оплачен', 'Ожидает', 'Возврат', 'Частично оплачен')),
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            updated_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_appointment) REFERENCES appointments(id_appointment),
            FOREIGN KEY (id_service) REFERENCES service_pricelist(id_service)
        );

        CREATE TABLE IF NOT EXISTS appointment_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_appointment INTEGER NOT NULL,
            id_service INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            price NUMERIC,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_appointment) REFERENCES appointments(id_appointment),
            FOREIGN KEY (id_service) REFERENCES service_pricelist(id_service)
        );

        CREATE TABLE IF NOT EXISTS users (
            id_user INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK (role IN ('admin', 'client')) NOT NULL,
            id_patient INTEGER,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            FOREIGN KEY (id_patient) REFERENCES patients(id_patient)
        );
        """
    )


def _table_has_rows(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
    return cur.fetchone() is not None


def seed_data(conn: sqlite3.Connection) -> None:
    if _table_has_rows(conn, "users"):
        return

    with conn:
        conn.executescript(
            """
            INSERT INTO patients (
                medical_card_number, fio, birth_date, gender, address, phone, email,
                passport_series, passport_number, insurance_policy_number, insurance_type,
                insurance_company, registration_date, created_at, updated_at
            ) VALUES
                ('MC001', 'Иванов Иван Иванович', '1980-05-15', 'M', 'ул. Ленина, д. 10', '79150001122', 'ivanov@mail.ru', '1234', '567890', 'INS001', 'ОМС', 'Страховая Компания 1', '2023-01-12', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('MC002', 'Петров Сергей Олегович', '1985-08-22', 'M', 'ул. Пушкина, д. 25', '79160004567', 'petrov.sergey@mail.ru', '4321', '098765', 'INS002', 'ДМС', 'Страховая Компания 2', '2023-03-08', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('MC003', 'Сидорова Анна Петровна', '1990-11-30', 'Ж', 'ул. Горького, д. 30', '79170007890', 'sidorova@mail.ru', '5678', '123456', 'INS003', 'Платно', 'Страховая Компания 3', '2024-02-15', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO doctors (
                fio, specialization, license_number, phone, email, office_number,
                hire_date, consultation_price, is_active, created_at, updated_at
            ) VALUES
                ('Сидоров Алексей Николаевич', 'Терапевт', 'LN001', '79151112233', 'sidorov@clinic.ru', '101', '2020-04-01', 1200, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Орлов Дмитрий Сергеевич', 'Хирург', 'LN002', '79153334455', 'orlov@clinic.ru', '102', '2021-06-15', 1500, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Кузнецова Елена Петровна', 'Педиатр', 'LN003', '79156667788', 'kuznetsova@clinic.ru', '103', '2022-09-10', 1300, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO service_pricelist (
                service_name, service_category, price_oms, price_dms, price_paid,
                duration_minutes, is_active, created_at, updated_at
            ) VALUES
                ('Консультация терапевта', 'Консультация', 1200, 1500, 1800, 30, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Консультация хирурга', 'Консультация', 1500, 1800, 2000, 45, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('Консультация педиатра', 'Консультация', 1300, 1600, 1900, 30, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO appointments (
                id_patient, id_doctor, appointment_date, appointment_time,
                appointment_type, status, price, notes, created_at, updated_at
            ) VALUES
                (1, 1, '2024-03-01', '10:00:00', 'Первичный', 'Завершен', 1200, 'Общий осмотр', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 2, '2024-03-02', '11:00:00', 'Повторный', 'Запланирован', 1500, 'Консультация', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 3, '2024-03-03', '12:00:00', 'Профилактический', 'На приеме', 1300, 'Профилактический осмотр', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO medical_records (
                id_appointment, id_patient, id_doctor, record_date, complaints,
                examination, diagnosis_icd10, diagnosis_description, treatment_plan,
                created_at, updated_at
            ) VALUES
                (1, 1, 1, '2024-03-01', 'Головная боль', 'Общий осмотр', 'R51', 'Головная боль напряжения', 'Отдых и парацетамол', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 2, 2, '2024-03-02', 'Боль в животе', 'Пальпация живота', 'R10.4', 'Боль в области живота', 'Ибупрофен и диета', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 3, 3, '2024-03-03', 'Кашель', 'Аускультация легких', 'R05', 'Острый бронхит', 'Амоксициллин и ингаляции', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO prescriptions (
                id_record, id_patient, id_doctor, prescription_date, medication_name,
                dosage, duration_days, instructions, is_active, created_at, updated_at
            ) VALUES
                (1, 1, 1, '2024-03-01', 'Амоксициллин', '500 мг', 7, '3 раза в день', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 2, 2, '2024-03-02', 'Ибупрофен', '200 мг', 5, '2 раза в день', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 3, 3, '2024-03-03', 'Парацетамол', '500 мг', 3, '3 раза в день', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO lab_orders (
                id_record, id_patient, id_doctor, order_date, test_name, status,
                result_date, result_text, created_at, updated_at
            ) VALUES
                (1, 1, 1, '2024-03-01', 'Общий анализ крови', 'Выполнен', '2024-03-02', 'В пределах нормы', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 2, 2, '2024-03-02', 'Анализ мочи', 'Назначен', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 3, 3, '2024-03-03', 'Биохимический анализ крови', 'Отменен', NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO payments (
                id_appointment, id_service, payment_date, amount, payment_method,
                payment_status, created_at, updated_at
            ) VALUES
                (1, 1, '2024-03-01', 1200, 'Карта', 'Оплачен', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (2, 2, '2024-03-02', 1500, 'Наличные', 'Оплачен', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                (3, 3, '2024-03-03', 1300, 'По полису', 'Оплачен', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

            INSERT INTO users (login, password, role, id_patient) VALUES
                ('admin', 'admin', 'admin', NULL),
                ('ivanov', 'ivanov123', 'client', 1),
                ('petrov', 'petrov123', 'client', 2),
                ('sidorova', 'sidorova123', 'client', 3);
            """
        )


def setup_database(db_path: Optional[str | Path] = None, *, seed: bool = True) -> Path:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    conn = get_connection(path)
    try:
        init_db(conn)
        if seed:
            seed_data(conn)
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    setup_database()