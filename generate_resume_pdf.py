import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

def generate_pdf():
    pdf_path = os.path.join(os.path.dirname(__file__), "Bhavesh_Singh_Tomer_Resume.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    # Custom styles
    name_style = ParagraphStyle(
        'Name',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=20,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    contact_style = ParagraphStyle(
        'Contact',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155'),
        alignment=1
    )
    section_style = ParagraphStyle(
        'Section',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=13,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=6,
        spaceAfter=2
    )
    subhead_style = ParagraphStyle(
        'Subhead',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )
    subhead_right = ParagraphStyle(
        'SubheadRight',
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569'),
        alignment=2
    )
    body_style = ParagraphStyle(
        'Body',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )
    bullet_style = ParagraphStyle(
        'Bullet',
        fontName='Helvetica',
        fontSize=8.2,
        leading=10.5,
        textColor=colors.HexColor('#1E293B'),
        leftIndent=12,
        firstLineIndent=-8,
        spaceBefore=1,
        spaceAfter=1
    )

    story = []

    # 1. Header
    story.append(Paragraph("Bhavesh Singh Tomer", name_style))
    story.append(Spacer(1, 2))
    contact_text = (
        "Adm. No.: 23JE0231 &nbsp;|&nbsp; Phone: +91 7078028307 &nbsp;|&nbsp; "
        "Email: <u>bhaveshsingh1807@gmail.com</u><br/>"
        "LinkedIn: <u>linkedin.com/in/BhaveshTomer</u> &nbsp;|&nbsp; GitHub: <u>github.com/BST1807</u>"
    )
    story.append(Paragraph(contact_text, contact_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0F172A'), spaceAfter=4))

    def add_section_header(title):
        story.append(Paragraph(title.upper(), section_style))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor('#94A3B8'), spaceAfter=4))

    # 2. Education
    add_section_header("Education")
    edu_table_data = [
        [
            Paragraph("<b>IIT (ISM) Dhanbad</b>", subhead_style),
            Paragraph("<i>Expected May 2027</i>", subhead_right)
        ],
        [
            Paragraph("<i>B.Tech in Mining Machinery Engineering (Department of Mechanical Engineering), CGPA: 8.00</i>", body_style),
            Paragraph("Dhanbad, Jharkhand", subhead_right)
        ]
    ]
    t_edu = Table(edu_table_data, colWidths=[400, 140])
    t_edu.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_edu)
    story.append(Paragraph("&bull; <b>Relevant Coursework:</b> Data Structures and Algorithms (C++), Digital Image Processing, Computer Programming, Computer Programming Lab", bullet_style))
    story.append(Spacer(1, 3))

    # 3. Experience
    add_section_header("Experience")
    exp_table_data = [
        [
            Paragraph("<b>1Stop</b>", subhead_style),
            Paragraph("<i>Apr 2024 &ndash; Jun 2024</i>", subhead_right)
        ],
        [
            Paragraph("<i>Web Development Front-End</i>", body_style),
            Paragraph("", subhead_right)
        ]
    ]
    t_exp = Table(exp_table_data, colWidths=[400, 140])
    t_exp.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_exp)
    story.append(Paragraph("&bull; Developed responsive websites using HTML, CSS, JavaScript, Bootstrap, and jQuery, with mobile-friendly layouts and reusable UI components.", bullet_style))
    story.append(Paragraph("&bull; Implemented interactive features such as navigation menus, form validation, dynamic content updates, sliders, carousels, and smooth scrolling to improve user experience.", bullet_style))
    story.append(Spacer(1, 3))

    # 4. Projects
    add_section_header("Projects")

    # Project 1: HistoLens AI
    p1_head = [
        [
            Paragraph("<b>HistoLens AI: High-Resolution Digital Pathology & WSI Analysis</b> | <i>Python, FastAPI, OpenSeadragon, OpenCV, Scikit-Image, DeepZoom</i>", subhead_style),
            Paragraph("<u>[GitHub]</u>", subhead_right)
        ]
    ]
    t_p1 = Table(p1_head, colWidths=[470, 70])
    t_p1.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(t_p1)
    story.append(Paragraph("&bull; Architected an on-demand DeepZoom tile streaming pipeline (256&times;256 tiles) to process gigapixel Whole Slide Images (~50K&times;50K), decoupling multi-gigabyte files from RAM to sustain &lt;150 MB runtime memory.", bullet_style))
    story.append(Paragraph("&bull; Engineered an automated tissue segmentation module using Otsu and HSV chroma thresholding to filter 80% blank glass background, coupled with Beer-Lambert optical density deconvolution for Hematoxylin & Eosin stain separation.", bullet_style))
    story.append(Paragraph("&bull; Implemented a high-magnification (40&times;) ROI patch analyzer with single-cell nuclei segmentation, quantifying nuclear crowding (&gt;2500 cells/mm&sup2;), pleomorphism, and malignancy probability in real time.", bullet_style))
    story.append(Paragraph("&bull; Developed a full-stack digital pathology viewer with OpenSeadragon (1&times;&ndash;40&times; multi-scale zoom), real-time tumor probability heatmap overlays, WHO disease stratification, TSR calculation, and automated signed PDF report generation.", bullet_style))
    story.append(Spacer(1, 4))

    # Project 2: AgenticAI RAG
    p2_head = [
        [
            Paragraph("<b>AgenticAI RAG for SWE-QA</b> | <i>LangGraph, LangChain, Qdrant, Hugging Face, FastAPI, Docker, RAGAS</i>", subhead_style),
            Paragraph("<u>[GitHub]</u>", subhead_right)
        ]
    ]
    t_p2 = Table(p2_head, colWidths=[470, 70])
    t_p2.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(t_p2)
    story.append(Paragraph("&bull; Developed an Agentic Retrieval-Augmented Generation (RAG) system for software engineering question answering over technical documentation and open-source code repositories using LangGraph, Qdrant, and Mistral 7B.", bullet_style))
    story.append(Paragraph("&bull; Implemented Adaptive-RAG with intelligent query routing and Corrective-RAG featuring retrieval evaluation, query refinement, and iterative re-retrieval, improving Answer Relevancy by 17.8% over a baseline RAG pipeline.", bullet_style))
    story.append(Paragraph("&bull; Assembled a hybrid retrieval pipeline combining BM25 and dense vector search (Sentence Transformers + Qdrant) with BGE reranking and AST-aware code chunking across multiple repositories.", bullet_style))
    story.append(Paragraph("&bull; Containerized the application using Docker, exposed FastAPI REST APIs, and evaluated using RAGAS, achieving 91.8% Faithfulness, 89.6% Context Precision, 93.1% Answer Relevancy, and an average response latency of 840 ms.", bullet_style))
    story.append(Spacer(1, 4))

    # Project 3: Bitcoin x402
    p3_head = [
        [
            Paragraph("<b>Bitcoin x402 Payment System</b> | <i>Starknet, Next.js, TypeScript, Express.js, Web3</i>", subhead_style),
            Paragraph("<u>[GitHub]</u>", subhead_right)
        ]
    ]
    t_p3 = Table(p3_head, colWidths=[470, 70])
    t_p3.setStyle(TableStyle([('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
    story.append(t_p3)
    story.append(Paragraph("&bull; Developed an HTTP 402-based payment system enabling Bitcoin-denominated micropayments for API access and pay-per-use services on Starknet.", bullet_style))
    story.append(Paragraph("&bull; Built backend workflows for HTTP 402 payment handling, transaction verification, payment validation, and secure request processing.", bullet_style))
    story.append(Paragraph("&bull; Developed a Next.js payment interface with QR-based wallet integration, real-time transaction tracking, and payment diagnostics.", bullet_style))
    story.append(Paragraph("&bull; Integrated blockchain payment workflows with nonce-based transaction validation and explored privacy-preserving ZK proof mechanisms for payment verification.", bullet_style))
    story.append(Spacer(1, 3))

    # 5. Technical Skills
    add_section_header("Technical Skills")
    story.append(Paragraph("<b>Languages:</b> Python, C++, JavaScript, TypeScript, Solidity, SQL", bullet_style))
    story.append(Paragraph("<b>Technologies/Frameworks:</b> FastAPI, OpenCV, PyTorch, Scikit-Image, OpenSeadragon, React.js, Express.js, Node.js, Docker, MongoDB", bullet_style))
    story.append(Paragraph("<b>Concepts:</b> Digital Image Processing, Computer Vision, DeepZoom/WSI Tiling, Agentic RAG, Blockchain, REST APIs", bullet_style))
    story.append(Spacer(1, 3))

    # 6. Achievements
    add_section_header("Achievements")
    story.append(Paragraph("&bull; Team member of a winning project in ETHGlobal&rsquo;s Agentic Ethereum &ndash; OPSEC track.", bullet_style))
    story.append(Spacer(1, 3))

    # 7. Social Engagements
    add_section_header("Social Engagements")
    social_data = [
        [
            Paragraph("<b>Club Member:</b> Cyber Labs &ndash; Tech Society of IIT Dhanbad", body_style),
            Paragraph("<b>Lawn Tennis:</b> College Team", body_style)
        ],
        [
            Paragraph("<b>Volunteer:</b> Srijan (Cultural Fest) Documentation Team", body_style),
            Paragraph("<b>Captain:</b> House Captain at DPS Bareilly", body_style)
        ]
    ]
    t_soc = Table(social_data, colWidths=[310, 230])
    t_soc.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
    ]))
    story.append(t_soc)

    doc.build(story)
    print(f"Generated PDF successfully at {pdf_path}")

if __name__ == "__main__":
    generate_pdf()
