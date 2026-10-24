# Campus Resource Intelligence & Sharing System (CRISS)

An enterprise-grade, full-stack college DBMS project combining college-owned academic inventory management with student-to-student peer resource sharing. Built with **Python Flask**, **MySQL 8.0**, **Bootstrap 5**, and **Chart.js**.

---

## Table of Contents
1. [Project Overview & Key Objectives](#1-project-overview--key-objectives)
2. [Technology Stack](#2-technology-stack)
3. [Core Capabilities & Features](#3-core-capabilities--features)
4. [Relational Database Design (3NF Normalization)](#4-relational-database-design-3nf-normalization)
5. [Demand-Aware Resource Allocation Engine](#5-demand-aware-resource-allocation-engine)
6. [Alternative Resource Recommendation Engine](#6-alternative-resource-recommendation-engine)
7. [Installation & Setup Instructions](#7-installation--setup-instructions)
8. [Demo Accounts & Development Credentials](#8-demo-accounts--development-credentials)
9. [Automated Test Suite](#9-automated-test-suite)
10. [Core Relational SQL Queries & DBMS Architecture](#10-core-relational-sql-queries--dbms-architecture)

---

## 1. Project Overview & Key Objectives

Traditional college resource systems isolate academic assets: central libraries track books, departmental labs hoard test kits, and students frequently have spare components (calculators, sensor boards, course monographs) sitting idle.

**CRISS** bridges this divide by delivering a unified, dual-pooled campus platform:
- **Institutional Asset Management**: Tracks textbooks, graphing calculators, Arduino/Raspberry Pi lab kits, laptops, AI workstation nodes, and bookable study rooms.
- **Student-to-Student Peer Lending**: Enables verified students to safely offer personal equipment for lending to peers without exposing sensitive personal contact information.
- **Resource Intelligence**: Calculates unmet demand rates, tracks inventory contention, prevents double-booking using MySQL row locking (`SELECT ... FOR UPDATE`), and recommends alternative assets when requested items are unavailable.

---

## 2. Technology Stack

- **Backend**: Python 3.13 / Flask 3.1
- **Database**: MySQL Server 8.0 (InnoDB Storage Engine)
- **Database Connector**: `mysql-connector-python` (with connection pooling & parameterized queries)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons
- **Data Visualizations**: Chart.js 4.4
- **Security & Password Hashing**: `werkzeug.security` (PBKDF2-SHA256 salted hashes), CSRF session tokens
- **Test Framework**: `pytest`

---

## 3. Core Capabilities & Features

### A. Role-Based Access Control (RBAC)
- **Student**: Browse catalog, reserve available assets, request unavailable items, view active loans, list peer resources, manage personal reservations.
- **Faculty**: Reserve high-demand lab equipment, request priority slots, report lab maintenance issues.
- **Admin**: Dean/Librarian command center: oversee inventory, manage circulation desk (checkouts & returns), review pending reservation holds, operate the Demand Allocation Engine, manage repairs, and export audit reports to CSV.

### B. Double-Booking Prevention & Concurrency Control
- Reservation holds execute inside database transactions.
- Employs **`SELECT ... FOR UPDATE`** row-level write locks to evaluate overlapping time ranges (`NOT (end <= req_start OR start >= req_end)`).
- Rejects conflicting concurrent allocations with automated transaction rollbacks.
- Blocks users with unresolved overdue items from reserving new campus resources.

### C. Circulation Desk & Automated Triggers
- Direct physical checkout by copy barcode and student campus ID.
- MySQL triggers automatically update inventory status:
  - `trg_after_loan_insert_update_copy`: Transitions `resource_copies.status = 'on_loan'` upon checkout.
  - `trg_after_loan_return_update_copy`: Restores `resource_copies.status = 'available'` upon return.
- If an item is returned damaged, it automatically routes to the **Maintenance Workflow** (`status = 'maintenance'`).

### D. Privacy-Preserving Peer Sharing
- Students can publish peer listings (e.g. course books, IC components).
- Private phone numbers and personal emails are **never exposed** in the peer catalog.
- Exchanges use designated campus safe pickup points (e.g. Central Library Foyer, Department Lobbies).

---

## 4. Relational Database Design (3NF Normalization)

The database schema is organized into 12 normalized tables:

| Table Name | Description | Primary Key | Foreign Keys / Key Constraints |
| :--- | :--- | :--- | :--- |
| `departments` | Academic departments housing resources | `department_id` | `code UNIQUE` |
| `users` | Role-based accounts (student, faculty, admin) | `user_id` | `email UNIQUE`, `student_faculty_id UNIQUE`, `department_id` |
| `categories` | Resource taxonomy & borrow durations | `category_id` | `name UNIQUE` |
| `resources` | Master resource catalog metadata | `resource_id` | `category_id`, `department_id`, `owner_user_id` |
| `resource_copies`| Physical inventory units | `copy_id` | `resource_id`, `barcode UNIQUE` |
| `student_listings`| Peer lending offers & safe pickup locations | `listing_id` | `resource_id UNIQUE`, `lender_user_id` |
| `reservations` | Time-bounded hold requests | `reservation_id` | `resource_id`, `copy_id`, `user_id`, `approval_admin_id` |
| `loans` | Active & historical circulation records | `loan_id` | `copy_id`, `borrower_id`, `issuer_id`, `reservation_id` |
| `resource_requests`| Unmet demand tracking queue | `request_id` | `user_id`, `resource_id`, `category_id`, `fulfilled_copy_id` |
| `maintenance_records`| Damage tracking & repair costs | `maintenance_id` | `copy_id`, `reported_by` |
| `usage_logs` | Audit trail for transactions | `log_id` | `user_id` |
| `notifications` | In-app alerts for due dates & approvals | `notification_id` | `user_id` |

### Database Views
1. **`view_resource_inventory_summary`**: Real-time aggregation of total units, available copies, active loans, and active reservation counts per master resource.
2. **`view_unmet_demand_analytics`**: Aggregates total requests vs unfulfilled requests by category and computes exact unmet demand rate percentages.

### Stored Procedure
- **`sp_reserve_resource`**: Stored procedure implementing atomic reservation creation with `START TRANSACTION`, row locking (`FOR UPDATE`), conflict detection, and rollback safety.

---

## 5. Demand-Aware Resource Allocation Engine

The platform does not rely on vague "AI" claims. It computes transparent, deterministic mathematical rankings based on real database records:

### Formulas
$$\text{Unmet Demand Rate (\%)} = \frac{\text{Unfulfilled Valid Requests}}{\text{Total Valid Requests}} \times 100$$

$$\text{Utilization Rate (\%)} = \frac{\text{On-Loan Copies} + \text{Reserved Copies}}{\text{Total Physical Copies}} \times 100$$

$$\text{Priority Score} = (\text{Unmet Demand Rate} \times 0.40) + (\text{Utilization Rate} \times 0.35) + (\text{Request Frequency Factor} \times 0.15) + (\text{Alternative Scarcity Factor} \times 0.10)$$

Where:
- $\text{Request Frequency Factor} = \min(100, \text{Total Valid Requests} \times 20)$
- $\text{Alternative Scarcity Factor} = \max(0, 100 - (\text{Available Alternatives} \times 25))$

### Priority Tiers & Actionable Recommendations
- **Score $\ge 70$ (CRITICAL)**: Solicit additional procurement or initiate student peer lending campaigns.
- **Score $45 - 69$ (HIGH)**: Reallocate units from sister departments or enforce overdue item recalls.
- **Score $20 - 44$ (MODERATE)**: Standard circulation cycle.
- **Score $< 20$ (LOW / SUFFICIENT)**: Inventory is adequate; consider promotional visibility for underused assets.

---

## 6. Alternative Resource Recommendation Engine

When a requested asset has 0 available physical copies:
1. **Category Match (40 pts)**: Identifies resources sharing the exact academic category.
2. **Department Match (25 pts)**: Identifies resources housed in the same department building.
3. **Curricular Purpose Keyword Match (20 pts)**: Tokenizes purpose descriptions (e.g. "signals", "calculus", "robotics") to match coursework topics.
4. **Availability Bonus (15 pts)**: Verifies physical copies with `status = 'available'`.
5. **Human-Readable Explanation**: Explains why the alternative is suggested (e.g. *"Suggested because: Same academic category (Scientific Calculators); Located in same department (LIB); 2 physical unit(s) immediately available in Library Tech Circulation Desk."*).

---

## 7. Installation & Setup Instructions

### Prerequisites
- Python 3.10+ (Tested on Python 3.13)
- MySQL Server 8.0

### Step 1: Clone or Navigate to Directory
```powershell
cd c:\Users\naral\Desktop\DBMS
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Create a `.env` file (or copy from `.env.example`):
```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=criss-secure-session-key-college-dbms-2026

# MySQL Database Configuration
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306      # Or 3308 if running a development instance
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=criss_db
MYSQL_POOL_SIZE=5
```

### Step 4: Initialize MySQL Database & Schema
Import `schema.sql` into MySQL:
```powershell
mysql -u root -p < schema.sql
```

### Step 5: Seed Sample Academic Data
Populate realistic departments, users, inventory, loans, reservations, unmet demand requests, and maintenance tickets:
```powershell
python seed.py
```

### Step 6: Start the Application
```powershell
python app.py
```
Access the application in your browser at: **`http://127.0.0.1:5000`**

---

## 8. Demo Accounts & Development Credentials

The database comes pre-seeded with accounts representing all three primary user roles. Quick-fill buttons are provided on the login page for convenience during evaluation:

| Role | Name | Email Address | Password | Campus ID |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | Dr. Eleanor Vance (Dean) | `admin@criss.edu` | `AdminPassword@123` | `ADM-001` |
| **Faculty** | Prof. Rajesh Kulkarni | `faculty@criss.edu` | `FacultyPassword@123` | `FAC-042` |
| **Faculty** | Prof. Sunita Sharma | `sharma.fac@criss.edu`| `FacultyPassword@123` | `FAC-043` |
| **Student** | Aarav Sharma | `student@criss.edu` | `StudentPassword@123` | `STU-2024-001` |
| **Student** | Priya Patel (Peer Lender)| `lender@criss.edu` | `StudentPassword@123` | `STU-2023-018` |
| **Student** | Rohit Verma (Overdue User)| `rohit@criss.edu` | `StudentPassword@123` | `STU-2025-089` |

---

## 9. Automated Test Suite

CRISS includes a complete `pytest` test suite covering all critical workflows:

```powershell
python -m pytest tests/ -v
```

### Test Coverage Summary:
- **`test_auth.py`**: Salted password hashing verification, role authorization, invalid credential rejection, user registration.
- **`test_reservation_conflict.py`**: Atomic reservation creation, double-booking rejection on overlapping windows, overdue borrower hold restrictions.
- **`test_loans_returns.py`**: Direct physical checkout, trigger status synchronization (`available` $\rightarrow$ `on_loan`), overdue scan, item returns, maintenance transitions.
- **`test_demand_engine.py`**: View calculation verification for unmet demand rates, multi-criteria priority score ranking, duplicate request prevention.
- **`test_recommendations.py`**: Alternative suggestions when stock is depleted, rationale explanation verification, peer listing matching.
- **`test_routes.py`**: End-to-end HTTP route execution across public, student, and admin portals, Chart.js JSON APIs, and CSV audit exports.

---

## 10. Core Relational SQL Queries & DBMS Architecture

The CRISS database architecture implements 12 core SQL queries demonstrating advanced relational operations including joins, subqueries, views, procedures, and triggers against live MySQL.

### Query Summary:
1. **Multi-Table INNER JOIN**: Joins `resources`, `categories`, and `departments` to resolve taxonomy and building locations.
2. **LEFT OUTER JOIN**: Queries resources while counting physical copies, preserving resources with 0 physical copies.
3. **GROUP BY with Multi-Level Aggregation**: Aggregates inventory count across categories broken down into available, on loan, and maintenance statuses.
4. **HAVING Clause Filter**: Filters departments where active overdue loans exceed the critical threshold ($\ge 1$).
5. **Statistical Aggregate Functions**: Computes `COUNT(*)`, `AVG()`, `MAX()`, `MIN()`, and `SUM()` on loan duration and circulation metrics.
6. **Correlated Subquery**: Identifies high-contention resources whose unfulfilled demand exceeds the department's average unfulfilled demand.
7. **Nested Subquery (`WHERE ... IN`)**: Identifies users disqualified from new reservations due to active overdue loan violations.
8. **Compiled View Query (`view_resource_inventory_summary`)**: Evaluates real-time copy totals and active reservation contention.
9. **Compiled View Query (`view_unmet_demand_analytics`)**: Extracts category-level unmet demand rate percentages.
10. **Date Arithmetic & Range Filtering**: Evaluates active loans coming due within the next 3 days using `BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 3 DAY)`.
11. **Stored Procedure (`sp_reserve_resource`)**: Demonstrates transactional execution with row locking (`FOR UPDATE`) and rollback handlers.
12. **Multi-Table Conditional Aggregation**: Analyzes peer-to-peer student lending participation and pickup readiness.

---

### Technical DBMS Questions & Architecture Details:

**Q1: Why is this database in 3NF?**
> *Answer:* It satisfies 1NF (all column values are atomic, each table has a primary key). It satisfies 2NF (all non-key attributes depend on the complete primary key; no partial dependencies). It satisfies 3NF because transitive dependencies are eliminated—for example, Department building details are isolated in `departments` rather than duplicated in `resources`, preventing update and deletion anomalies.

**Q2: How does the system prevent double-booking when multiple students attempt to reserve simultaneously?**
> *Answer:* The reservation service initiates an explicit transaction (`START TRANSACTION`). When locating candidate copies, it applies **`SELECT ... FOR UPDATE`**, which acquires an exclusive row-level write lock in MySQL InnoDB. If another transaction attempts to reserve the same copy, it must wait. Once committed, subsequent transactions detect 0 available copies for that interval and roll back cleanly without data inconsistency.

**Q3: How do database triggers interact with the Python application?**
> *Answer:* Triggers `trg_after_loan_insert_update_copy` and `trg_after_loan_return_update_copy` handle state transitions directly inside MySQL. When the application executes `INSERT INTO loans`, the trigger automatically transitions `resource_copies.status = 'on_loan'` and logs an audit record in `usage_logs`. This ensures data integrity even if records are inserted outside the Flask application (e.g. via MySQL Workbench or batch scripts).
