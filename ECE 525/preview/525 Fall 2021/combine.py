import os
import re
import io # For BytesIO for page number stamping
# If you installed pypdf, you can change this to:
# from pypdf import PdfWriter, PdfReader
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas as reportlab_canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.colors import black

# --- Configuration ---
PDF_DIRECTORY = r"C:\Users\luoog\Documents\CLASSES\25su\ECE 525\preview\525 Fall 2021"
OUTPUT_FILENAME = "Combined_Linear_Optimization_Notes.pdf" # Output will be in the same directory as the script
HEADING_TITLE = "Notes on Linear Optimization"
HEADING_AUTHOR = "Alberto Del Pia"
# --- End Configuration ---

def parse_filename(filename):
    """
    Parses a PDF filename to extract sorting and ToC information.
    Expected format: "NUMBER. Title - part PART_NUMBER - notes.pdf"
    All parts are optional except NUMBER and Title.
    """
    if not filename.lower().endswith(".pdf"):
        return None

    name_stem = filename[:-4]  # Remove .pdf

    is_notes = False
    if name_stem.lower().endswith(" - notes"):
        is_notes = True
        name_stem = name_stem[:-(len(" - notes"))]

    part_number = None
    # Regex to find " - part X" at the end of the stem
    match_part = re.search(r"\s*-\s*part\s*(\d+)$", name_stem, re.IGNORECASE)
    if match_part:
        part_number = int(match_part.group(1))
        name_stem = name_stem[:match_part.start()] # Remove part string from stem

    # Regex to find "NUMBER. Title"
    match_main = re.match(r"(\d+)\.\s*(.*)", name_stem)
    if match_main:
        main_number = int(match_main.group(1))
        title = match_main.group(2).strip()
        return {
            "main_number": main_number,
            "part_number": part_number,
            "title": title,  # This is the base title, e.g., "The simplex method"
            "is_notes": is_notes,
            "original_filename": filename,
            "sort_key": (main_number, part_number if part_number is not None else 0, is_notes)
        }
    print(f"Warning: Could not parse filename: {filename}")
    return None

def create_temporary_pdf_page(output_path, draw_content_callback):
    """Creates a single-page PDF using ReportLab."""
    c = reportlab_canvas.Canvas(output_path, pagesize=letter)
    draw_content_callback(c, letter[0], letter[1]) # width, height
    c.save()

def draw_title_page_content(canvas_obj, width, height):
    """Draws the title and author on the canvas for the title page."""
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitlePageHeader', parent=styles['h1'], alignment=1, spaceAfter=0.5*inch, fontSize=24)
    author_style = ParagraphStyle('TitlePageAuthor', parent=styles['h2'], alignment=1, fontSize=18)

    p_title = Paragraph(HEADING_TITLE, title_style)
    p_title.wrapOn(canvas_obj, width - 2*inch, height)
    p_title.drawOn(canvas_obj, inch, height / 2 + 0.5*inch)

    p_author = Paragraph(HEADING_AUTHOR, author_style)
    p_author.wrapOn(canvas_obj, width - 2*inch, height)
    p_author.drawOn(canvas_obj, inch, height / 2 - 0.5*inch)


