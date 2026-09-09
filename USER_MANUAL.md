# EXCUSE PATTERN AI — User Manual v2.1

> **System**: Excuse Pattern Recognition AI (EPAI)  
> **Version**: 9.5 · Neural Intelligence Engine  
> **Stack**: Python 3.11 · Flask · Supabase · Groq LLaMA-3.3-70B · Redis/RQ  
> **Theme**: Neural Glassmorphism · Lucide Icons  

---

## WHAT IS EXCUSE PATTERN AI?

**Definition (one line):**  
> *Excuse Pattern AI is a system that detects fake or suspicious delay excuses for task management using AI, NLP, and behavioral scoring.*

**In plain terms:**  
When an employee submits a reason for being late on a task, the system:
1. Reads the text using Natural Language Processing (NLP)
2. Classifies the excuse category (e.g., "Personal Emergency", "Technical Issue")
3. Calculates an **Authenticity Score** (0–100)
4. Issues a **Verdict**: `REAL`, `SUSPICIOUS`, or `FAKE`
5. Logs it to the database and generates an AI Report

---

## GLOSSARY — KEY TERMS (Single-Word Definitions)

| Term | Definition |
|---|---|
| **Excuse** | A reason submitted for a task delay |
| **Verdict** | AI's final judgment: REAL / SUSPICIOUS / FAKE |
| **Authenticity Score** | % likelihood the excuse is genuine (0 = fake, 100 = real) |
| **Avoidance Score** | % of evasive language detected in the reason text |
| **Risk Level** | Severity classification: Low / Medium / High |
| **Delay** | A task submitted/completed after its deadline |
| **Sentiment** | Emotional tone of the excuse text (Positive / Negative / Neutral) |
| **Confidence** | AI certainty % in its own category classification |
| **Pattern Frequency** | How many delays a user has submitted in total |
| **Neural Sensitivity** | Admin-controlled strictness of AI analysis (0–10 scale) |
| **Report ID** | Unique identifier: `EPAI-YYMMDD-HHMMxM-U{id}-T{id}` |
| **Operative** | System term for "user/employee" |
| **Anomaly** | System term for "delay submission" |
| **Contagion Alert** | When multiple employees show simultaneous behavioral drift |
| **Z-Score Drift** | Statistical deviation of a user's behavior from their own baseline |
| **Task Matrix** | The full list of all tasks in the system |
| **Proof Document** | File uploaded as evidence supporting a delay excuse |

---

## USER ROLES

### 👤 Employee — The Contributor
**What they can do:**
- View tasks assigned to them
- Submit delays with reasons and proof documents
- View their own AI analysis results and verdict
- Chat with the AI assistant
- View their profile and performance metrics
- Download their own task AI reports

**Example:**  
> John is assigned "Submit Q3 Report" with deadline March 5. He misses it. He opens the task → clicks **Signal Anomaly** → types his reason → optionally uploads a document → submits. AI processes the excuse and shows a verdict.

---

### 👔 Manager — The Strategist
**What they can do:**
- Everything an Employee can
- Create, edit, and assign tasks to employees
- View all team members' tasks and delays
- Access team analytics and intelligence reports
- Generate AI Reports for any team member's tasks

**Example:**  
> Sarah manages 5 employees. She goes to Analytics → sees that 3 employees have submitted delays this week. She checks the Risk Distribution chart and opens individual task reports to review AI verdicts.

---

### 👑 Admin — The Controller
**What they can do:**
- Everything a Manager can
- Add, edit, or delete any user account
- Access the full Admin Panel
- **Generate AI Reports for ALL users and tasks** (exclusive feature)
- Adjust Neural Sensitivity settings
- View real-time system logs and audit trail
- Configure AI confidence thresholds

**Example:**  
> Admin navigates to Admin Panel → clicks **AI Reports** tab → sees all operatives listed → clicks **View Report** for any user → full consolidated delay analysis report opens.

---

### 🛡️ ROLE NORMALIZATION (New in v2.1)
The system now uses standardized, case-insensitive role mapping. Whether a user is registered as `Admin`, `admin`, or `ADMIN`, the system internally normalizes this to ensure consistent permission checks and data access.

---

## CORE FEATURES — HOW EACH WORKS

---

### 1. DASHBOARD
**Definition:** The home screen showing real-time personal performance metrics.

**What you see:**
- Total tasks assigned
- Pending / completed / delayed counts
- Behavioral Intelligence Score (BIS)
- Recent activity log

**Example:**  
> Employee opens the app → sees "3 Pending Tasks", "Authenticity Score: 78%", "Risk Level: LOW" at a glance.

