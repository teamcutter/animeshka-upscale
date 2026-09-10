# Team Agreement — Internal Work Regulations

> **MINISTRY OF SCIENCE AND HIGHER EDUCATION OF THE REPUBLIC OF KAZAKHSTAN**
> **KAZAKH-GERMAN UNIVERSITY — Faculty of Engineering and Information Technology**
>
> **Project:** Photo and Video Quality Enhancement Using AI Models (Animeshka Upscale)
> **Team:** Banum, Gleb, Maksim, Ruslan | **Version:** 1.0 from 08.09.2026 | **Location:** Almaty, 2026

Agreement is adopted unanimously and binding for the whole Softproject semester. Covers communication, roles, violations/sanctions, and exclusion procedure.

---

## 1. Communication Channels & Response Time

| Channel | Purpose | SLA | Owner |
|---------|---------|-----|-------|
| **Telegram team chat** | Main channel: operational questions, short statuses, task agreements | ≤ 12h on weekdays 09:00–22:00 | Every member |
| **Online meeting (Google Meet / Zoom)** | Weekly sync Tue + Fri: blockers, demo of intermediate results | Mandatory attendance, delay ≤ 10 min | Organized by Банум (sprint coordinator) |
| **Git repository (Issues / PRs / commits)** | Formal task tracking, code review, decision history | PR review ≤ 24h after request | PR author assigns reviewer; reviewer — second backend or frontend depending on block |
| **E-mail / teacher channel** | Official communication with curator, discipline, report delivery | ≤ 24h | Банум (coordinator); in absence — any member |

> Silence > 24h in work chat without prior notice of unavailability (illness, force majeure, trip) = violation (§3).
> Planned unavailability (> 12h on a weekday) must be announced in chat ≥ 6h in advance.

---

## 2. Roles & Responsibilities

Each member has one primary zone + one backup zone to switch to on overload/absence. Roles are fixed in Sprint 1 research memo and confirmed here for the whole semester; changes only by unanimous vote with chat record.

| Member | Role | Primary zone | Backup zone |
|--------|------|--------------|-------------|
| **Banum** | Data Engineer / Data Scientist, sprint coordinator | Dataset, quality metrics (PSNR/SSIM/VMAF), ML QoP model, Grafana dashboard, docs | Frontend analytics (with Максим) |
| **Gleb** | Backend developer | REST API (FastAPI), PostgreSQL, backend↔inference wiring, deploy | Inference pipeline (with Руслан) |
| **Ruslan** | Backend developer (inference) | Inference module (2K/4K), local Grafana run, test runs & result handover | REST API (with Глеб) |
| **Maksim** | Frontend developer | App UI, before/after pairs, dashboard embed, backend API integration | Dashboard assembly (with Банум) |

Sprint coordinator (Banum) owns docs, task tracking and teacher communication, but **cannot make product decisions alone** — all key decisions are collegial.

---

## 3. Violation Levels & Sanctions

Violations are logged by the coordinator (Банум) in team chat with date, substance and level. Any member may contest — decided by vote of remaining members (simple majority).

| Level | Violation | Examples | Sanction |
|-------|-----------|----------|----------|
| **1 — Minor** | Single comms breach or small delay | Late reply; meeting lateness ≤ 15 min without warning | Verbal remark in chat, log entry |
| **2 — Moderate** | Missed intermediate deadline without warning | Stage task not delivered on time; missed meeting without valid reason | Written warning + takes extra task next stage |
| **3 — Serious** | Repeated L2 or missed sprint-critical deadline | Second consecutive block delay; blocking others by undone task | Share reduction in sprint grade (10–25% by team vote); escalation to coordinator and, on repeat, to teacher |
| **4 — Critical** | Systematic non-participation or gross misconduct (deceit, plagiarism) | No contribution entire sprint; false reporting | Initiate exclusion procedure (§4) |

> Cumulative: **two L2 violations within one sprint → auto-upgraded to L3.**
> L3+ sanctions are reported to the teacher with the sprint report.

---

## 4. Exclusion Procedure

Triggered only on **one L4** or **≥ 3 L3** over the semester. Exclusion is a last resort after warnings/escalation failed.

1. **Grounds recorded** — Coordinator publishes written summary of violations (dates, substance, sanctions already applied) in chat.
2. **Right to respond** — Affected member gets ≥ 48h for written explanation to the team.
3. **Vote** — Exclusion requires **unanimous** vote of all other members (≥ 3 × "for" in a team of 4).
4. **Teacher notification** — Regardless of outcome, case + decision are documented and sent to the teacher for final academic confirmation.
5. **Redistribution** — If excluded, primary + backup zones (§2) are immediately redistributed; coordinator updates project docs and research memo within 48h.

---

Agreement enters force upon confirmation by all members in team chat and lasts until end of semester. Amendments only by unanimous consent with date + version recorded.