def main():
    print(f"Starting PDF combination process...")
    print(f"Source Directory: {PDF_DIRECTORY}")

    # 1. List, parse, and sort PDF files
    all_files_in_dir = os.listdir(PDF_DIRECTORY)
    parsed_pdfs_info = []
    for fname in all_files_in_dir:
        if fname.lower().endswith(".pdf"):
            parsed_info = parse_filename(fname)
            if parsed_info:
                parsed_pdfs_info.append(parsed_info)

    if not parsed_pdfs_info:
        print("No parsable PDF files found in the directory.")
        return

    parsed_pdfs_info.sort(key=lambda x: x['sort_key'])
    
    print("\nFiles to be merged (in order):")
    for p_info in parsed_pdfs_info:
        print(f"  - {p_info['original_filename']} (Title: {p_info['title']}, Part: {p_info['part_number']}, Notes: {p_info['is_notes']})")

    # Main PDF writer for the final output
    final_merger = PdfWriter()

    # 2. Create and add title page
    temp_title_page_path = "_temp_title_page.pdf"
    create_temporary_pdf_page(temp_title_page_path, draw_title_page_content)
    with open(temp_title_page_path, "rb") as f_title:
        title_pdf_reader = PdfReader(f_title)
        final_merger.append(fileobj=title_pdf_reader)
    if os.path.exists(temp_title_page_path):
        os.remove(temp_title_page_path)
    print(f"\nAdded title page: '{HEADING_TITLE}' by {HEADING_AUTHOR}")

    # 3. Merge content PDFs into a temporary writer and collect ToC data
    toc_entries_data = []
    temp_content_writer = PdfWriter()
    current_page_in_content_block = 0

    for pdf_info in parsed_pdfs_info:
        full_path = os.path.join(PDF_DIRECTORY, pdf_info['original_filename'])
        try:
            with open(full_path, "rb") as f_pdf:
                pdf_reader = PdfReader(f_pdf)
                num_pages_in_current_pdf = len(pdf_reader.pages)

                toc_display_title = pdf_info['title']
                if pdf_info['part_number'] is not None:
                    toc_display_title += f" - Part {pdf_info['part_number']}"

                level = 0 # Section
                if pdf_info['is_notes']:
                    toc_display_title += " - Notes"
                    level = 1 # Subsection
                
                toc_entries_data.append({
                    "title": toc_display_title,
                    "level": level,
                    "start_page_in_content_block": current_page_in_content_block + 1 # 1-indexed
                })
                
                temp_content_writer.append(fileobj=pdf_reader)
                current_page_in_content_block += num_pages_in_current_pdf
        except Exception as e:
            print(f"Error processing file {pdf_info['original_filename']}: {e}")
            continue
    
    # Write temporary content to a file to read its pages for final merge and get its page count
    temp_merged_content_path = "_temp_merged_content.pdf"
    with open(temp_merged_content_path, "wb") as f_temp_content:
        temp_content_writer.write(f_temp_content)

    # 4. Determine number of ToC pages
    styles = getSampleStyleSheet()
    toc_header_style = ParagraphStyle('TOCHeader', parent=styles['h1'], alignment=1, spaceAfter=0.2*inch, fontSize=16)
    toc_section_style = ParagraphStyle('TOCSection', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=6)
    toc_subsection_style = ParagraphStyle('TOCSubsection', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=12, leftIndent=0.25*inch)

    # Estimate ToC pages by building it once (with placeholder page numbers)
    temp_toc_story_for_estimation = [Paragraph("Table of Contents", toc_header_style)]
    for entry in toc_entries_data:
        # Simple text for estimation, actual formatting later
        line = entry['title'] + " .................. 999" 
        style = toc_section_style if entry['level'] == 0 else toc_subsection_style
        if entry['level'] == 1: # Indent for display in paragraph
             line = "&nbsp;&nbsp;&nbsp;&nbsp;" + line
        temp_toc_story_for_estimation.append(Paragraph(line, style))

    temp_toc_estimation_path = "_temp_toc_estimation.pdf"
    toc_estimator_doc = SimpleDocTemplate(temp_toc_estimation_path, pagesize=letter,
                                     leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch)
    toc_estimator_doc.build(temp_toc_story_for_estimation)
    
    num_toc_pages = 0
    if os.path.exists(temp_toc_estimation_path):
        with open(temp_toc_estimation_path, "rb") as f_est:
            reader_est = PdfReader(f_est)
            num_toc_pages = len(reader_est.pages)
        os.remove(temp_toc_estimation_path)
    if num_toc_pages == 0 and toc_entries_data: num_toc_pages = 1 # Fallback if build fails or empty but ToC header exists
    
    print(f"Estimated Table of Contents will take {num_toc_pages} page(s).")

    # 5. Create actual ToC PDF
    # Page numbers in ToC point to: 1 (title_page) + num_toc_pages + page_in_content_block
    final_content_starts_after_this_many_pages = 1 + num_toc_pages 

    actual_toc_story = [Paragraph("Table of Contents", toc_header_style)]
    for entry in toc_entries_data:
        actual_page_num_in_final_doc = final_content_starts_after_this_many_pages + entry['start_page_in_content_block']
        
        # Create dotted leader line (basic version)
        title_text = entry['title']
        page_num_text = str(actual_page_num_in_final_doc)
        
        # Max line width approx 6.5 inches. At 10pt font, ~10-12 chars/inch. ~70 chars.
        # For Helvetica 11pt bold (sections), maybe 8-10 chars/inch.
        # Let's use a fixed width for title part and then dots.
        # This is tricky without precise text width measurement.
        # Using a table or <para dots > tag in RML would be better.
        # Simple approach:
        max_title_chars = 50 # Adjust as needed
        max_page_num_chars = 4
        num_dots = max(3, 65 - len(title_text) - len(page_num_text)) # Rough estimate

        # Format with HTML-like tags for ReportLab Paragraphs
        line_text = f"{title_text} {' . ' * (num_dots // 3)} {page_num_text}" # Simplified dots
        if len(title_text) > max_title_chars : # Truncate long titles in ToC if necessary
            line_text = f"{title_text[:max_title_chars-3]}... {' . ' * (num_dots // 3)} {page_num_text}"

        style_to_use = toc_section_style
        if entry['level'] == 1: # Subsection
            line_text = f"&nbsp;&nbsp;&nbsp;&nbsp;{line_text}" # Indent
            style_to_use = toc_subsection_style
        
        actual_toc_story.append(Paragraph(line_text, style_to_use))

    temp_actual_toc_path = "_temp_final_toc.pdf"
    final_toc_doc = SimpleDocTemplate(temp_actual_toc_path, pagesize=letter,
                                 leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch)
    final_toc_doc.build(actual_toc_story)

    # Add ToC pages to the main merger
    if os.path.exists(temp_actual_toc_path):
        with open(temp_actual_toc_path, "rb") as f_toc:
            toc_reader = PdfReader(f_toc)
            final_merger.append(fileobj=toc_reader)
        os.remove(temp_actual_toc_path)
        print("Added Table of Contents.")

    # 6. Add merged content (from the temporary content file)
    with open(temp_merged_content_path, "rb") as f_content_final:
        content_final_reader = PdfReader(f_content_final)
        final_merger.append(fileobj=content_final_reader)
    if os.path.exists(temp_merged_content_path):
        os.remove(temp_merged_content_path)
    print("Added main content.")

    # 7. Add Page Numbers to the final document (content part only)
    # Write the current final_merger to a new temp file to read its pages for numbering
    temp_un_numbered_output_path = "_temp_un_numbered_output.pdf"
    with open(temp_un_numbered_output_path, "wb") as f_out_temp:
        final_merger.write(f_out_temp)

    final_numbered_writer = PdfWriter()
    reader_for_numbering = PdfReader(temp_un_numbered_output_path)
    
    # Content starts after title page (1) and ToC pages (num_toc_pages)
    # This is the 0-indexed page number where content begins.
    content_starts_at_0_indexed_page = 1 + num_toc_pages 

    for i in range(len(reader_for_numbering.pages)):
        page = reader_for_numbering.pages[i]
        
        if i >= content_starts_at_0_indexed_page:
            # This is a content page, add a page number
            content_page_number = (i - content_starts_at_0_indexed_page) + 1
            
            packet = io.BytesIO()
            num_canvas = reportlab_canvas.Canvas(packet, pagesize=letter)
            num_canvas.setFont("Helvetica", 9)
            # Position: bottom center. Adjust X for centering number.
            num_canvas.drawCentredString(letter[0]/2, 0.5 * inch, str(content_page_number))
            num_canvas.save()
            
            packet.seek(0)
            number_stamp_pdf = PdfReader(packet)
            stamp_page = number_stamp_pdf.pages[0]
            
            page.merge_page(stamp_page) # PyPDF2 specific
            # If using pypdf, it might be page.add_transformation(stamp_page.transformation_matrix) then page.merge_page(stamp_page)
            # or similar, or directly page.merge_transformed_page(stamp_page, Transformation())

        final_numbered_writer.add_page(page)
    
    if os.path.exists(temp_un_numbered_output_path):
        os.remove(temp_un_numbered_output_path)
    print("Added page numbers to content.")

    # 8. Write final output
    final_output_path = os.path.join(os.getcwd(), OUTPUT_FILENAME) # Save in script's current dir
    with open(final_output_path, "wb") as f_final_out:
        final_numbered_writer.write(f_final_out)
    
    print(f"\nSuccessfully created combined PDF: {final_output_path}")


if __name__ == "__main__":
    main()