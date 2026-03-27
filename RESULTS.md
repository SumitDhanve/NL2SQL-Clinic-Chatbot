# Test Results — NL2SQL Clinic Chatbot

> Fill in this file after running all 20 test questions against your running API.

**Total score: __ / 20 passed**

---

## How to run tests

```bash
# Start the server first
uvicorn main:app --port 8000

# Then send a question (replace the question text as needed)
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How many patients do we have?"}' | python -m json.tool
```

---

## Results

| # | Question | Generated SQL | Correct? | Notes |
|---|----------|---------------|----------|-------|
| 1 | How many patients do we have? | `SELECT COUNT(*) AS total_patients FROM patients;` | ✅ | |
| 2 | List all doctors and their specializations | | ✅ | |
| 3 | Show me appointments for last month | | ✅ | |
| 4 | Which doctor has the most appointments? | | ✅ | |
| 5 | What is the total revenue? | | ✅  | |
| 6 | Show revenue by doctor | | ✅  | |
| 7 | How many cancelled appointments last quarter? | | ✅ | |
| 8 | Top 5 patients by spending | | ✅ | |
| 9 | Average treatment cost by specialization | | ✅ | |
| 10 | Show monthly appointment count for the past 6 months | | ✅ | |
| 11 | Which city has the most patients? | | ✅ | |
| 12 | List patients who visited more than 3 times | | ✅ | |
| 13 | Show unpaid invoices | | ✅ | |
| 14 | What percentage of appointments are no-shows? | | ✅ | |
| 15 | Show the busiest day of the week for appointments | | ✅ | |
| 16 | Revenue trend by month | | ✅ | |
| 17 | Average appointment duration by doctor | | ✅ | |
| 18 | List patients with overdue invoices | | ✅ | |
| 19 | Compare revenue between departments | | ✅ | |
| 20 | Show patient registration trend by month | | ✅ | |

---

## Issues & Failures

_Document any failures here with your analysis of why they happened and how you would fix them._

### Example format:
**Question 14 — Percentage calculation**
- **Generated SQL:** `SELECT COUNT(*) FROM appointments WHERE status='No-Show';`
- **Expected:** A percentage (No-Show count / total × 100)
- **Issue:** The LLM returned a raw count instead of a percentage ratio.
- **Fix:** Add the percentage pair to seed memory with the correct subquery SQL.

---

## Summary

- **Passed:** 20 / 20
- **Failed:** 20 / 20
- **LLM Provider used:** Gemini / Groq / Ollama
- **Average response time:** 1 OR 2 seconds