---

### 2. TASK MATRIX
**Definition:** The master list of all tasks — filterable by status, priority, and assignee.

**How it works:**
- Tasks are color-coded by status: `PENDING` (yellow), `COMPLETED` (green), `DELAYED` (red)
- Click any task row → opens Task Details
- Managers/Admins see all tasks; Employees see only their own

**Example:**  
> Manager searches "High Priority" tasks filtered by "Delayed" → sees 2 overdue tasks → clicks each to review the AI delay analysis.

---

### 3. TASK DETAILS PAGE
**Definition:** The full detail view of a single task including all AI analysis results.

**Sections:**
| Section | Content |
|---|---|
| Task Info | Title, description, priority, deadline, assigned to |
| Action Bar | Edit, Submit Delay, View AI Report buttons |
| Delay Analysis | AI verdict, authenticity score, sentiment, category |
| Task Documents | Uploaded files (proof documents, resources) |

**How to submit a delay (Signal Anomaly):**
1. Open any task → click **Signal Anomaly** (red button)
2. Type your delay reason (minimum 20 characters)
3. Optionally drag-and-drop a proof document (PDF, image, doc — max 10MB)
4. Click **Submit Anomaly**
5. AI processes instantly → verdict shown on the task page

**Example:**  
> "My laptop crashed and corrupted all project files. I have attached a screenshot of the error."  
> → AI classifies: **Technical Issue** · Confidence 82% · Authenticity 71% · Verdict: **REAL**

---

### 4. AI DELAY ANALYSIS ENGINE
**Definition:** The core AI pipeline that processes every delay excuse submitted.

**How it works (step by step):**

```
Excuse Text Submitted
        ↓
[Step 1] NLP Preprocessing — tokenize, clean text
        ↓
[Step 2] Category Classification — ML model assigns category
        (e.g., Personal Emergency, Technical Issue, Workload Overload)
        ↓
[Step 3] Sentiment Analysis — TextBlob measures emotional polarity
        (Positive / Negative / Neutral, -1.0 to +1.0)
        ↓
[Step 4] Authenticity Scoring — composite formula:
        • Specificity of language
        • Emotional consistency
        • Historical pattern match
        • Vagueness penalty
        ↓
[Step 5] Verdict Classification:
        • REAL        → Authenticity ≥ 65%, low evasion
        • SUSPICIOUS  → Authenticity 40–64%, some evasion
        • FAKE        → Authenticity < 40%, high evasion
        ↓
[Step 6] Risk Level Assignment:
        • Low    → 0–3 delays on record, high authenticity
        • Medium → 4–7 delays or moderate authenticity
        • High   → 8+ delays or low authenticity
        ↓
[Step 7] Results stored to database + Report generated
```

**Example:**  
> Excuse: *"I was sick."*  
> → Too vague → Authenticity 28% → Fake Score 72 → **FAKE** · High Risk

> Excuse: *"Server outage at AWS us-east-1 from 9AM-3PM blocked deployment. I have attached the AWS status page screenshot."*  
> → Specific, verifiable → Authenticity 88% → **REAL** · Low Risk

---

### 5. AI VERDICT BADGE
**Definition:** The colored badge displayed on task details showing the AI's final judgment.

| Badge | Color | Meaning |
|---|---|---|
| ✅ REAL | Green | Excuse is genuine and verifiable |
| ⚠️ SUSPICIOUS | Amber | Excuse is vague or inconsistent |
| ❌ FAKE | Red | Excuse shows evasion patterns |

---

### 6. PROOF DOCUMENT UPLOAD
**Definition:** A file the employee uploads to back up their delay excuse.

**How it works:**
- Located inside the **Signal Anomaly** modal (delay submission form)
- Drag-and-drop zone OR click to browse files
- Supported: PDF, JPG, PNG, DOCX, MP4, ZIP (max 10MB)
- File stored securely in Supabase Storage
- Linked to the delay record and shown in the AI Report

**Example:**  
> Employee claims power outage → uploads a photo of the outage notification from the electricity provider → AI raises authenticity score.

---

### 7. TASK DOCUMENTS PANEL
**Definition:** A dedicated section on the Task Details page for uploading general task-related files (not just proof — resources, references, deliverables).

**How it works:**
- Drag-and-drop any file into the **TASK_DOCUMENTS** panel
- Files are stored in Supabase under the task's folder
- Displayed with file icon, name, size, and upload timestamp
- Accessible to both assignee and manager

---

### 8. AI REPORT — SINGLE TASK
**Definition:** A formal A4-style document showing the full AI analysis of one specific task's delay.

