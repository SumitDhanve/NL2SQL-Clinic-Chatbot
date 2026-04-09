# Results

The table below documents the required 20 test questions, representative SQL, and the expected behavior this implementation is designed to support.

| # | Question | Representative SQL | Expected Result |
|---|---|---|---|
| 1 | How many patients do we have? | `SELECT COUNT(*) AS total_patients FROM patients` | Returns patient count |
| 2 | List all doctors and their specializations | `SELECT name, specialization FROM doctors ORDER BY name` | Returns doctor list |
| 3 | Show me appointments for last month | `SELECT id, patient_id, doctor_id, appointment_date, status FROM appointments WHERE appointment_date >= date('now', 'start of month', '-1 month') AND appointment_date < date('now', 'start of month') ORDER BY appointment_date` | Filters last month appointments |
| 4 | Which doctor has the most appointments? | `SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON d.id = a.doctor_id GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1` | Aggregation and ordering |
| 5 | What is the total revenue? | `SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices` | SUM revenue |
| 6 | Show revenue by doctor | `SELECT d.name, ROUND(SUM(t.cost), 2) AS total_revenue FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.id, d.name ORDER BY total_revenue DESC, d.name` | JOIN and GROUP BY |
| 7 | How many cancelled appointments last quarter? | `SELECT COUNT(*) AS cancelled_appointments FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', '-3 months')` | Status and date filter |
| 8 | Top 5 patients by spending | `SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON p.id = i.patient_id GROUP BY p.id, p.first_name, p.last_name ORDER BY total_spending DESC, p.last_name, p.first_name LIMIT 5` | JOIN, ORDER, LIMIT |
| 9 | Average treatment cost by specialization | `SELECT d.specialization, ROUND(AVG(t.cost), 2) AS average_treatment_cost FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.specialization ORDER BY average_treatment_cost DESC, d.specialization` | Multi-table AVG |
| 10 | Show monthly appointment count for the past 6 months | `SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now', '-5 months', 'start of month') GROUP BY strftime('%Y-%m', appointment_date) ORDER BY month` | Date grouping |
| 11 | Which city has the most patients? | `SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1` | GROUP BY and COUNT |
| 12 | List patients who visited more than 3 times | `SELECT p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON p.id = a.patient_id GROUP BY p.id, p.first_name, p.last_name HAVING COUNT(a.id) > 3 ORDER BY visit_count DESC, p.last_name, p.first_name` | HAVING clause |
| 13 | Show unpaid invoices | `SELECT id, patient_id, invoice_date, total_amount, paid_amount, status FROM invoices WHERE status IN ('Pending', 'Overdue') ORDER BY invoice_date DESC` | Status filter |
| 14 | What percentage of appointments are no-shows? | `SELECT ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments` | Percentage calculation |
| 15 | Show the busiest day of the week for appointments | `SELECT CASE strftime('%w', appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END AS day_of_week, COUNT(*) AS appointment_count FROM appointments GROUP BY strftime('%w', appointment_date) ORDER BY appointment_count DESC LIMIT 1` | Date function aggregation |
| 16 | Revenue trend by month | `SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS revenue FROM invoices GROUP BY strftime('%Y-%m', invoice_date) ORDER BY month` | Time-series revenue |
| 17 | Average appointment duration by doctor | `SELECT d.name, ROUND(AVG(t.duration_minutes), 2) AS average_duration_minutes FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.id, d.name ORDER BY average_duration_minutes DESC, d.name` | AVG duration |
| 18 | List patients with overdue invoices | `SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount FROM patients p JOIN invoices i ON p.id = i.patient_id WHERE i.status = 'Overdue' ORDER BY i.invoice_date DESC` | JOIN and filter |
| 19 | Compare revenue between departments | `SELECT d.department, ROUND(SUM(t.cost), 2) AS department_revenue FROM doctors d JOIN appointments a ON d.id = a.doctor_id JOIN treatments t ON a.id = t.appointment_id GROUP BY d.department ORDER BY department_revenue DESC, d.department` | Department revenue comparison |
| 20 | Show patient registration trend by month | `SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS registrations FROM patients GROUP BY strftime('%Y-%m', registered_date) ORDER BY month` | Registration trend |

## Pass Count

Designed target: `20 / 20`

## Notes

- The SQL shown above is the intended correct form for each question.
- In a live run, exact SQL text may differ slightly while still being correct.
- Because this environment does not include installed Vanna and Gemini dependencies by default, end-to-end execution against the live LLM should be verified after `pip install -r requirements.txt` and a valid `.env` are in place.
