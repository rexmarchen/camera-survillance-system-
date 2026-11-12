import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 756, "CamFu — Smart CCTV Feed Management System | Viva Preparation Guide")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 750, 576, 750)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 25, page_str)
        self.drawString(36, 25, "Confidential — For Internal Project Team Use Only")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 35, 576, 35)
        self.restoreState()

def create_viva_pdf(output_filename="CamFu_Viva_Preparation_Guide.pdf"):
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0284C7"),
        spaceAfter=8
    )

    overview_box_style = ParagraphStyle(
        'OverviewBox',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1E293B")
    )

    member_title_style = ParagraphStyle(
        'MemberTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=6,
        spaceAfter=2,
        keepWithNext=True
    )

    role_sub_style = ParagraphStyle(
        'RoleSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0369A1"),
        spaceAfter=8,
        keepWithNext=True
    )

    q_style = ParagraphStyle(
        'QuestionText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    a_style = ParagraphStyle(
        'AnswerText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5
    )

    story = []

    # =============================================================
    # PAGE 1: OVERVIEW & MEMBER 1 (ANSHU)
    # =============================================================
    story.append(Paragraph("CamFu: Smart CCTV Feed Management System", title_style))
    story.append(Paragraph("<b>Viva Voce & Technical Examination Guide</b> &nbsp;|&nbsp; Role-by-Role Questions & Core Architecture", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=8))

    pitch_html = (
        "<b>Project Pitch (What any member should say in the first 30 seconds):</b><br/>"
        "<i>\"CamFu solves CCTV monitoring fatigue. Traditional security setups force operators to watch dozens of static, "
        "equal-sized screens where 95% of feeds have zero activity. CamFu connects an AI computer vision engine with a desktop "
        "surveillance client to analyze motion, crowd density, and unusual behavior in real-time. It continuously calculates a "
        "priority score and automatically promotes the highest-risk camera into a large 2×2 spotlight feed while dimming inactive feeds.\"</i>"
    )
    pitch_p = Paragraph(pitch_html, overview_box_style)
    pitch_table = Table([[pitch_p]], colWidths=[540])
    pitch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BAE6FD")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', [4, 4, 4, 4])
    ]))
    story.append(pitch_table)
    story.append(Spacer(1, 8))

    # Anshu Section
    m1_box = Paragraph("<b>MEMBER 1: ANSHU — System Architect & Integration Lead</b>", member_title_style)
    m1_role = Paragraph("<b>Assigned Domain:</b> System Design, Component Decoupling, Inter-Process Integration & Flow Orchestration", role_sub_style)
    story.append(m1_box)
    story.append(m1_role)

    story.append(Paragraph("Q1: Explain the high-level architecture of CamFu and how the components interact.", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> CamFu follows a <b>dual-tier decoupled architecture</b>:<br/>"
        "• <b>Desktop Client (JavaFX):</b> Native multi-threaded surveillance interface managing video rendering, camera configuration, and grid presentation.<br/>"
        "• <b>AI Engine (Python Flask):</b> Background microservice listening on port 5000 running OpenCV frame processors for each camera.<br/>"
        "• <b>Shared Persistence Layer:</b> An asynchronous SQLite/MySQL database stores priority scores every 2 seconds, decoupling heavy frame analysis from the GUI.",
        a_style
    ))

    story.append(Paragraph("Q2: Why did you choose a hybrid JavaFX + Python stack instead of building everything in one language?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Each language was chosen for its primary operational strength:<br/>"
        "• <b>JavaFX</b> excels at multi-threaded native desktop rendering, smooth 60 FPS video playback, and low GUI memory overhead.<br/>"
        "• <b>Python</b> has the premier Computer Vision ecosystem (OpenCV, NumPy) and enables rapid model iteration.<br/>"
        "• <b>Thread Safety:</b> By running Python as an independent OS process, any spike in AI computation or frame decoding never freezes the user interface.",
        a_style
    ))

    story.append(Paragraph("Q3: How do the Java client and Python AI engine communicate?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Through two separate channels:<br/>"
        "1. <b>Database-backed Shared State:</b> Python updates priority scores in the database every 2 seconds. The Java GUI polls latest scores every 3–5 seconds to refresh the grid layout without socket locking.<br/>"
        "2. <b>HTTP REST Endpoints:</b> Java polls <code>http://localhost:5000/health</code> to verify AI engine status. A live web dashboard at <code>/</code> and JSON endpoint at <code>/api/scores</code> allow external monitoring.",
        a_style
    ))

    story.append(Paragraph("Q4: What happens if the Python AI service crashes during surveillance?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> The architecture is fault-tolerant. Video streaming runs on independent daemon threads inside JavaFX. If the AI engine stops, live camera feeds continue streaming smoothly without interruption; only dynamic auto-sorting pauses until the service is restored.",
        a_style
    ))

    story.append(PageBreak())

    # =============================================================
    # PAGE 2: MEMBER 2 (AIRIS)
    # =============================================================
    m2_box = Paragraph("<b>MEMBER 2: AIRIS — AI, Computer Vision & Scoring Lead</b>", member_title_style)
    m2_role = Paragraph("<b>Assigned Domain:</b> OpenCV Pipeline, Motion Subtraction, Crowd Estimation & Priority Weighting", role_sub_style)
    story.append(m2_box)
    story.append(m2_role)

    story.append(Paragraph("Q1: How exactly is the 'Motion Score' computed from camera frames?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b><br/>"
        "1. Each incoming frame is downsampled to <b>320×240</b> pixels for high-throughput processing.<br/>"
        "2. We use <b>MOG2 Background Subtraction</b> (<code>cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=25, detectShadows=True)</code>) to segment moving foreground pixels.<br/>"
        "3. A threshold of 254 eliminates gray shadow pixels (value 127). Morphological opening and dilation merge fragmented body contours.<br/>"
        "4. The moving pixel ratio is smoothed via Exponential Moving Average (EMA) to prevent flickering:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>Motion Score = 0.7 × previous + 0.3 × min(1.0, motion_ratio × 4.0)</b>",
        a_style
    ))

    story.append(Paragraph("Q2: How does the engine estimate 'Crowd Density' without heavy neural networks?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Using <b>Contour Silhouette Analysis</b> on the dilated foreground mask. We filter out noise blobs and detect contours with area &gt; 800 px² (representing adult human silhouettes at 320×240). The count of distinct human-sized blobs is mapped to crowd level (4+ people = 1.0) and smoothed across frames.",
        a_style
    ))

    story.append(Paragraph("Q3: How is 'Unusual Behavior' detected?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> We track the <b>motion velocity / rate-of-change</b> (Δmotion &gt; 0.20). Sudden surges (running, panic, fights) increment a spike counter. If sustained motion exceeds 0.55, the behavior anomaly score spikes: <code>min(1.0, (motion - 0.45) × 1.5 + spike_boost)</code>, triggering a visual <b>🔴 ALERT</b> badge.",
        a_style
    ))

    story.append(Paragraph("Q4: What is the exact formula for overall Priority Score?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Defined in <code>config.yaml</code> as a weighted linear combination:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>Priority = (0.40 × Motion) + (0.30 × Crowd) + (0.20 × Behavior) + (0.10 × Time Factor)</b><br/>"
        "Motion holds the highest operational weight (40%), followed by crowd density (30%), anomaly behavior (20%), and time-of-day risk (10% — night hours 22:00–06:00 scale up to 0.9).",
        a_style
    ))

    story.append(Paragraph("Q5: Why did you add background model warmup?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> When MOG2 starts, it has no reference background and treats the entire first frame as motion (scoring 100%). We implemented a 30-frame silent warmup loop upon camera connection so background pixels are learned before real-time scoring begins.",
        a_style
    ))

    story.append(PageBreak())

    # =============================================================
    # PAGE 3: MEMBER 3 (AKSHIT)
    # =============================================================
    m3_box = Paragraph("<b>MEMBER 3: AKSHIT — Frontend, JavaFX Dashboard & Smart Layout Lead</b>", member_title_style)
    m3_role = Paragraph("<b>Assigned Domain:</b> UI Architecture, Dynamic Hero Grid, Multi-Stream Threading & Live Demo", role_sub_style)
    story.append(m3_box)
    story.append(m3_role)

    story.append(Paragraph("Q1: What is the 'Smart Auto-Layout' (Hero Grid) feature, and why is it important?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Standard security control rooms show static, equal-sized video grids where operators easily miss incidents. CamFu introduces an <b>automated priority layout</b>:<br/>"
        "• The camera with highest overall priority is dynamically promoted to a <b>2×2 'Hero' slot (60% width)</b> with an amber <code>⭐ PRIORITY</code> badge.<br/>"
        "• Subordinate active cameras are placed on the right and bottom.<br/>"
        "• Inactive feeds (score &lt; 0.20) are automatically dimmed to 55% opacity, eliminating operator fatigue.",
        a_style
    ))

    story.append(Paragraph("Q2: When the grid reorders cameras based on priority, does the video stutter or reconnect?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> <b>No.</b> We cache and reuse <code>VLCStreamPanel</code> instances in a ConcurrentHashMap. When priority rankings change, we only update the cell coordinates in the <code>GridPane</code>. The video capture threads and socket connections remain uninterrupted.",
        a_style
    ))

    story.append(Paragraph("Q3: How do you prevent UI freezing when rendering 4, 8, or 16 camera streams?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Through <b>thread isolation</b>. Each camera feed runs its frame decoding on a dedicated background daemon thread. Decoded frames are delivered to JavaFX ImageViews via non-blocking <code>Platform.runLater()</code> calls. Database polling for priority rankings also runs on a separate scheduled thread pool.",
        a_style
    ))

    story.append(Paragraph("Q4: What visual indicators are implemented on camera tiles?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b><br/>"
        "• <b>Gold Border & ⭐ PRIORITY Badge:</b> Highlight the top-ranked camera.<br/>"
        "• <b>Red Border & 🔴 ALERT Badge:</b> Highlight feeds where unusual behavior exceeds 0.50.<br/>"
        "• <b>Green / Red Status Dot:</b> Indicates camera connection status (ACTIVE vs DISCONNECTED).",
        a_style
    ))

    story.append(Paragraph("Q5: How does the priority table complement the grid view?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> The Priority Table Panel provides an exact real-time numerical audit log showing exact values for Motion, Crowd, Behavior, and overall Priority score for each camera, sorted from highest to lowest risk.",
        a_style
    ))

    story.append(PageBreak())

    # =============================================================
    # PAGE 4: MEMBER 4 (ANSHIKA) & TRAP QUESTIONS
    # =============================================================
    m4_box = Paragraph("<b>MEMBER 4: ANSHIKA — Backend, Database, Automation & Testing Lead</b>", member_title_style)
    m4_role = Paragraph("<b>Assigned Domain:</b> Database Persistence, Failover Systems, Launcher Automation & QA Testing", role_sub_style)
    story.append(m4_box)
    story.append(m4_role)

    story.append(Paragraph("Q1: What database is used, and what is the automatic failover mechanism?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> We built an <b>automatic fallback system</b> in <code>DatabaseConnectionPool.java</code> and <code>db_manager.py</code>. The application attempts to connect to MySQL first. If MySQL is not running or unreachable (1s timeout), it seamlessly falls back to an embedded <b>SQLite database (<code>camfu.db</code>)</b>, auto-creating all tables and seeding default camera records so the system always runs out of the box.",
        a_style
    ))

    story.append(Paragraph("Q2: Describe the primary database tables in CamFu.", q_style))
    story.append(Paragraph(
        "<b>Answer:</b><br/>"
        "• <code>cameras</code>: Stores camera ID, name, location, RTSP/HTTP URL, resolution, and status.<br/>"
        "• <code>priority_scores</code>: Stores motion, crowd, behavior, time factor, and overall scores with timestamps.<br/>"
        "• <code>events</code>: Records triggered security incidents, confidence levels, and recorded clip paths.",
        a_style
    ))

    story.append(Paragraph("Q3: How did you ensure the project runs seamlessly on any machine without setup issues?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> Added <b>Maven Wrapper (<code>mvnw.cmd</code> / <code>mvnw</code>)</b> so anyone can run it without installing Maven; automated <b>dynamic classpath generation</b> in <code>run-camfu.ps1</code>; added cross-version Python dependencies; and built <b>1-click launchers</b> (<code>CamFu.bat</code> and <code>run-camfu.sh</code>).",
        a_style
    ))

    story.append(Paragraph("Q4: How does selective automated video recording work?", q_style))
    story.append(Paragraph(
        "<b>Answer:</b> To save disk space, CamFu doesn't record static hours of empty footage. When a camera's motion score exceeds 0.35 or unusual behavior is flagged, OpenCV's <code>VideoWriter</code> automatically records timestamped <code>.avi</code> clips into the <code>recordings/</code> directory with overlay location and time tags.",
        a_style
    ))

    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0284C7"), spaceAfter=6))

    # Trap Questions
    story.append(Paragraph("<b>⚡ Top 3 'Trap' Questions from Examiners (How to Answer as a Team)</b>", q_style))

    story.append(Paragraph(
        "<b>1. \"Is this real AI or just basic OpenCV image processing?\"</b><br/>"
        "<b>Answer:</b> <i>\"It is Computer Vision AI. MOG2 is a probabilistic Gaussian Mixture Model that continuously learns and adapts to scene lighting. The priority scoring engine uses behavioral heuristics and temporal moving averages. Furthermore, the architecture is designed so neural object detectors (like YOLOv8-nano) can be dropped directly into the frame processor without altering the UI.\"</i>",
        a_style
    ))

    story.append(Paragraph(
        "<b>2. \"What is the biggest limitation of your current implementation?\"</b><br/>"
        "<b>Answer:</b> <i>\"Sudden severe lighting changes (e.g. flipping a light switch in a dark room) can momentarily register as motion until the background model adapts (about 30 frames). In future releases, we plan to add edge-AI semantic segmentation to distinguish lighting shifts from physical objects.\"</i>",
        a_style
    ))

    story.append(Paragraph(
        "<b>3. \"Can this scale to 50 or 100 cameras?\"</b><br/>"
        "<b>Answer:</b> <i>\"Yes, because the AI processing can be distributed. Multiple camera stream processors can run across distributed worker nodes or edge devices (e.g., Raspberry Pi / Jetson Nano), all reporting their numerical scores to the central database, keeping the central control room lightweight.\"</i>",
        a_style
    ))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated: {output_filename}")

if __name__ == '__main__':
    create_viva_pdf()