**Report Sections:**

| # | Section | Contents |
|---|---|---|
| 01 | Employee Information | Name, email, role, job title |
| 02 | Task Information | Title, priority, complexity, deadline, status |
| 03 | Delay Details | Duration, category, confidence, sentiment, verdict |
| 04 | Supporting Document | Proof file name and upload time |
| 05 | AI Evaluation Summary | Authenticity, Avoidance, Reliability score bars |
| 06 | AI Conclusion | Groq LLaMA-3.3-70B generated paragraph |

**Report ID Format:**  
`EPAI-YYMMDD-HHMMxM-U{user_id}-T{task_id}`  
Example: `EPAI-260303-1037AM-U17-T45`

**How to access:**
- Admin Panel → AI Reports tab → **View Report** (teal button)
- Task Details page → **AI Report** button (only if a delay exists)

**Example output:**  
> *"Nadesh has recorded 3 delays predominantly attributed to 'Technical Issue' patterns. Behavioral analysis indicates a low risk profile with an average sentiment polarity of 0.12. Current performance trajectory suggests improvement with sustained task completion consistency."*

---

### 9. AI REPORT — CONSOLIDATED USER
**Definition:** A single report covering ALL delays submitted by one employee — showing overall patterns, trends, and risk profile.

**Report Sections:**

| # | Section | Contents |
|---|---|---|
| 01 | Employee Information | Name, email, role |
| 02 | Summary Statistics | Total tasks, delays, delay rate %, avg risk, common category |
| 03 | Delay Record History | Table of all delays with days late, category, confidence, risk |
| 04 | AI Conclusion | Overall behavioral assessment across all delays |

**How to access:**
- Admin Panel → AI Reports tab → **View Report** next to any user row

**Example:**  
> Admin views Nadesh's consolidated report → sees: 10 tasks, 4 delays (40% delay rate), most common category: "Workload Overload", avg risk score: 45%, conclusion: "Moderate risk profile, recommend workload review."

---

### 10. PDF DOWNLOAD
**Definition:** The ability to download any AI Report as a professionally formatted A4 PDF.

**Format:** Word-style document with:  
- Navy header bar (EXCUSE PATTERN AI branding)
- White background, black text
- Section headers with blue left accent bar
- Alternating row table (delay records)
- Page numbers and confidentiality footer

**How to use:**
- Report View page → click **Download PDF** (indigo button)
- Admin Panel → AI Reports → **PDF** button (purple button)

---

### 11. PRINT
**Definition:** Print the on-screen report using the browser's native print dialog.

**How to use:**
- Report View page → click **🖨️ Print** (purple button)
- Browser print dialog opens → select your printer or "Microsoft Print to PDF"
- Paper size automatically set to **A4 Portrait**
- Navigation/buttons hidden — only report content prints

---

### 12. ANALYTICS — INTELLIGENCE DASHBOARD
**Definition:** Visual KPIs and AI-driven charts showing workforce-level behavioral patterns.

**Sub-sections:**

| Page | What it shows |
|---|---|
| **Overview** | Authenticity gauge, risk distribution matrix, delay trends |
| **AI Intelligence** | Behavioral archetypes, pattern frequency heatmaps |
| **Trends** | Time-series performance graphs per user and team |

**Example:**  
> Analytics Overview → Risk Distribution chart shows: 60% Low Risk / 30% Medium / 10% High → Admin adjusts Neural Sensitivity upward to flag more borderline cases.

---

### 13. AI CHATBOT
**Definition:** An integrated conversational AI assistant (Groq LLaMA-3.3-70B) aware of the system context.

**What it can do:**
- Answer questions about your own performance
- Explain AI verdicts in plain language
- Give quick insights ("What's my authenticity score?")
- Help frame task delays more clearly
- Respond to system status queries

**Example:**  
> Employee types: *"Am I high risk?"*  
> Chatbot: *"Your current Authenticity Signal is 74%. You have 1 low-risk delay submission. Trend: stable."*

---

### 14. ADMIN PANEL
**Definition:** The exclusive admin control center with full system visibility and user management.

**Tabs:**

| Tab | Purpose |
|---|---|
| **Operatives** | View all users, add/edit/delete accounts, view AI Report per user |
| **Task Matrix** | View all tasks across the entire organization |
| **AI Reports** | Generate View + PDF reports for every user and task |
| **System Logs** | Searchable audit trail of all system events |
| **Intelligence Matrix** | Adjust Neural Sensitivity, AI confidence, detection window |

---

