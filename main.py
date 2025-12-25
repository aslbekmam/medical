import sys
from datetime import datetime, date
from typing import Optional, List

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QDate, QTime
from PyQt5.QtGui import QFont
import db


STATUSES = ['Запланирован', 'На приеме', 'Завершен', 'Не явился', 'Отменен']
APPOINTMENT_TYPES = ['Первичный', 'Повторный', 'Профилактический']


class Database:
    def __init__(self):
        db.setup_database(seed=True)
        self.conn = db.get_connection()

    def get_appointments(self, status: Optional[str] = None,
                         date_from: Optional[str] = None,
                         date_to: Optional[str] = None) -> List[dict]:
        query = """
            SELECT a.id_appointment, a.appointment_date, a.appointment_time,
                   a.appointment_type, a.status, a.price, a.notes,
                   p.fio as patient_fio, p.phone as patient_phone,
                   d.fio as doctor_fio, d.specialization
            FROM appointments a
            JOIN patients p ON a.id_patient = p.id_patient
            JOIN doctors d ON a.id_doctor = d.id_doctor
            WHERE 1=1
        """
        params = []
        if status and status != 'Все':
            query += " AND a.status = ?"
            params.append(status)
        if date_from:
            query += " AND a.appointment_date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND a.appointment_date <= ?"
            params.append(date_to)
        query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"
        cur = self.conn.execute(query, params)
        return [dict(row) for row in cur.fetchall()]

    def get_patients(self) -> List[dict]:
        cur = self.conn.execute("SELECT * FROM patients ORDER BY fio")
        return [dict(row) for row in cur.fetchall()]

    def get_doctors(self, active_only: bool = True) -> List[dict]:
        query = "SELECT * FROM doctors"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY fio"
        cur = self.conn.execute(query)
        return [dict(row) for row in cur.fetchall()]

    def get_services(self, active_only: bool = True) -> List[dict]:
        query = "SELECT * FROM service_pricelist"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY service_category, service_name"
        cur = self.conn.execute(query)
        return [dict(row) for row in cur.fetchall()]

    def get_appointment_services(self, id_appointment: int) -> List[dict]:
        cur = self.conn.execute("""
            SELECT aps.*, sp.service_name, sp.service_category
            FROM appointment_services aps
            JOIN service_pricelist sp ON aps.id_service = sp.id_service
            WHERE aps.id_appointment = ?
        """, (id_appointment,))
        return [dict(row) for row in cur.fetchall()]

    def create_patient(self, fio: str, phone: str, email: str) -> int:
        cur = self.conn.execute("""
            INSERT INTO patients (fio, phone, email, registration_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (fio, phone, email, date.today().isoformat()))
        self.conn.commit()
        return cur.lastrowid

    def create_appointment(self, id_patient: int, id_doctor: int,
                           appointment_date: str, appointment_time: str,
                           appointment_type: str, notes: str, price: float) -> int:
        cur = self.conn.execute("""
            INSERT INTO appointments (id_patient, id_doctor, appointment_date, appointment_time,
                                       appointment_type, status, price, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'Запланирован', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (id_patient, id_doctor, appointment_date, appointment_time, appointment_type, price, notes))
        self.conn.commit()
        return cur.lastrowid

    def add_appointment_service(self, id_appointment: int, id_service: int, price: float, quantity: int = 1):
        self.conn.execute("""
            INSERT INTO appointment_services (id_appointment, id_service, price, quantity)
            VALUES (?, ?, ?, ?)
        """, (id_appointment, id_service, price, quantity))
        self.conn.commit()

    def update_appointment(self, id_appointment: int, id_doctor: int, status: str, notes: str, price: float):
        self.conn.execute("""
            UPDATE appointments SET id_doctor = ?, status = ?, notes = ?, price = ?,
                                    updated_at = CURRENT_TIMESTAMP
            WHERE id_appointment = ?
        """, (id_doctor, status, notes, price, id_appointment))
        self.conn.commit()

    def clear_appointment_services(self, id_appointment: int):
        self.conn.execute("DELETE FROM appointment_services WHERE id_appointment = ?", (id_appointment,))
        self.conn.commit()

    def get_patient_appointments(self, id_patient: int) -> List[dict]:
        cur = self.conn.execute("""
            SELECT a.*, d.fio as doctor_fio, d.specialization
            FROM appointments a
            JOIN doctors d ON a.id_doctor = d.id_doctor
            WHERE a.id_patient = ?
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
        """, (id_patient,))
        return [dict(row) for row in cur.fetchall()]

    def get_appointment_by_id(self, id_appointment: int) -> Optional[dict]:
        cur = self.conn.execute("""
            SELECT a.*, p.fio as patient_fio, p.phone as patient_phone,
                   d.fio as doctor_fio, d.specialization
            FROM appointments a
            JOIN patients p ON a.id_patient = p.id_patient
            JOIN doctors d ON a.id_doctor = d.id_doctor
            WHERE a.id_appointment = ?
        """, (id_appointment,))
        row = cur.fetchone()
        return dict(row) if row else None

    def authenticate(self, login: str, password: str) -> Optional[dict]:
        cur = self.conn.execute("""
            SELECT u.*, p.fio as patient_fio
            FROM users u
            LEFT JOIN patients p ON u.id_patient = p.id_patient
            WHERE u.login = ? AND u.password = ?
        """, (login, password))
        row = cur.fetchone()
        return dict(row) if row else None


class NewAppointmentDialog(QDialog):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.database = database
        self.selected_services = []
        self.setWindowTitle("Новый приём")
        self.setMinimumWidth(600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        patient_group = QGroupBox("Пациент")
        patient_layout = QFormLayout()
        self.patient_combo = QComboBox()
        self.patient_combo.addItem("-- Новый пациент --", None)
        for p in self.database.get_patients():
            self.patient_combo.addItem(f"{p['fio']} ({p['phone']})", p['id_patient'])
        self.patient_combo.currentIndexChanged.connect(self.on_patient_changed)
        patient_layout.addRow("Выбрать:", self.patient_combo)

        self.fio_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        patient_layout.addRow("ФИО:", self.fio_edit)
        patient_layout.addRow("Телефон:", self.phone_edit)
        patient_layout.addRow("Email:", self.email_edit)
        patient_group.setLayout(patient_layout)
        layout.addWidget(patient_group)

        appt_group = QGroupBox("Приём")
        appt_layout = QFormLayout()
        self.doctor_combo = QComboBox()
        for d in self.database.get_doctors():
            self.doctor_combo.addItem(f"{d['fio']} ({d['specialization']})", d['id_doctor'])
        appt_layout.addRow("Врач:", self.doctor_combo)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        appt_layout.addRow("Дата:", self.date_edit)

        self.time_edit = QTimeEdit(QTime(9, 0))
        appt_layout.addRow("Время:", self.time_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(APPOINTMENT_TYPES)
        appt_layout.addRow("Тип:", self.type_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        appt_layout.addRow("Примечания:", self.notes_edit)
        appt_group.setLayout(appt_layout)
        layout.addWidget(appt_group)

        services_group = QGroupBox("Услуги из прайс-листа")
        services_layout = QVBoxLayout()
        self.services_list = QListWidget()
        self.services_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for s in self.database.get_services():
            item = QListWidgetItem(f"{s['service_name']} — {s['price_paid']} руб.")
            item.setData(Qt.UserRole, s)
            self.services_list.addItem(item)
        self.services_list.itemSelectionChanged.connect(self.update_total)
        services_layout.addWidget(self.services_list)

        self.total_label = QLabel("Итого: 0 руб.")
        self.total_label.setFont(QFont("Arial", 12, QFont.Bold))
        services_layout.addWidget(self.total_label)
        services_group.setLayout(services_layout)
        layout.addWidget(services_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def on_patient_changed(self, index):
        patient_id = self.patient_combo.currentData()
        is_new = patient_id is None
        self.fio_edit.setEnabled(is_new)
        self.phone_edit.setEnabled(is_new)
        self.email_edit.setEnabled(is_new)
        if not is_new:
            self.fio_edit.clear()
            self.phone_edit.clear()
            self.email_edit.clear()

    def update_total(self):
        total = sum(item.data(Qt.UserRole)['price_paid'] for item in self.services_list.selectedItems())
        self.total_label.setText(f"Итого: {total:.2f} руб.")

    def get_data(self) -> dict:
        selected_services = [item.data(Qt.UserRole) for item in self.services_list.selectedItems()]
        total = sum(s['price_paid'] for s in selected_services)
        return {
            'patient_id': self.patient_combo.currentData(),
            'fio': self.fio_edit.text().strip(),
            'phone': self.phone_edit.text().strip(),
            'email': self.email_edit.text().strip(),
            'doctor_id': self.doctor_combo.currentData(),
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'time': self.time_edit.time().toString("HH:mm:ss"),
            'type': self.type_combo.currentText(),
            'notes': self.notes_edit.toPlainText().strip(),
            'services': selected_services,
            'total': total
        }


class EditAppointmentDialog(QDialog):
    def __init__(self, database: Database, appointment: dict, parent=None):
        super().__init__(parent)
        self.database = database
        self.appointment = appointment
        self.setWindowTitle(f"Редактирование приёма #{appointment['id_appointment']}")
        self.setMinimumWidth(600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox("Информация")
        info_layout = QFormLayout()
        info_layout.addRow("Пациент:", QLabel(self.appointment['patient_fio']))
        info_layout.addRow("Телефон:", QLabel(self.appointment.get('patient_phone', '')))
        info_layout.addRow("Дата:", QLabel(self.appointment['appointment_date']))
        info_layout.addRow("Время:", QLabel(self.appointment['appointment_time']))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        edit_group = QGroupBox("Редактирование")
        edit_layout = QFormLayout()

        self.doctor_combo = QComboBox()
        doctors = self.database.get_doctors()
        for i, d in enumerate(doctors):
            self.doctor_combo.addItem(f"{d['fio']} ({d['specialization']})", d['id_doctor'])
            if d['id_doctor'] == self.appointment['id_doctor']:
                self.doctor_combo.setCurrentIndex(i)
        edit_layout.addRow("Врач:", self.doctor_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.status_combo.setCurrentText(self.appointment['status'])
        edit_layout.addRow("Статус:", self.status_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(self.appointment.get('notes', ''))
        self.notes_edit.setMaximumHeight(60)
        edit_layout.addRow("Примечания:", self.notes_edit)
        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)

        services_group = QGroupBox("Услуги")
        services_layout = QVBoxLayout()
        self.services_list = QListWidget()
        self.services_list.setSelectionMode(QAbstractItemView.MultiSelection)

        current_service_ids = set()
        for s in self.database.get_appointment_services(self.appointment['id_appointment']):
            current_service_ids.add(s['id_service'])

        for s in self.database.get_services():
            item = QListWidgetItem(f"{s['service_name']} — {s['price_paid']} руб.")
            item.setData(Qt.UserRole, s)
            self.services_list.addItem(item)
            if s['id_service'] in current_service_ids:
                item.setSelected(True)

        self.services_list.itemSelectionChanged.connect(self.update_total)
        services_layout.addWidget(self.services_list)

        self.total_label = QLabel()
        self.total_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.update_total()
        services_layout.addWidget(self.total_label)
        services_group.setLayout(services_layout)
        layout.addWidget(services_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_total(self):
        total = sum(item.data(Qt.UserRole)['price_paid'] for item in self.services_list.selectedItems())
        self.total_label.setText(f"Итого: {total:.2f} руб.")

    def get_data(self) -> dict:
        selected_services = [item.data(Qt.UserRole) for item in self.services_list.selectedItems()]
        total = sum(s['price_paid'] for s in selected_services)
        return {
            'doctor_id': self.doctor_combo.currentData(),
            'status': self.status_combo.currentText(),
            'notes': self.notes_edit.toPlainText().strip(),
            'services': selected_services,
            'total': total
        }


class AdminTab(QWidget):
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self.setup_ui()
        self.load_appointments()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        filter_group = QGroupBox("Фильтры")
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Статус:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("Все")
        self.status_filter.addItems(STATUSES)
        filter_layout.addWidget(self.status_filter)

        filter_layout.addWidget(QLabel("Дата с:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("по:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate().addMonths(1))
        filter_layout.addWidget(self.date_to)

        self.filter_btn = QPushButton("Фильтровать")
        self.filter_btn.clicked.connect(self.apply_filter)
        filter_layout.addWidget(self.filter_btn)

        self.show_all_btn = QPushButton("Показать все")
        self.show_all_btn.clicked.connect(self.show_all)
        filter_layout.addWidget(self.show_all_btn)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        btn_layout = QHBoxLayout()
        self.new_btn = QPushButton("Новый приём")
        self.new_btn.clicked.connect(self.new_appointment)
        btn_layout.addWidget(self.new_btn)

        self.edit_btn = QPushButton("Редактировать")
        self.edit_btn.clicked.connect(self.edit_appointment)
        btn_layout.addWidget(self.edit_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Дата", "Время", "Пациент", "Врач", "Тип", "Статус", "Стоимость"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(self.edit_appointment)
        layout.addWidget(self.table)

    def load_appointments(self, status=None, date_from=None, date_to=None):
        appointments = self.database.get_appointments(status, date_from, date_to)
        self.table.setRowCount(len(appointments))
        for i, a in enumerate(appointments):
            self.table.setItem(i, 0, QTableWidgetItem(str(a['id_appointment'])))
            self.table.setItem(i, 1, QTableWidgetItem(a['appointment_date']))
            self.table.setItem(i, 2, QTableWidgetItem(a['appointment_time']))
            self.table.setItem(i, 3, QTableWidgetItem(a['patient_fio']))
            self.table.setItem(i, 4, QTableWidgetItem(a['doctor_fio']))
            self.table.setItem(i, 5, QTableWidgetItem(a['appointment_type']))
            self.table.setItem(i, 6, QTableWidgetItem(a['status']))
            self.table.setItem(i, 7, QTableWidgetItem(f"{a['price']:.2f}" if a['price'] else "0.00"))

    def apply_filter(self):
        status = self.status_filter.currentText()
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        self.load_appointments(status, date_from, date_to)

    def show_all(self):
        self.status_filter.setCurrentIndex(0)
        self.load_appointments()

    def get_selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def new_appointment(self):
        dialog = NewAppointmentDialog(self.database, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if data['patient_id'] is None:
                if not data['fio']:
                    QMessageBox.warning(self, "Ошибка", "Введите ФИО пациента")
                    return
                patient_id = self.database.create_patient(data['fio'], data['phone'], data['email'])
            else:
                patient_id = data['patient_id']

            appt_id = self.database.create_appointment(
                patient_id, data['doctor_id'], data['date'], data['time'],
                data['type'], data['notes'], data['total']
            )
            for s in data['services']:
                self.database.add_appointment_service(appt_id, s['id_service'], s['price_paid'])

            self.load_appointments()
            QMessageBox.information(self, "Успех", f"Приём #{appt_id} создан")

    def edit_appointment(self):
        appt_id = self.get_selected_id()
        if not appt_id:
            QMessageBox.warning(self, "Ошибка", "Выберите приём")
            return

        appointment = self.database.get_appointment_by_id(appt_id)
        if not appointment:
            return

        dialog = EditAppointmentDialog(self.database, appointment, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self.database.update_appointment(
                appt_id, data['doctor_id'], data['status'], data['notes'], data['total']
            )
            self.database.clear_appointment_services(appt_id)
            for s in data['services']:
                self.database.add_appointment_service(appt_id, s['id_service'], s['price_paid'])

            self.load_appointments()
            QMessageBox.information(self, "Успех", "Приём обновлён")


class ClientTab(QWidget):
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self.current_patient_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        patient_group = QGroupBox("Выбор пациента")
        patient_layout = QHBoxLayout()
        self.patient_combo = QComboBox()
        self.patient_combo.addItem("-- Выберите --", None)
        for p in self.database.get_patients():
            self.patient_combo.addItem(f"{p['fio']} ({p['phone']})", p['id_patient'])
        self.patient_combo.currentIndexChanged.connect(self.on_patient_selected)
        patient_layout.addWidget(self.patient_combo)
        patient_layout.addStretch()
        patient_group.setLayout(patient_layout)
        layout.addWidget(patient_group)

        book_group = QGroupBox("Запись на приём")
        book_layout = QFormLayout()

        self.book_doctor = QComboBox()
        for d in self.database.get_doctors():
            self.book_doctor.addItem(f"{d['fio']} ({d['specialization']})", d['id_doctor'])
        book_layout.addRow("Врач:", self.book_doctor)

        self.book_date = QDateEdit(QDate.currentDate().addDays(1))
        self.book_date.setCalendarPopup(True)
        self.book_date.setMinimumDate(QDate.currentDate())
        book_layout.addRow("Дата:", self.book_date)

        self.book_time = QTimeEdit(QTime(9, 0))
        book_layout.addRow("Время:", self.book_time)

        self.book_type = QComboBox()
        self.book_type.addItems(APPOINTMENT_TYPES)
        book_layout.addRow("Тип приёма:", self.book_type)

        self.book_service = QComboBox()
        for s in self.database.get_services():
            self.book_service.addItem(f"{s['service_name']} — {s['price_paid']} руб.", s)
        book_layout.addRow("Услуга:", self.book_service)

        self.book_btn = QPushButton("Записаться")
        self.book_btn.clicked.connect(self.book_appointment)
        book_layout.addRow("", self.book_btn)
        book_group.setLayout(book_layout)
        layout.addWidget(book_group)

        history_group = QGroupBox("История обслуживания")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "ID", "Дата", "Время", "Врач", "Статус", "Стоимость"
        ])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

    def on_patient_selected(self, index):
        self.current_patient_id = self.patient_combo.currentData()
        self.load_history()

    def load_history(self):
        self.history_table.setRowCount(0)
        if not self.current_patient_id:
            return

        appointments = self.database.get_patient_appointments(self.current_patient_id)
        self.history_table.setRowCount(len(appointments))
        for i, a in enumerate(appointments):
            self.history_table.setItem(i, 0, QTableWidgetItem(str(a['id_appointment'])))
            self.history_table.setItem(i, 1, QTableWidgetItem(a['appointment_date']))
            self.history_table.setItem(i, 2, QTableWidgetItem(a['appointment_time']))
            self.history_table.setItem(i, 3, QTableWidgetItem(a['doctor_fio']))
            self.history_table.setItem(i, 4, QTableWidgetItem(a['status']))
            self.history_table.setItem(i, 5, QTableWidgetItem(f"{a['price']:.2f}" if a['price'] else "0.00"))

    def book_appointment(self):
        if not self.current_patient_id:
            QMessageBox.warning(self, "Ошибка", "Выберите пациента")
            return

        service = self.book_service.currentData()
        price = service['price_paid'] if service else 0

        appt_id = self.database.create_appointment(
            self.current_patient_id,
            self.book_doctor.currentData(),
            self.book_date.date().toString("yyyy-MM-dd"),
            self.book_time.time().toString("HH:mm:ss"),
            self.book_type.currentText(),
            "",
            price
        )
        if service:
            self.database.add_appointment_service(appt_id, service['id_service'], price)

        self.load_history()
        QMessageBox.information(self, "Успех", f"Вы записаны на приём #{appt_id}")


class LoginDialog(QDialog):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.database = database
        self.user = None
        self.setWindowTitle("Авторизация")
        self.setFixedSize(300, 150)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Введите логин")
        form_layout.addRow("Логин:", self.login_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Введите пароль")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Пароль:", self.password_edit)
        layout.addLayout(form_layout)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self.try_login)
        layout.addWidget(self.login_btn)

        self.password_edit.returnPressed.connect(self.try_login)
        self.login_edit.returnPressed.connect(self.try_login)

    def try_login(self):
        login = self.login_edit.text().strip()
        password = self.password_edit.text()

        user = self.database.authenticate(login, password)
        if user:
            self.user = user
            self.accept()
        else:
            self.error_label.setText("Неверный логин или пароль")
            self.password_edit.clear()
            self.password_edit.setFocus()

    def get_user(self) -> Optional[dict]:
        return self.user


class AdminWindow(QMainWindow):
    def __init__(self, database: Database, user: dict):
        super().__init__()
        self.database = database
        self.user = user
        self.setWindowTitle("Медицинская клиника — Администратор")
        self.setMinimumSize(1000, 700)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(AdminTab(self.database))
        self.setCentralWidget(central)


class ClientWindow(QMainWindow):
    def __init__(self, database: Database, user: dict):
        super().__init__()
        self.database = database
        self.user = user
        self.patient_id = user.get('id_patient')
        patient_name = user.get('patient_fio', user['login'])
        self.setWindowTitle(f"Медицинская клиника — {patient_name}")
        self.setMinimumSize(900, 600)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.setup_ui(layout)
        self.setCentralWidget(central)
        self.load_history()

    def setup_ui(self, layout):
        book_group = QGroupBox("Запись на приём")
        book_layout = QFormLayout()

        self.book_doctor = QComboBox()
        for d in self.database.get_doctors():
            self.book_doctor.addItem(f"{d['fio']} ({d['specialization']})", d['id_doctor'])
        book_layout.addRow("Врач:", self.book_doctor)

        self.book_date = QDateEdit(QDate.currentDate().addDays(1))
        self.book_date.setCalendarPopup(True)
        self.book_date.setMinimumDate(QDate.currentDate())
        book_layout.addRow("Дата:", self.book_date)

        self.book_time = QTimeEdit(QTime(9, 0))
        book_layout.addRow("Время:", self.book_time)

        self.book_type = QComboBox()
        self.book_type.addItems(APPOINTMENT_TYPES)
        book_layout.addRow("Тип приёма:", self.book_type)

        self.book_service = QComboBox()
        for s in self.database.get_services():
            self.book_service.addItem(f"{s['service_name']} — {s['price_paid']} руб.", s)
        book_layout.addRow("Услуга:", self.book_service)

        self.book_btn = QPushButton("Записаться")
        self.book_btn.clicked.connect(self.book_appointment)
        book_layout.addRow("", self.book_btn)
        book_group.setLayout(book_layout)
        layout.addWidget(book_group)

        history_group = QGroupBox("История обслуживания")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "ID", "Дата", "Время", "Врач", "Статус", "Стоимость"
        ])
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

    def load_history(self):
        self.history_table.setRowCount(0)
        if not self.patient_id:
            return

        appointments = self.database.get_patient_appointments(self.patient_id)
        self.history_table.setRowCount(len(appointments))
        for i, a in enumerate(appointments):
            self.history_table.setItem(i, 0, QTableWidgetItem(str(a['id_appointment'])))
            self.history_table.setItem(i, 1, QTableWidgetItem(a['appointment_date']))
            self.history_table.setItem(i, 2, QTableWidgetItem(a['appointment_time']))
            self.history_table.setItem(i, 3, QTableWidgetItem(a['doctor_fio']))
            self.history_table.setItem(i, 4, QTableWidgetItem(a['status']))
            self.history_table.setItem(i, 5, QTableWidgetItem(f"{a['price']:.2f}" if a['price'] else "0.00"))

    def book_appointment(self):
        if not self.patient_id:
            QMessageBox.warning(self, "Ошибка", "Пациент не привязан к аккаунту")
            return

        service = self.book_service.currentData()
        price = service['price_paid'] if service else 0

        appt_id = self.database.create_appointment(
            self.patient_id,
            self.book_doctor.currentData(),
            self.book_date.date().toString("yyyy-MM-dd"),
            self.book_time.time().toString("HH:mm:ss"),
            self.book_type.currentText(),
            "",
            price
        )
        if service:
            self.database.add_appointment_service(appt_id, service['id_service'], price)

        self.load_history()
        QMessageBox.information(self, "Успех", f"Вы записаны на приём #{appt_id}")


def main():
    app = QApplication(sys.argv)

    database = Database()

    login_dialog = LoginDialog(database)
    if login_dialog.exec_() != QDialog.Accepted:
        sys.exit(0)

    user = login_dialog.get_user()

    if user['role'] == 'admin':
        window = AdminWindow(database, user)
    else:
        window = ClientWindow(database, user)

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()