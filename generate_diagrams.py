"""
Generate high-resolution PNG diagrams for CRISS Project Report.
Uses Graphviz 'dot' to render crisp diagrams with academic typography.
"""

import subprocess
import os

# 1. System Architecture
arch_dot = """digraph G {
    rankdir=TB;
    nodesep=0.4;
    ranksep=0.5;
    bgcolor="#ffffff";
    node [fontname="Arial", fontsize=10, shape=box, style="rounded,filled"];
    edge [fontname="Arial", fontsize=9, color="#475569"];

    subgraph cluster_presentation {
        label = "Presentation Tier (Responsive Client Interface)";
        style = "filled";
        color = "#0f172a";
        fillcolor = "#f8fafc";
        fontname = "Arial Bold";
        fontsize = 11;
        fontcolor = "#0f172a";

        UI_Web [label="Bootstrap 5 / HTML5 / CSS3\nAcademic Technology UI", fillcolor="#e0f2fe", color="#0284c7"];
        UI_Charts [label="Chart.js 4.4 Analytics Visualizations\n(Utilization, Demand, Inventory)", fillcolor="#e0f2fe", color="#0284c7"];
        UI_Peer [label="Student Peer-to-Peer Sharing Portal\n(Privacy-Shielded Academic Lending)", fillcolor="#e0f2fe", color="#0284c7"];
    }

    subgraph cluster_application {
        label = "Application & Business Logic Tier (Python Flask)";
        style = "filled";
        color = "#0d9488";
        fillcolor = "#f0fdfa";
        fontname = "Arial Bold";
        fontsize = 11;
        fontcolor = "#0d9488";

        Auth_Svc [label="Auth & RBAC Service\n(PBKDF2 Hashing, CSRF Tokens)", fillcolor="#ccfbf1", color="#0d9488"];
        Resv_Svc [label="Reservation Service\n(ACID Holds, Conflict Engine)", fillcolor="#ccfbf1", color="#0d9488"];
        Loan_Svc [label="Loan Circulation Desk\n(Checkouts, Returns, Overdue)", fillcolor="#ccfbf1", color="#0d9488"];
        Demand_Eng [label="Demand-Aware Allocation Engine\n(Unmet Rate, MCDA Priority Scoring)", fillcolor="#fee2e2", color="#dc2626"];
        Rec_Svc [label="Alternative Recommendation Engine\n(Category, Dept, Purpose Matching)", fillcolor="#ccfbf1", color="#0d9488"];
        Maint_Svc [label="Maintenance & Repair Service\n(Damage Workflow, Cost Tracking)", fillcolor="#ccfbf1", color="#0d9488"];
        Peer_Svc [label="Peer Lending Service\n(Student Listings, Privacy Shields)", fillcolor="#ccfbf1", color="#0d9488"];
    }

    subgraph cluster_database {
        label = "Data Tier (MySQL 8.0 InnoDB RDBMS - 3NF Normalized)";
        style = "filled";
        color = "#1e293b";
        fillcolor = "#f1f5f9";
        fontname = "Arial Bold";
        fontsize = 11;
        fontcolor = "#1e293b";

        DB_Tables [label="12 Normalized Relational Tables\n(Users, Resources, Copies, Reservations, Loans...)", fillcolor="#ffffff", color="#334155"];
        DB_Views [label="Compiled Analytical Views\n(view_resource_inventory_summary,\nview_unmet_demand_analytics)", fillcolor="#ffffff", color="#334155"];
        DB_Proc [label="Stored Procedure\n(sp_reserve_resource with FOR UPDATE)", fillcolor="#ffffff", color="#334155"];
        DB_Triggers [label="ACID State Triggers\n(trg_after_loan_insert_update_copy,\ntrg_after_loan_return_update_copy)", fillcolor="#ffffff", color="#334155"];
    }

    UI_Web -> Auth_Svc [label="HTTP / Sessions"];
    UI_Web -> Resv_Svc [label="Booking Requests"];
    UI_Web -> Loan_Svc [label="Checkout / Return"];
    UI_Charts -> Demand_Eng [label="REST JSON APIs"];
    UI_Peer -> Peer_Svc [label="Listings & Borrows"];

    Auth_Svc -> DB_Tables [label="users, departments"];
    Resv_Svc -> DB_Tables [label="SELECT ... FOR UPDATE"];
    Resv_Svc -> DB_Proc [label="CALL sp_reserve_resource"];
    Loan_Svc -> DB_Tables [label="INSERT loans"];
    Loan_Svc -> DB_Triggers [label="Fires on loan events"];
    Demand_Eng -> DB_Views [label="Query Analytical Views"];
    Peer_Svc -> DB_Tables [label="student_listings"];
    Rec_Svc -> DB_Tables [label="Query Alternative Assets"];
    Maint_Svc -> DB_Tables [label="maintenance_records"];
}
"""