### ⚡ ASYNC ARCHITECTURE (Enhanced Scalability)
**Definition:** Background processing system to handle heavy AI and analytics tasks without slowing down the UI.

**How it works:**
- **Task Offloading:** Complex calculations (like AI report generation and global analytics) are moved to background workers.
- **Caching:** The system uses Redis (or a ThreadPoolExecutor fallback) to cache AI results, reducing computation per request by up to 80%.
- **Concurrent Users:** This architecture allows the system to scale to 20+ concurrent users with sub-second response times.

---

### 🔐 SECURITY HARDENING (RLS & Audit)
**Definition:** Level 3 security integration protecting all database tables.

**Features:**
- **Row Level Security (RLS):** All database tables have RLS enabled. This prevents unauthorized direct access via Supabase APIs.
- **Security Invoker Views:** Database views (like `task_statistics`) are configured with `security_invoker = true` to respect the calling user's permissions.
- **Audit Logging:** Every administrative action is logged to the `audit_logs` table for compliance and security tracking.

---

### 🎨 PREMIUM UI & GLASSMORPHISM
**Definition:** High-impact visual design focused on "Neural Glassmorphism."

**Visual Tokens:**
- **Backgrounds:** Dynamic gradients with frosted-glass overlays.
- **Typography:** Using "Inter" and "Outfit" fonts for a modern, tech-forward feel.
- **Micro-animations:** Subtle hover states and loading transitions using Framer Motion-inspired CSS.
- **Responsive Layouts:** Full support for mobile, tablet, and ultra-wide desktop views.

---

**AI Reports Tab — How to use:**
1. Login as Admin → go to Admin Panel
2. Click **AI Reports** tab (teal, highlighted)
3. **CONSOLIDATED USER REPORTS** section: click **View Report** next to any employee
4. **SINGLE TASK REPORTS** section: click **View Report** or **PDF** next to any task

---

### 15. PROFILE & SETTINGS
**Definition:** Personal account management pages for all users.

**Profile page includes:**
- Personal info (name, email, job role, department)
- Performance metrics (BIS score, delay history)
- Account settings (change password, notification preferences)

**Settings page includes:**
- Theme and display preferences
- Notification toggles
- Security settings

---

## COMPLETE USER JOURNEY — EXAMPLE

> **Scenario:** Nadesh (Employee) misses a task deadline. Admin reviews and generates a report.

```
1. EMPLOYEE SIDE
   ─────────────
   Task "Q3 Report" is marked overdue
   Nadesh opens Task Details
   Clicks "Signal Anomaly" (red button)
   Types: "Server outage blocked all cloud access for 6 hours"
   Uploads: server_outage_screenshot.png
   Clicks "Submit Anomaly"

2. AI PROCESSING (instant)
   ──────────────────────
   NLP classifies: Technical Issue (confidence 87%)
   Authenticity Score: 76%
   Sentiment: Neutral (0.08)
   Verdict: REAL
   Risk Level: Low

3. TASK PAGE UPDATES
   ──────────────────
   Green "REAL" badge appears
   Score bars animate in
   "AI Report" button appears in action bar

4. ADMIN REVIEW
   ─────────────
   Admin opens Admin Panel → AI Reports tab
   Clicks "View Report" next to Nadesh
   Consolidated report shows: 5 tasks, 2 delays, 40% delay rate
   Clicks "PDF" → downloads A4 Word-style report
   Prints for HR file
```

---

## FREQUENTLY ASKED QUESTIONS

**Q: Why is my excuse marked FAKE?**  
A: The AI detected vague, non-specific language. Add concrete details — dates, system names, error messages, or attach a proof document to raise your authenticity score.

**Q: Can I resubmit a delay?**  
A: No. Once submitted, the analysis is locked for audit integrity. Contact your manager if there's an error.

**Q: Why does the AI Report button not appear?**  
A: The AI Report button only appears on tasks that have had a delay submitted. Complete a delay submission first.

**Q: Who can see my reports?**  
A: You can see your own task reports. Managers see their team's reports. Admins can see all reports.

**Q: What is the Fake Score?**  
A: A number 0–100 measuring how evasive the excuse language is. Higher = more fake-sounding. Below 35 = REAL verdict.

**Q: What triggers a High Risk flag?**  
A: 8+ delays on record, or authenticity consistently below 40%, or a single delay with fake score above 70.

**Q: What is Neural Sensitivity?**  
A: Admin-controlled strictness (0–10). Higher value = AI flags more excuses as suspicious. Default 8.5 (Aggressive mode).

---

*Document version: 2.1 · Updated: March 2026 · EXCUSE PATTERN AI Intelligence Engine v9.5*
