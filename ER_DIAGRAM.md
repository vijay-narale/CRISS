# CRISS - Entity-Relationship (ER) Diagram & Normalization Analysis

## 1. System ER Diagram (Mermaid Relational Architecture)

```mermaid
erDiagram
    DEPARTMENTS ||--o{ USERS : "employs / enrolls"
    DEPARTMENTS ||--o{ RESOURCES : "hosts / houses"
    USERS ||--o{ RESOURCES : "owns (peer lending)"
    USERS ||--o{ RESERVATIONS : "books"
    USERS ||--o{ LOANS : "borrows"
    USERS ||--o{ RESOURCE_REQUESTS : "logs unmet demand"
    USERS ||--o{ STUDENT_LISTINGS : "publishes peer offer"
    USERS ||--o{ MAINTENANCE_RECORDS : "reports fault"
    USERS ||--o{ USAGE_LOGS : "triggers action"
    USERS ||--o{ NOTIFICATIONS : "receives"

    CATEGORIES ||--o{ RESOURCES : "classifies"
    CATEGORIES ||--o{ RESOURCE_REQUESTS : "categorizes"

    RESOURCES ||--o{ RESOURCE_COPIES : "contains physical units"
    RESOURCES ||--o{ RESERVATIONS : "targets"
    RESOURCES ||--o{ RESOURCE_REQUESTS : "records demand for"
    RESOURCES ||--o| STUDENT_LISTINGS : "extends peer metadata"

    RESOURCE_COPIES ||--o{ RESERVATIONS : "allocated to"
    RESOURCE_COPIES ||--o{ LOANS : "circulated in"
    RESOURCE_COPIES ||--o{ MAINTENANCE_RECORDS : "services"
    RESOURCE_COPIES ||--o{ RESOURCE_REQUESTS : "fulfills"

    RESERVATIONS ||--o| LOANS : "converts to"
    STUDENT_LISTINGS ||--o{ LOANS : "lends peer item"

    DEPARTMENTS {
        int department_id PK
        string code UK
        string name
        string building
        timestamp created_at
    }

    USERS {
        int user_id PK
        string email UK
        string password_hash
        string full_name
        enum role "student | faculty | admin"
        int department_id FK
        string phone "Private"
        string student_faculty_id UK
        enum status "active | suspended"
        timestamp created_at
    }

    CATEGORIES {
        int category_id PK
        string name UK
        text description
        int max_borrow_days
        timestamp created_at
    }

    RESOURCES {
        int resource_id PK
        string title
        int category_id FK
        int department_id FK
        enum owner_type "institution | student"
        int owner_user_id FK
        string isbn_or_identifier
        string model_or_author
        string purpose
        string location
        boolean requires_approval
        timestamp created_at
    }

    RESOURCE_COPIES {
        int copy_id PK
        int resource_id FK
        string barcode UK
        enum condition_grade "New | Good | Fair | Needs Maintenance"
        enum status "available | reserved | on_loan | maintenance | retired"
        timestamp added_date
    }

    STUDENT_LISTINGS {
        int listing_id PK
        int resource_id FK,UK
        int lender_user_id FK
        string condition_desc
        string pickup_instructions "Confidential safe point"
        enum listing_status "available | lent | paused | withdrawn"
        date available_from
        date available_until
        timestamp created_at
    }

    RESERVATIONS {
        int reservation_id PK
        int resource_id FK
        int copy_id FK
        int user_id FK
        datetime start_datetime
        datetime end_datetime
        enum status "pending_approval | confirmed | fulfilled | cancelled | expired | rejected"
        int approval_admin_id FK
        text notes
        timestamp created_at
    }

    LOANS {
        int loan_id PK
        int reservation_id FK
        int copy_id FK
        int student_listing_id FK
        int borrower_id FK
        int issuer_id FK
        datetime checkout_date
        datetime due_date
        datetime return_date
        enum status "active | returned | overdue | lost"
        string checkout_condition
        string return_condition
        text notes
        timestamp created_at
    }

    RESOURCE_REQUESTS {
        int request_id PK
        int user_id FK
        int resource_id FK
        int category_id FK
        string description
        enum status "unfulfilled | fulfilled | cancelled | expired"
        int fulfilled_copy_id FK
        datetime fulfilled_at
        timestamp created_at
    }

    MAINTENANCE_RECORDS {
        int maintenance_id PK
        int copy_id FK
        int reported_by FK
        text issue_description
        enum status "reported | in_repair | repaired | decommissioned"
        decimal cost
        datetime started_at
        datetime completed_at
        text repair_notes
    }

    USAGE_LOGS {
        int log_id PK
        string entity_type
        int entity_id
        int user_id FK
        string action
        text details
        timestamp logged_at
    }

    NOTIFICATIONS {
        int notification_id PK
        int user_id FK
        string title
        text message
        enum category "reservation_approved | upcoming_due | overdue | request_fulfilled | general"
        boolean is_read
        timestamp created_at
    }
```