# 2. Relational ER Diagram
er_dot = """digraph ER {
    rankdir=LR;
    nodesep=0.5;
    ranksep=0.7;
    bgcolor="#ffffff";
    node [fontname="Arial", fontsize=9, shape=record, style="filled", fillcolor="#ffffff", color="#334155"];
    edge [fontname="Arial", fontsize=8, color="#0f172a"];

    departments [label="{DEPARTMENTS | department_id (PK)\\lcode (UK)\\lname\\lbuilding\\lcreated_at\\l}", fillcolor="#e0f2fe", color="#0284c7"];
    users [label="{USERS | user_id (PK)\\lemail (UK)\\lpassword_hash\\lfull_name\\lrole (Enum)\\ldepartment_id (FK)\\lphone (Private)\\lstudent_faculty_id (UK)\\lstatus\\l}", fillcolor="#e0f2fe", color="#0284c7"];
    categories [label="{CATEGORIES | category_id (PK)\\lname (UK)\\ldescription\\lmax_borrow_days\\l}", fillcolor="#fef3c7", color="#d97706"];
    resources [label="{RESOURCES (Master) | resource_id (PK)\\ltitle\\lcategory_id (FK)\\ldepartment_id (FK)\\lowner_type (Enum)\\lowner_user_id (FK)\\lisbn_or_identifier\\lpurpose\\llocation\\lrequires_approval\\l}", fillcolor="#ccfbf1", color="#0d9488"];
    resource_copies [label="{RESOURCE_COPIES (Units) | copy_id (PK)\\lresource_id (FK)\\lbarcode (UK)\\lcondition_grade\\lstatus (available, on_loan...)\\l}", fillcolor="#ccfbf1", color="#0d9488"];
    student_listings [label="{STUDENT_LISTINGS (P2P) | listing_id (PK)\\lresource_id (FK,UK)\\llender_user_id (FK)\\lcondition_desc\\lpickup_instructions (Safe Point)\\llisting_status\\lavailable_from / until\\l}", fillcolor="#ede9fe", color="#7c3aed"];
    reservations [label="{RESERVATIONS | reservation_id (PK)\\lresource_id (FK)\\lcopy_id (FK)\\luser_id (FK)\\lstart_datetime\\lend_datetime\\lstatus (confirmed, pending...)\\lnotes\\l}", fillcolor="#fee2e2", color="#dc2626"];
    loans [label="{LOANS | loan_id (PK)\\lreservation_id (FK)\\lcopy_id (FK)\\lborrower_id (FK)\\lissuer_id (FK)\\lcheckout_date\\ldue_date\\lreturn_date\\lstatus (active, returned, overdue)\\lreturn_condition\\l}", fillcolor="#fee2e2", color="#dc2626"];
    resource_requests [label="{RESOURCE_REQUESTS | request_id (PK)\\luser_id (FK)\\lresource_id (FK)\\lcategory_id (FK)\\ldescription\\lstatus (unfulfilled, fulfilled)\\lfulfilled_copy_id (FK)\\l}", fillcolor="#fef3c7", color="#d97706"];
    maintenance_records [label="{MAINTENANCE_RECORDS | maintenance_id (PK)\\lcopy_id (FK)\\lreported_by (FK)\\lissue_description\\lstatus (reported, in_repair...)\\lcost\\l}", fillcolor="#f3e8ff", color="#9333ea"];
    usage_logs [label="{USAGE_LOGS (Audit) | log_id (PK)\\lentity_type\\lentity_id\\luser_id (FK)\\laction\\ldetails\\llogged_at\\l}", fillcolor="#f1f5f9", color="#475569"];
    notifications [label="{NOTIFICATIONS | notification_id (PK)\\luser_id (FK)\\ltitle\\lmessage\\lcategory\\lis_read\\l}", fillcolor="#f1f5f9", color="#475569"];

    departments -> users [label="1 : N"];
    departments -> resources [label="1 : N"];
    categories -> resources [label="1 : N"];
    categories -> resource_requests [label="1 : N"];
    users -> resources [label="1 : N (Peer Owner)"];
    resources -> resource_copies [label="1 : N"];
    resources -> student_listings [label="1 : 1"];
    users -> student_listings [label="1 : N (Lender)"];
    users -> reservations [label="1 : N (Requester)"];
    resources -> reservations [label="1 : N"];
    resource_copies -> reservations [label="1 : N"];
    reservations -> loans [label="0..1 : 1"];
    resource_copies -> loans [label="1 : N"];
    users -> loans [label="1 : N (Borrower)"];
    users -> resource_requests [label="1 : N"];
    resources -> resource_requests [label="1 : N"];
    resource_copies -> resource_requests [label="1 : 1 (Fulfillment)"];
    resource_copies -> maintenance_records [label="1 : N"];
    users -> maintenance_records [label="1 : N (Reporter)"];
    users -> notifications [label="1 : N"];
    users -> usage_logs [label="1 : N"];
}
"""

