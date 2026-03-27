"""
setup_database.py  (async)
==========================
Creates clinic.db with full schema and realistic dummy data.
All database writes use aiosqlite (non-blocking).

Run:
    python setup_database.py
"""

import asyncio
import random
from datetime import date, datetime, timedelta
from typing import Optional

import aiosqlite

DB_PATH = "clinic.db"

# ──────────────────────────────────────────────────────────────────────────
# Schema DDL
# ──────────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    date_of_birth   DATE,
    gender          TEXT,
    city            TEXT,
    registered_date DATE
);

CREATE TABLE IF NOT EXISTS doctors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    specialization  TEXT,
    department      TEXT,
    phone           TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER,
    doctor_id        INTEGER,
    appointment_date DATETIME,
    status           TEXT,
    notes            TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id)  REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS treatments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id   INTEGER,
    treatment_name   TEXT,
    cost             REAL,
    duration_minutes INTEGER,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER,
    invoice_date DATE,
    total_amount REAL,
    paid_amount  REAL,
    status       TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
"""

# ──────────────────────────────────────────────────────────────────────────
# Seed data pools
# ──────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav","Aditi","Amit","Ananya","Anjali","Arjun","Deepa","Farhan","Gaurav",
    "Isha","Karan","Kavya","Manish","Meera","Mohit","Neha","Nikhil","Pooja",
    "Priya","Rahul","Rajesh","Riya","Rohit","Sana","Sanjay","Shreya","Suresh",
    "Tanvi","Uday","Vandana","Vikram","Vishal","Yogesh","Zara","Aisha","Bunty",
    "Chetan","Divya","Ekta","Faisal","Geeta","Harish","Irfan","Jyoti","Kishore",
    "Lalit","Maya","Nanda","Omkar","Payal",
]
LAST_NAMES = [
    "Sharma","Verma","Singh","Patel","Gupta","Kumar","Joshi","Mehta","Rao",
    "Nair","Iyer","Reddy","Bhat","Kapoor","Malhotra","Agarwal","Chauhan",
    "Pandey","Tiwari","Mishra","Shukla","Dubey","Saxena","Srivastava","Yadav",
]
CITIES = [
    "Mumbai","Pune","Bangalore","Delhi","Chennai",
    "Hyderabad","Ahmedabad","Kolkata","Jaipur","Surat",
]
SPECIALIZATIONS  = ["Dermatology","Cardiology","Orthopedics","General","Pediatrics"]
DEPARTMENTS      = {
    "Dermatology": "Skin Care",
    "Cardiology":  "Heart & Vascular",
    "Orthopedics": "Bone & Joint",
    "General":     "General Medicine",
    "Pediatrics":  "Child Health",
}
APPT_STATUSES        = ["Scheduled","Completed","Cancelled","No-Show"]
APPT_STATUS_WEIGHTS  = [10, 55, 20, 15]
INVOICE_STATUSES     = ["Paid","Pending","Overdue"]
INVOICE_WEIGHTS      = [55, 25, 20]
TREATMENT_NAMES      = {
    "Dermatology": ["Chemical Peel","Laser Therapy","Acne Treatment","Mole Removal","Skin Biopsy"],
    "Cardiology":  ["ECG","Echocardiogram","Stress Test","Angioplasty","Holter Monitor"],
    "Orthopedics": ["X-Ray","MRI Scan","Physiotherapy","Cast Application","Joint Injection"],
    "General":     ["General Checkup","Blood Test","BP Monitoring","Vaccination","Wound Dressing"],
    "Pediatrics":  ["Child Checkup","Vaccination","Nebulization","Growth Assessment","Hearing Test"],
}
NOTES_POOL = [
    "Patient reported mild discomfort.",
    "Follow-up required in 2 weeks.",
    "All vitals normal.",
    "Patient is responding well to treatment.",
    "Referred to specialist.",
    None, None, None,   # realistic NULLs
]


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _rand_date(start: date, end: date) -> date:
    return start + timedelta(days=random.randint(0, (end - start).days))


def _rand_datetime(start: date, end: date) -> datetime:
    d    = _rand_date(start, end)
    hour = random.choice([9,10,11,12,14,15,16,17])
    mins = random.choice([0,15,30,45])
    return datetime(d.year, d.month, d.day, hour, mins)

def _phone_or_null() -> Optional[str]:
    if random.random() < 0.15:
        return None
    return f"+91-{random.randint(70000,99999)}-{random.randint(10000,99999)}"


def _email_or_null(first: str, last: str) -> Optional[str]:
    if random.random() < 0.10:
        return None
    domains = ["gmail.com","yahoo.com","hotmail.com","outlook.com"]
    return f"{first.lower()}.{last.lower()}{random.randint(1,99)}@{random.choice(domains)}"


# ──────────────────────────────────────────────────────────────────────────
# Async build function
# ──────────────────────────────────────────────────────────────────────────

async def build_database() -> None:
    today    = date.today()
    year_ago = today - timedelta(days=365)

    async with aiosqlite.connect(DB_PATH) as db:
        # ── Schema ───────────────────────────────────────────────────────
        await db.executescript(SCHEMA)
        await db.commit()

        # ── Doctors (15, 3 per specialization) ───────────────────────────
        used_names: set[str] = set()
        doctor_rows: list[tuple] = []
        for spec in SPECIALIZATIONS:
            for _ in range(3):
                while True:
                    name = f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
                    if name not in used_names:
                        used_names.add(name)
                        break
                doctor_rows.append((name, spec, DEPARTMENTS[spec], _phone_or_null()))

        await db.executemany(
            "INSERT INTO doctors (name, specialization, department, phone) VALUES (?,?,?,?)",
            doctor_rows,
        )
        await db.commit()

        async with db.execute("SELECT id, specialization FROM doctors") as cur:
            doctors = await cur.fetchall()   # [(id, spec), …]

        # ── Patients (200) ───────────────────────────────────────────────
        patient_rows: list[tuple] = []
        for _ in range(200):
            fn  = random.choice(FIRST_NAMES)
            ln  = random.choice(LAST_NAMES)
            dob = _rand_date(date(1950,1,1), date(2010,12,31))
            reg = _rand_date(year_ago, today)
            patient_rows.append((
                fn, ln,
                _email_or_null(fn, ln),
                _phone_or_null(),
                dob.isoformat(),
                random.choice(["M","F"]),
                random.choice(CITIES),
                reg.isoformat(),
            ))

        await db.executemany(
            """INSERT INTO patients
               (first_name,last_name,email,phone,date_of_birth,gender,city,registered_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            patient_rows,
        )
        await db.commit()

        async with db.execute("SELECT id FROM patients") as cur:
            patient_ids = [r[0] for r in await cur.fetchall()]

        # ── Appointments (500) ───────────────────────────────────────────
        repeat_patients = random.sample(patient_ids, 30)
        appt_rows: list[tuple] = []
        for _ in range(500):
            pid     = random.choice(repeat_patients) if random.random() < 0.25 \
                      else random.choice(patient_ids)
            doc_id  = random.choice(doctors)[0]
            appt_dt = _rand_datetime(year_ago, today)
            status  = random.choices(APPT_STATUSES, weights=APPT_STATUS_WEIGHTS)[0]
            notes   = random.choice(NOTES_POOL)
            appt_rows.append((pid, doc_id, appt_dt.isoformat(), status, notes))

        await db.executemany(
            "INSERT INTO appointments (patient_id,doctor_id,appointment_date,status,notes)"
            " VALUES (?,?,?,?,?)",
            appt_rows,
        )
        await db.commit()

        # ── Treatments (350, completed appointments only) ─────────────────
        async with db.execute(
            "SELECT id, doctor_id FROM appointments WHERE status='Completed'"
        ) as cur:
            completed = await cur.fetchall()

        async with db.execute("SELECT id, specialization FROM doctors") as cur:
            doc_spec: dict[int, str] = {r[0]: r[1] for r in await cur.fetchall()}

        random.shuffle(completed)
        treatment_rows: list[tuple] = []
        for appt_id, doc_id in completed[:350]:
            spec  = doc_spec.get(doc_id, "General")
            tname = random.choice(TREATMENT_NAMES[spec])
            cost  = round(random.uniform(50, 5000), 2)
            dur   = random.randint(15, 120)
            treatment_rows.append((appt_id, tname, cost, dur))

        await db.executemany(
            "INSERT INTO treatments (appointment_id,treatment_name,cost,duration_minutes)"
            " VALUES (?,?,?,?)",
            treatment_rows,
        )
        await db.commit()

        # ── Invoices (300) ────────────────────────────────────────────────
        invoice_rows: list[tuple] = []
        for pid in random.choices(patient_ids, k=300):
            inv_date   = _rand_date(year_ago, today)
            total      = round(random.uniform(100, 8000), 2)
            inv_status = random.choices(INVOICE_STATUSES, weights=INVOICE_WEIGHTS)[0]
            paid       = total if inv_status == "Paid" \
                         else round(random.uniform(0, total * 0.5), 2)
            invoice_rows.append((pid, inv_date.isoformat(), total, paid, inv_status))

        await db.executemany(
            "INSERT INTO invoices (patient_id,invoice_date,total_amount,paid_amount,status)"
            " VALUES (?,?,?,?,?)",
            invoice_rows,
        )
        await db.commit()

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"✅ Database created: {DB_PATH}")
    print(f"   Created {len(patient_rows)} patients")
    print(f"   Created {len(doctor_rows)} doctors")
    print(f"   Created {len(appt_rows)} appointments")
    print(f"   Created {len(treatment_rows)} treatments")
    print(f"   Created {len(invoice_rows)} invoices")


# ──────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(build_database())