---

## 2. Relational Normalization Analysis (3NF Decomposition)

The schema was designed strictly to satisfy **Third Normal Form (3NF)**:

### First Normal Form (1NF) Compliance
- Every relation has a defined Primary Key (`INT AUTO_INCREMENT`).
- All columns store atomic, non-repeating scalar attributes.
- Multi-valued attributes (such as multiple physical inventory copies of a single textbook or calculator title) are decomposed into a separate child entity `resource_copies`.

### Second Normal Form (2NF) Compliance
- All non-key attributes are fully functionally dependent on the entire primary key.
- Since synthetic surrogate primary keys (`department_id`, `resource_id`, `copy_id`, `loan_id`) are used, there are no composite primary keys with partial dependencies.

### Third Normal Form (3NF) Compliance
- **Elimination of Transitive Dependencies**:
  - In an un-normalized schema, storing Department building name or Category max borrow days directly inside the `resources` or `users` table would introduce transitive dependencies (`resource_id` $\rightarrow$ `department_id` $\rightarrow$ `building`).
  - By separating `departments` and `categories` into standalone master tables, changes to department buildings or category borrow rules do not cause update anomalies across resources.
- **Physical Copy Separation**:
  - Catalog metadata (title, author, ISBN, purpose) is decoupled from physical instance state (barcode, condition grade, maintenance status). If one copy is damaged, the master resource metadata remains untouched.
- **Student Peer Sharing Normalization**:
  - Student lending metadata (`pickup_instructions`, `condition_desc`, lending availability dates) is decoupled into `student_listings` with a 1-to-1 foreign key to `resources`.
  - Student private contact data (`phone`) resides exclusively in `users`, preventing accidental public exposure or privacy violations.

---

## 3. Concurrency Control & MySQL Locking Mechanism

### Transaction Isolation Level
CRISS leverages MySQL InnoDB's default **`REPEATABLE READ`** isolation level with explicit **Row-Level Exclusive Locking (`SELECT ... FOR UPDATE`)**:

1. **Reservation Hold Concurrency**:
   - When a user submits a reservation request, the system opens an ACID transaction (`START TRANSACTION`).
   - A row-level write lock is placed on eligible copies:
     ```sql
     SELECT rc.copy_id 
     FROM resource_copies rc
     WHERE rc.resource_id = %s
       AND rc.status IN ('available', 'reserved')
       AND rc.copy_id NOT IN (
           SELECT res.copy_id 
           FROM reservations res
           WHERE res.resource_id = %s
             AND res.copy_id IS NOT NULL
             AND res.status IN ('confirmed', 'pending_approval')
             AND NOT (res.end_datetime <= %s OR res.start_datetime >= %s)
       )
     ORDER BY rc.copy_id ASC
     LIMIT 1
     FOR UPDATE;
     ```
   - **Double-Booking Prevention**: The `FOR UPDATE` clause instructs InnoDB to acquire an exclusive row lock (`X lock`) on the candidate copy record and prevents concurrent transactions from inspecting or holding the same unit until the active transaction commits or rolls back.
   - If two students click "Reserve" at the exact same millisecond for the last remaining calculator or laptop, the second transaction waits. Once the first transaction commits, the second transaction sees 0 available copies and safely rolls back with a clear user message, eliminating race conditions.

2. **Trigger-Based Inventory State Synchronization**:
   - `trg_after_loan_insert_update_copy`: Triggered automatically after a row is inserted into `loans`. Synchronizes `resource_copies.status = 'on_loan'` and inserts an audit log entry in `usage_logs`.
   - `trg_after_loan_return_update_copy`: Triggered automatically when `loans.status` transitions to `'returned'`. Safely restores `resource_copies.status = 'available'` (unless flagged for maintenance), ensuring application code and database triggers never conflict.