# 3. Reservation & Loan Lifecycle State Machine
lifecycle_dot = """digraph Lifecycle {
    rankdir=LR;
    nodesep=0.5;
    ranksep=0.6;
    bgcolor="#ffffff";
    node [fontname="Arial", fontsize=9, shape=box, style="rounded,filled"];
    edge [fontname="Arial", fontsize=8, color="#334155"];

    subgraph cluster_resv {
        label = "Reservation Lifecycle State Machine";
        style = "filled";
        color = "#0284c7";
        fillcolor = "#f0f9ff";
        fontname = "Arial Bold";
        fontsize = 10;

        R_Start [label="Start Hold Request", shape=circle, fillcolor="#0284c7", fontcolor="#ffffff", width=0.4];
        R_Pending [label="pending_approval\n(Approval Required / Student)", fillcolor="#fef3c7", color="#d97706"];
        R_Confirmed [label="confirmed\n(Copy Locked: FOR UPDATE)", fillcolor="#dcfce7", color="#16a34a"];
        R_Cancelled [label="cancelled\n(Released back to pool)", fillcolor="#f1f5f9", color="#475569"];
        R_Rejected [label="rejected\n(Declined by Coordinator)", fillcolor="#fee2e2", color="#dc2626"];
        R_Fulfilled [label="fulfilled\n(Converted to Loan)", fillcolor="#e0f2fe", color="#0284c7"];

        R_Start -> R_Pending [label="Requires Approval=TRUE"];
        R_Start -> R_Confirmed [label="Auto-Approved"];
        R_Pending -> R_Confirmed [label="Admin / Faculty Approves"];
        R_Pending -> R_Rejected [label="Admin Declines"];
        R_Confirmed -> R_Cancelled [label="User / Admin Cancels"];
        R_Pending -> R_Cancelled [label="User Cancels"];
        R_Confirmed -> R_Fulfilled [label="Issued at Circulation Desk"];
    }

    subgraph cluster_loan {
        label = "Circulation Loan Lifecycle State Machine";
        style = "filled";
        color = "#0d9488";
        fillcolor = "#f0fdfa";
        fontname = "Arial Bold";
        fontsize = 10;

        L_Checkout [label="Physical Checkout\n(Copy -> 'on_loan' via Trigger)", fillcolor="#ccfbf1", color="#0d9488"];
        L_Active [label="active\n(Due date tracked)", fillcolor="#dcfce7", color="#16a34a"];
        L_Overdue [label="overdue\n(Due date exceeded;\nBorrower blocked)", fillcolor="#fee2e2", color="#dc2626"];
        L_Returned_Good [label="returned (Good / Fair)\n(Copy -> 'available' via Trigger)", fillcolor="#dcfce7", color="#16a34a"];
        L_Returned_Maint [label="returned (Needs Maintenance)\n(Copy -> 'maintenance';\nTicket created)", fillcolor="#f3e8ff", color="#9333ea"];

        R_Fulfilled -> L_Checkout [label="Circulation Scan", style="dashed", color="#0284c7"];
        L_Checkout -> L_Active [label="Loan Active"];
        L_Active -> L_Overdue [label="NOW() > due_date\n(Daily Overdue Scan)"];
        L_Active -> L_Returned_Good [label="Return (Normal)"];
        L_Active -> L_Returned_Maint [label="Return (Damaged)"];
        L_Overdue -> L_Returned_Good [label="Late Return (Fine Assessed)"];
        L_Overdue -> L_Returned_Maint [label="Late Return (Damaged)"];
    }
}
"""

def generate():
    specs = [
        ('arch.dot', arch_dot, 'architecture_diagram.png'),
        ('er.dot', er_dot, 'er_diagram.png'),
        ('lifecycle.dot', lifecycle_dot, 'lifecycle_diagram.png')
    ]
    for dot_file, content, png_file in specs:
        with open(dot_file, 'w', encoding='utf-8') as f:
            f.write(content)
        subprocess.run(['dot', '-Tpng', '-Gdpi=250', dot_file, '-o', png_file], check=True)
        print(f"Generated {png_file} successfully! Size: {os.path.getsize(png_file)} bytes")

if __name__ == '__main__':
    generate()
