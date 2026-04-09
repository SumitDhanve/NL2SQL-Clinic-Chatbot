"""Create and seed the clinic SQLite database."""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path("clinic.db")
RANDOM_SEED = 42

PATIENT_COUNT = 200
DOCTOR_COUNT = 15
APPOINTMENT_COUNT = 500
TREATMENT_COUNT = 350
INVOICE_COUNT = 300

SPECIALIZATIONS = [
    "Dermatology",
    "Cardiology",
    "Orthopedics",
    "General",
    "Pediatrics",
]

DEPARTMENTS = {
    "Dermatology": "Skin Care",
    "Cardiology": "Heart Center",
    "Orthopedics": "Bone and Joint",
    "General": "Primary Care",
    "Pediatrics": "Child Care",
}

FIRST_NAMES = [
    "Aarav", "Aditi", "Aisha", "Akash", "Ananya", "Arjun", "Bhavya", "Dev",
    "Diya", "Farhan", "Gauri", "Ishaan", "Isha", "Kabir", "Karan", "Kavya",
    "Krishna", "Meera", "Mihir", "Naina", "Neha", "Nikhil", "Pooja", "Priya",
    "Rahul", "Rhea", "Rohit", "Sana", "Sanjay", "Shreya", "Sneha", "Tanvi",
    "Varun", "Ved", "Vihaan", "Zara",
]

LAST_NAMES = [
    "Agarwal", "Bansal", "Chauhan", "Desai", "Gupta", "Iyer", "Jain", "Joshi",
    "Kapoor", "Kulkarni", "Mehta", "Menon", "Nair", "Patel", "Rao", "Reddy",
    "Shah", "Sharma", "Singh", "Srinivasan", "Tiwari", "Verma", "Yadav",
]

CITIES = [
    "Bengaluru",
    "Chennai",
    "Delhi",
    "Hyderabad",
    "Jaipur",
    "Kolkata",
    "Lucknow",
    "Mumbai",
    "Pune",
    "Surat",
]

DOCTOR_PROFILES = {
    "Dermatology": [
        ("Dr. Rhea Kapoor", "9001100001"),
        ("Dr. Karan Shah", "9001100002"),
        ("Dr. Meera Joshi", "9001100003"),
    ],
    "Cardiology": [
        ("Dr. Rahul Menon", "9001200001"),
        ("Dr. Aditi Nair", "9001200002"),
        ("Dr. Varun Desai", "9001200003"),
    ],
    "Orthopedics": [
        ("Dr. Arjun Patel", "9001300001"),
        ("Dr. Sneha Rao", "9001300002"),
        ("Dr. Nikhil Sharma", "9001300003"),
    ],
    "General": [
        ("Dr. Priya Verma", "9001400001"),
        ("Dr. Dev Agarwal", "9001400002"),
        ("Dr. Isha Gupta", "9001400003"),
    ],
    "Pediatrics": [
        ("Dr. Tanvi Jain", "9001500001"),
        ("Dr. Rohit Kulkarni", "9001500002"),
        ("Dr. Zara Bansal", "9001500003"),
    ],
}

APPOINTMENT_STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show"]
APPOINTMENT_WEIGHTS = [0.18, 0.56, 0.18, 0.08]

INVOICE_STATUSES = ["Paid", "Pending", "Overdue"]
INVOICE_WEIGHTS = [0.58, 0.25, 0.17]

NOTES = [
    None,
    None,
    "Routine follow-up advised.",
    "Patient reported mild discomfort.",
    "Bring previous reports in next visit.",
    "Symptoms improving after medication.",
    "Further evaluation recommended.",
]

