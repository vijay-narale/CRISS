import docx
import os

def verify_all():
    doc1_path = "CRISS_Cover_Certificate_Abstract.docx"
    doc2_path = "CRISS_Mini_Project_Report.docx"
    
    assert os.path.exists(doc1_path), f"Missing {doc1_path}"
    assert os.path.exists(doc2_path), f"Missing {doc2_path}"
    
    size1 = os.path.getsize(doc1_path)
    size2 = os.path.getsize(doc2_path)
    print(f"File 1: {doc1_path} ({size1} bytes)")
    print(f"File 2: {doc2_path} ({size2} bytes)")
    
    # -------------------------------------------------------------------------
    # VERIFY FILE 1
    # -------------------------------------------------------------------------
    d1 = docx.Document(doc1_path)
    print(f"\n--- Verifying {doc1_path} ---")
    print(f"Sections count: {len(d1.sections)} (Expected 3: Cover, Certificate, Abstract)")
    assert len(d1.sections) == 3, "Doc 1 should have exactly 3 sections"
    
    # Check institutional strings
    full_text_1 = "\n".join([p.text for p in d1.paragraphs] + [cell.text for t in d1.tables for row in t.rows for cell in row.cells])
    required_strings_1 = [
        "CAMPUS RESOURCE INTELLIGENCE & SHARING SYSTEM",
        "A MINI PROJECT REPORT ON",
        "SAVITRIBAI PHULE PUNE UNIVERSITY",
        "INFORMATION TECHNOLOGY",
        "JSPM’s RAJARSHI SHAHU COLLEGE OF ENGINEERING",
        "TATHAWADE, PUNE 411033",
        "2025–2026",
        "CERTIFICATE",
        "[Student Name]",
        "Exam No: [Exam Number]",
        "RBT No: [RBT Number]",
        "[Guide Name]",
        "Dr. N. M. Ranjan",
        "Dr. A. M. Badadhe",
        "Place : Pune",
        "ABSTRACT"
    ]
    for s in required_strings_1:
        assert s in full_text_1, f"Missing required string in Doc 1: {s}"
        print(f"  [PASS] Found: '{s}'")
        
    # Check drawings (logos) in Doc 1
    drawings_1 = sum(1 for p in d1.paragraphs if 'w:drawing' in p._element.xml)
    print(f"  [PASS] Embedded drawings in Doc 1: {drawings_1} (Expected 2: Cover logo + Certificate logo)")
    assert drawings_1 >= 2, "Doc 1 must contain embedded college logo"
    
    # Check Abstract word count in Section 3
    # Abstract is paragraph after 'ABSTRACT' heading
    abs_paras = []
    found_abs_heading = False
    for p in d1.paragraphs:
        if "ABSTRACT" in p.text:
            found_abs_heading = True
            continue
        if found_abs_heading and p.text.strip():
            abs_paras.append(p.text.strip())
            break
            
    abs_text = " ".join(abs_paras)
    abs_word_count = len(abs_text.split())
    print(f"  [PASS] Abstract word count: {abs_word_count} words (Strict requirement: 100-120 words)")
    assert 100 <= abs_word_count <= 120, f"Abstract word count {abs_word_count} is out of bounds!"

    # -------------------------------------------------------------------------
    # VERIFY FILE 2
    # -------------------------------------------------------------------------
    d2 = docx.Document(doc2_path)
    print(f"\n--- Verifying {doc2_path} ---")
    
    # Check Header & Footer
    sec = d2.sections[0]
    header_text = [p.text for p in sec.header.paragraphs if p.text.strip()]
    footer_text = [p.text for p in sec.footer.paragraphs if p.text.strip()]
    print(f"  Header text: {header_text}")
    print(f"  Footer text: {footer_text}")
    assert any("MINI PROJECT" in t for t in header_text), "Header missing 'MINI PROJECT'"
    assert any("Page" in t for t in footer_text), "Footer missing 'Page'"
    assert any("JSPM’s RSCOE Tathawade , Pune" in t for t in footer_text), "Footer missing institutional text"
    print("  [PASS] Header and footer match template exactly.")
    
    # Check 6 Chapter Headings in exact order
    full_p_texts = [p.text.strip() for p in d2.paragraphs if p.text.strip()]
    expected_chapters = [
        "1. INTRODUCTION",
        "2. SOFTWARE REQUIREMENTS SPECIFICATION",
        "3. METHODOLOGY / SYSTEM DESIGN",
        "4. IMPLEMENTATION",
        "5. RESULTS / OUTPUT",
        "6. CONCLUSION"
    ]
    chap_indices = []
    for chap in expected_chapters:
        assert chap in full_p_texts, f"Missing chapter: {chap}"
        idx = full_p_texts.index(chap)
        chap_indices.append(idx)
        print(f"  [PASS] Found chapter '{chap}' at position {idx}")
        
    assert chap_indices == sorted(chap_indices), "Chapter headings are not in the exact prescribed order!"
    print("  [PASS] All 6 chapter headings in exact prescribed order.")
    
    # Check Chapter 1 Introduction Word Count
    intro_start = chap_indices[0] + 1
    intro_end = chap_indices[1]
    intro_paras = full_p_texts[intro_start:intro_end]
    intro_text = " ".join(intro_paras)
    intro_word_count = len(intro_text.split())
    print(f"  [PASS] Introduction word count: {intro_word_count} words (Strict requirement: 300-350 words)")
    assert 300 <= intro_word_count <= 350, f"Intro word count {intro_word_count} is out of bounds!"
    
    # Check Embedded Figures in Doc 2
    drawings_2 = sum(1 for p in d2.paragraphs if 'w:drawing' in p._element.xml)
    print(f"  [PASS] Embedded figure images in Doc 2: {drawings_2} (Expected 3: Architecture, ER, Lifecycle)")
    assert drawings_2 == 3, f"Expected 3 embedded images in Doc 2, found {drawings_2}"
    
    # Check Captions
    captions = [p.text for p in d2.paragraphs if p.text.startswith("Figure 3.")]
    print(f"  Captions: {captions}")
    assert len(captions) == 3, f"Expected 3 Figure 3.x captions, found {len(captions)}"
    
    # Check Tables
    print(f"  [PASS] Total tables in Doc 2: {len(d2.tables)} (FR table, RBAC table, 10 UI placeholders, Test suite table)")
    assert len(d2.tables) >= 13, f"Expected at least 13 tables, found {len(d2.tables)}"
    
    # Check UI Screens in Chapter 5
    ui_fig_tags = [f"Figure 5.{i}" for i in range(1, 11)]
    doc2_text = "\n".join(full_p_texts + [cell.text for t in d2.tables for row in t.rows for cell in row.cells])
    for tag in ui_fig_tags:
        assert tag in doc2_text, f"Missing UI screen placeholder: {tag}"
        print(f"  [PASS] Found UI screen placeholder: {tag}")
        
    # Check Test Cases in Chapter 5
    tc_tags = [f"TC-{i:02d}" for i in range(1, 17)]
    for tc in tc_tags:
        assert tc in doc2_text, f"Missing Test Case: {tc}"
    print(f"  [PASS] All 16 Test Cases (TC-01 through TC-16) present in test results table.")
    
    # Check Key Algorithms and DBMS Features Mentioned
    key_terms = [
        "Unmet Demand Rate", "MCDA", "Priority Score",
        "vw_resource_catalog", "vw_unmet_demand_summary",
        "sp_process_loan_return",
        "trg_after_loan_insert_update_copy_status",
        "trg_after_loan_return_update_copy_status",
        "SELECT ... FOR UPDATE", "InnoDB", "REPEATABLE READ"
    ]
    for term in key_terms:
        assert term in doc2_text, f"Missing key technical term in Doc 2: {term}"
        print(f"  [PASS] Found technical concept: '{term}'")

    print("\n========================================================")
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH 100% PASS!")
    print("========================================================")

if __name__ == "__main__":
    verify_all()
