import streamlit as st
import os
from PIL import Image
import img2pdf
import numpy as np
import cv2
from io import BytesIO
import tempfile
import time
import base64

# Custom CSS styling
def apply_custom_css():
    st.markdown(
        """
        <style>
        .stApp {
            max-width: 90%;
            padding: 2rem;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            padding: 10px 24px;
            transition: all 0.3s;
        }
        .stButton>button:hover {
            background-color: #45a049;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .stDownloadButton>button {
            background-color: #2196F3 !important;
            margin-top: 20px;
        }
        .stFileUploader>section>div:hover {
            border-color: #2196F3;
        }
        .stRadio>div {
            flex-direction: row;
            gap: 20px;
        }
        .stRadio>div>label {
            background-color: #f0f2f6;
            padding: 10px 20px;
            border-radius: 20px;
            transition: all 0.3s;
        }
        .stRadio>div>label:hover {
            background-color: #e0e0e0;
            cursor: pointer;
        }
        .stRadio>div>div>div>div {
            padding: 6px 15px !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2563eb;
        }
        .success-box {
            background-color: #d4edda;
            border-left: 5px solid #00aa00;
            padding: 10px 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .info-box {
            background-color: #d1ecf1;
            border-left: 5px solid #0dcaf0;
            padding: 10px 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .file-preview {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-top: 20px;
        }
        .preview-item {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            background: white;
            text-align: center;
            width: 150px;
        }
        .preview-item img {
            border-radius: 5px;
            margin-bottom: 8px;
            object-fit: cover;
        }
        .preview-item p {
            margin: 2px 0;
            font-size: 12px;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: #1e3799;
        }
        footer {
            visibility: hidden;
        }
        /* Clear images notification */
        .clear-notice {
            padding: 10px;
            background-color: #fff3cd;
            border-radius: 5px;
            margin: 10px 0;
            color: #856404;
            text-align: center;
            border-left: 4px solid #ffcc00;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

# Apply custom CSS
apply_custom_css()

# Initialize session state
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'processing_mode' not in st.session_state:
    st.session_state.processing_mode = 'color'
if 'processed_imgs' not in st.session_state:
    st.session_state.processed_imgs = []
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'file_ids' not in st.session_state:
    st.session_state.file_ids = set()

# App header
st.title("📷 Image to PDF Converter")
st.markdown("""
Convert multiple JPG images to a single PDF file with optional grayscale conversion.
""", unsafe_allow_html=True)

# Processing functions
def convert_image_to_color_or_grayscale(img, mode='color'):
    """Convert image to color or grayscale"""
    if mode == 'grayscale':
        if len(img.shape) > 2:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Convert to 3-channel for consistency
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if len(img.shape) == 2 else img
    return img

def format_file_size(size):
    """Convert file size to human-readable format"""
    for unit in ['B', 'KB', 'MB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} GB"

def get_aspect_ratio(width, height):
    """Calculate aspect ratio as string (e.g., 4:3)"""
    def gcd(a, b):
        return a if b == 0 else gcd(b, a % b)
    
    r = gcd(width, height)
    x = int(width / r)
    y = int(height / r)
    return f"{x}:{y}"

def image_to_bytes(img):
    """Convert PIL image to base64 string"""
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# Settings sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Processing mode selection
    mode_option = st.radio(
        "Conversion Mode", 
        ["Preserve Colors", "Convert to Grayscale"],
        index=0 if st.session_state.processing_mode == 'color' else 1,
        key='processing_mode_radio',
        help="Choose whether to keep images in color or convert to grayscale"
    )
    st.session_state.processing_mode = 'color' if mode_option == "Preserve Colors" else 'grayscale'
    
    # PDF options
    page_size = st.selectbox(
        "PDF Page Size", 
        ["A4 (210×297mm)", "Letter (8.5×11in)", "Legal (8.5×14in)", "A3 (297×420mm)"],
        index=0
    )
    
    # Map to img2pdf paper size names
    page_size_map = {
        "A4 (210×297mm)": "a4",
        "Letter (8.5×11in)": "letter",
        "Legal (8.5×14in)": "legal",
        "A3 (297×420mm)": "a3"
    }
    
    dpi = st.slider(
        "Image Quality (DPI)", 
        min_value=72,
        max_value=300,
        value=150,
        help="Higher DPI = better quality; lower DPI = smaller file size"
    )
    
    # Clear all button in sidebar
    if st.button("🧹 Clear All Files", use_container_width=True):
        st.session_state.uploaded_files = []
        st.session_state.processed_imgs = []
        st.session_state.pdf_bytes = None
        st.session_state.file_ids = set()
        st.rerun()
    
    st.divider()
    st.subheader("Instructions")
    st.markdown("""
    1. Upload your JPG images
    2. Select conversion settings
    3. Click **Create PDF**
    4. Download the generated PDF
    """)

# File uploader section
st.subheader("📁 Upload Images")
uploaded_files = st.file_uploader(
    "Select one or more JPG/JPEG files", 
    type=['jpg', 'jpeg'], 
    accept_multiple_files=True,
    label_visibility="collapsed"
)

# Calculate current file IDs
current_file_ids = {id(file) for file in uploaded_files}

# Track if files changed
files_changed = current_file_ids != st.session_state.file_ids

# Update session state if files changed
if files_changed:
    st.session_state.uploaded_files = uploaded_files
    st.session_state.file_ids = current_file_ids
    st.session_state.processed_imgs = []
    st.session_state.pdf_bytes = None

# Display message if no files
if not st.session_state.uploaded_files:
    st.markdown('<div class="clear-notice">ℹ️ Upload images to get started</div>', unsafe_allow_html=True)

# Display uploaded files preview
if st.session_state.uploaded_files:
    file_count = len(st.session_state.uploaded_files)
    st.success(f"✔️ You've uploaded {file_count} {'file' if file_count == 1 else 'files'}")
    
    # Create collapsible preview display
    st.markdown("**Image Preview**")
    with st.expander("Show Uploaded Images", expanded=True):
        st.markdown("<div class='file-preview'>", unsafe_allow_html=True)
        
        for i, uploaded_file in enumerate(st.session_state.uploaded_files):
            # Only process if not already processed
            if i >= len(st.session_state.processed_imgs):
                file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                uploaded_file.seek(0)  # Reset file pointer
                
                img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                height, width = img.shape[:2]
                aspect_ratio = get_aspect_ratio(width, height)
                
                processed_img = convert_image_to_color_or_grayscale(img, st.session_state.processing_mode)
                st.session_state.processed_imgs.append(processed_img)
            else:
                processed_img = st.session_state.processed_imgs[i]
                height, width = processed_img.shape[:2]
                aspect_ratio = get_aspect_ratio(width, height)
            
            # Create preview - convert BGR to RGB for PIL
            rgb_img = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
            preview_img = Image.fromarray(rgb_img)
            preview_img.thumbnail((180, 180))
            
            # Display preview
            st.markdown(
                f"""
                <div class="preview-item">
                    <img src="data:image/jpeg;base64,{image_to_bytes(preview_img)}" width="140">
                    <p style="font-weight:bold;overflow:hidden;text-overflow:ellipsis;height:1.5em;">{uploaded_file.name}</p>
                    <p>{width}×{height} ({aspect_ratio})</p>
                    <p>{format_file_size(len(uploaded_file.getvalue()))}</p>
                    <p><strong>{'B&W' if st.session_state.processing_mode=='grayscale' else 'Color'}</strong></p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        st.markdown("</div>", unsafe_allow_html=True)

# Process and output area
def create_pdf():
    if not st.session_state.uploaded_files:
        st.warning("Please upload at least one image first")
        return
        
    with st.spinner(f"🔧 Creating PDF from {len(st.session_state.uploaded_files)} images..."):
        try:
            # Prepare image data as byte buffers
            image_bytes_list = []
            
            for img_array in st.session_state.processed_imgs:
                # Convert to RGB using OpenCV's COLOR_BGR2RGB
                rgb_image = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                
                # Convert to PIL Image and save as JPEG bytes
                img_pil = Image.fromarray(rgb_image)
                byte_io = BytesIO()
                img_pil.save(byte_io, format='JPEG')
                image_bytes = byte_io.getvalue()
                image_bytes_list.append(image_bytes)
            
            # Create PDF
            pdf_bytes = img2pdf.convert(
                image_bytes_list,
                dpi=float(dpi),
                pagesize=page_size_map[page_size]
            )
            
            st.session_state.pdf_bytes = pdf_bytes
            st.success("✅ PDF created successfully!")
            
            # Show file info
            pdf_size = format_file_size(len(pdf_bytes))
            st.markdown(f"""
            <div class="success-box">
                <h3>Ready to Download!</h3>
                • PDF Size: <strong>{pdf_size}</strong><br>
                • Pages: <strong>{len(image_bytes_list)}</strong><br>
                • Format: <strong>{st.session_state.processing_mode.capitalize()}</strong>
            </div>
            """, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"❌ Error creating PDF: {str(e)}")

# Create PDF button
if st.button("✨ Create PDF", use_container_width=True):
    create_pdf()

# Show PDF creation summary
if st.session_state.pdf_bytes:
    # Generate unique filename
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"converted_images_{timestamp}.pdf"
    
    # Download button
    st.download_button(
        "⬇️ Download PDF", 
        data=st.session_state.pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True
    )
    
# Troubleshooting info
st.divider()
with st.expander("ℹ️ Troubleshooting Tips"):
    st.markdown("""
    **Common Issues:**
    - **Files not appearing:** Streamlit may cache files. Click "Clear All Files" and re-upload.
    - **Processing fails:**
        - Ensure JPG/JPEG format only
        - Avoid very large images (>20MB each)
    - **Quality issues:**
        - Increase DPI for better quality
        - Use grayscale for smaller file sizes
    - **Connection problems:**
        - Close and reopen the app if files don't refresh
        - Check browser console for errors (F12)
    """)

# Add a clear images option
if st.session_state.uploaded_files:
    if st.button("🗑️ Clear Uploaded Images", use_container_width=True):
        st.session_state.uploaded_files = []
        st.session_state.processed_imgs = []
        st.session_state.pdf_bytes = None
        st.session_state.file_ids = set()
        st.rerun()