TREATMENTS_BY_SPECIALIZATION = {
    "Dermatology": [
        ("Acne Treatment", (350, 1200), (20, 45)),
        ("Laser Therapy", (1500, 4200), (30, 75)),
        ("Skin Allergy Consultation", (500, 900), (15, 30)),
        ("Mole Removal", (1800, 3200), (25, 60)),
    ],
    "Cardiology": [
        ("ECG", (300, 800), (15, 25)),
        ("Echocardiogram", (1800, 3500), (30, 60)),
        ("Stress Test", (2200, 4500), (35, 70)),
        ("Cardiac Consultation", (800, 1400), (20, 40)),
    ],
    "Orthopedics": [
        ("Physiotherapy Session", (700, 1800), (30, 60)),
        ("Joint Injection", (1200, 2800), (20, 40)),
        ("Fracture Review", (600, 1200), (15, 35)),
        ("Knee Assessment", (900, 1700), (20, 45)),
    ],
    "General": [
        ("General Checkup", (250, 700), (15, 25)),
        ("Vaccination", (300, 1200), (10, 20)),
        ("Blood Pressure Review", (200, 450), (10, 15)),
        ("Fever Consultation", (350, 900), (15, 30)),
    ],
    "Pediatrics": [
        ("Child Wellness Visit", (400, 900), (20, 35)),
        ("Pediatric Vaccination", (500, 1500), (10, 20)),
        ("Growth Assessment", (450, 1000), (20, 30)),
        ("Nebulization", (300, 700), (15, 25)),
    ],
}


@dataclass(frozen=True)
class SeedSummary:
    patients: int
    doctors: int
    appointments: int
    treatments: int
    invoices: int


def random_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def random_datetime(start: datetime, end: datetime) -> datetime:
    total_seconds = int((end - start).total_seconds())
    offset = random.randint(0, total_seconds)
    candidate = start + timedelta(seconds=offset)
    hour = random.choice([9, 10, 11, 12, 14, 15, 16, 17])
    minute = random.choice([0, 15, 30, 45])
    return candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)


def maybe_email(first_name: str, last_name: str) -> str | None:
    if random.random() < 0.14:
        return None
    handle = f"{first_name}.{last_name}{random.randint(1, 99)}".lower()
    return f"{handle}@{random.choice(['gmail.com', 'outlook.com', 'yahoo.com'])}"


def maybe_phone() -> str | None:
    if random.random() < 0.12:
        return None
    return f"+91-{random.randint(70000, 99999)}-{random.randint(10000, 99999)}"


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def recreate_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS treatments;
        DROP TABLE IF EXISTS invoices;
        DROP TABLE IF EXISTS appointments;
        DROP TABLE IF EXISTS doctors;
        DROP TABLE IF EXISTS patients;

        CREATE TABLE patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth DATE,
            gender TEXT CHECK (gender IN ('M', 'F')),
            city TEXT,
            registered_date DATE
        );

        CREATE TABLE doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            department TEXT NOT NULL,
            phone TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date DATETIME NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            treatment_name TEXT NOT NULL,
            cost REAL NOT NULL,
            duration_minutes INTEGER NOT NULL,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        );

        CREATE TABLE invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            invoice_date DATE NOT NULL,
            total_amount REAL NOT NULL,
            paid_amount REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE INDEX idx_patients_city ON patients(city);
        CREATE INDEX idx_appointments_date ON appointments(appointment_date);
        CREATE INDEX idx_appointments_status ON appointments(status);
        CREATE INDEX idx_appointments_doctor ON appointments(doctor_id);
        CREATE INDEX idx_appointments_patient ON appointments(patient_id);
        CREATE INDEX idx_invoices_status ON invoices(status);
        CREATE INDEX idx_invoices_date ON invoices(invoice_date);
        """
    )


def seed_doctors(connection: sqlite3.Connection) -> list[int]:
    rows: list[tuple[str, str, str, str]] = []
    for specialization in SPECIALIZATIONS:
        for name, phone in DOCTOR_PROFILES[specialization]:
            rows.append((name, specialization, DEPARTMENTS[specialization], phone))

    connection.executemany(
        """
        INSERT INTO doctors (name, specialization, department, phone)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    return [row[0] for row in connection.execute("SELECT id FROM doctors").fetchall()]


def seed_patients(connection: sqlite3.Connection) -> list[int]:
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    rows: list[tuple[str, str, str | None, str | None, str, str, str, str]] = []
    for _ in range(PATIENT_COUNT):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        dob = random_date(date(1948, 1, 1), date(2018, 12, 31))
        rows.append(
            (
                first_name,
                last_name,
                maybe_email(first_name, last_name),
                maybe_phone(),
                dob.isoformat(),
                random.choice(["M", "F"]),
                random.choice(CITIES),
                random_date(one_year_ago, today).isoformat(),
            )
        )

    connection.executemany(
        """
        INSERT INTO patients (
            first_name, last_name, email, phone, date_of_birth, gender, city, registered_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return [row[0] for row in connection.execute("SELECT id FROM patients").fetchall()]


def seed_appointments(
    connection: sqlite3.Connection,
    patient_ids: list[int],
    doctor_ids: list[int],
) -> list[sqlite3.Row]:
    now = datetime.now()
    one_year_ago = now - timedelta(days=365)

    heavy_patients = random.sample(patient_ids, 35)
    heavy_doctors = doctor_ids[:5]

    rows: list[tuple[int, int, str, str, str | None]] = []
    for _ in range(APPOINTMENT_COUNT):
        patient_id = random.choice(heavy_patients) if random.random() < 0.38 else random.choice(patient_ids)
        doctor_id = random.choice(heavy_doctors) if random.random() < 0.45 else random.choice(doctor_ids)
        appointment_date = random_datetime(one_year_ago, now)
        status = random.choices(APPOINTMENT_STATUSES, weights=APPOINTMENT_WEIGHTS, k=1)[0]
        rows.append(
            (
                patient_id,
                doctor_id,
                appointment_date.isoformat(sep=" "),
                status,
                random.choice(NOTES),
            )
        )

    connection.executemany(
        """
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, status, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )
    return connection.execute(
        "SELECT id, doctor_id, status FROM appointments ORDER BY id"
    ).fetchall()


def seed_treatments(connection: sqlite3.Connection, appointments: list[sqlite3.Row]) -> None:
    doctor_specialization = {
        row["id"]: row["specialization"]
        for row in connection.execute("SELECT id, specialization FROM doctors").fetchall()
    }

    completed = [row for row in appointments if row["status"] == "Completed"]
    chosen = random.choices(completed, k=TREATMENT_COUNT)

    rows: list[tuple[int, str, float, int]] = []
    for appointment in chosen:
        specialization = doctor_specialization[appointment["doctor_id"]]
        treatment_name, cost_range, duration_range = random.choice(
            TREATMENTS_BY_SPECIALIZATION[specialization]
        )
        rows.append(
            (
                appointment["id"],
                treatment_name,
                round(random.uniform(*cost_range), 2),
                random.randint(*duration_range),
            )
        )

    connection.executemany(
        """
        INSERT INTO treatments (appointment_id, treatment_name, cost, duration_minutes)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def seed_invoices(connection: sqlite3.Connection, patient_ids: list[int]) -> None:
    today = date.today()
    one_year_ago = today - timedelta(days=365)

    frequent_patients = random.sample(patient_ids, 50)
    invoice_patients = frequent_patients + patient_ids

    rows: list[tuple[int, str, float, float, str]] = []
    for _ in range(INVOICE_COUNT):
        patient_id = random.choice(invoice_patients)
        total_amount = round(random.uniform(120, 5000), 2)
        status = random.choices(INVOICE_STATUSES, weights=INVOICE_WEIGHTS, k=1)[0]
        if status == "Paid":
            paid_amount = total_amount
        elif status == "Pending":
            paid_amount = round(random.uniform(total_amount * 0.2, total_amount * 0.85), 2)
        else:
            paid_amount = round(random.uniform(0, total_amount * 0.4), 2)

        rows.append(
            (
                patient_id,
                random_date(one_year_ago, today).isoformat(),
                total_amount,
                paid_amount,
                status,
            )
        )

    connection.executemany(
        """
        INSERT INTO invoices (patient_id, invoice_date, total_amount, paid_amount, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )


def seed_database() -> SeedSummary:
    random.seed(RANDOM_SEED)

    with create_connection() as connection:
        recreate_schema(connection)

        doctor_ids = seed_doctors(connection)
        patient_ids = seed_patients(connection)
        appointments = seed_appointments(connection, patient_ids, doctor_ids)
        seed_treatments(connection, appointments)
        seed_invoices(connection, patient_ids)
        connection.commit()

        summary = SeedSummary(
            patients=connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            doctors=connection.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
            appointments=connection.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
            treatments=connection.execute("SELECT COUNT(*) FROM treatments").fetchone()[0],
            invoices=connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
        )

    return summary


def main() -> None:
    summary = seed_database()
    print(f"Database created at {DB_PATH.resolve()}")
    print(
        "Created "
        f"{summary.patients} patients, "
        f"{summary.doctors} doctors, "
        f"{summary.appointments} appointments, "
        f"{summary.treatments} treatments, "
        f"{summary.invoices} invoices."
    )


if __name__ == "__main__":
    main()
