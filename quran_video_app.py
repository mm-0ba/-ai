import os
import re
import tempfile
import requests
import streamlit as st
import whisper
import arabic_reshaper
from bidi.algorithm import get_display
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip, concatenate_videoclips
import shutil
import time
from datetime import datetime

# ==================== Page Config ====================
st.set_page_config(
    page_title="Quran Studio Ultra AI | استوديو القرآن الخارق",
    page_icon="🕋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== Constants & Storage ====================
PEXELS_API_BASE = "https://api.pexels.com/videos"
VIDEO_W, VIDEO_H = 1080, 1920
AMIRI_FONT_URL = "https://github.com/googlefonts/amiri/raw/main/fonts/ttf/Amiri-Regular.ttf"
FONT_FILENAME = "Amiri-Regular.ttf"
ARCHIVE_DIR = "الفيديوهات_المنتجة"

os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ==================== Helper Functions ====================
def check_ffmpeg():
    if shutil.which("ffmpeg"): return shutil.which("ffmpeg")
    common = ["C:\\ffmpeg\\bin\\ffmpeg.exe", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    for p in common:
        if os.path.exists(p): return p
    return None

def download_font():
    if not os.path.exists(FONT_FILENAME):
        try:
            r = requests.get(AMIRI_FONT_URL, timeout=30)
            with open(FONT_FILENAME, 'wb') as f: f.write(r.content)
            return True
        except: return False
    return True

def get_archive_list():
    if not os.path.exists(ARCHIVE_DIR): return []
    files = [f for f in os.listdir(ARCHIVE_DIR) if f.lower().endswith('.mp4')]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(ARCHIVE_DIR, x)), reverse=True)
    return files

# ==================== Pro UI Styling ====================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&family=Amiri:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stApp { background: #050505; color: #ffffff; }

    .studio-header {
        background: linear-gradient(180deg, #1b5e20 0%, #050505 100%);
        padding: 3rem 1rem;
        border-radius: 0 0 40px 40px;
        text-align: center;
        border-bottom: 1px solid #2e7d32;
        margin-bottom: 2rem;
    }

    .studio-card {
        background: #0f0f0f;
        border-radius: 25px;
        padding: 1.5rem;
        border: 1px solid #1e1e1e;
        margin-bottom: 1.5rem;
    }

    .percentage-text {
        font-size: 3.5rem;
        font-weight: bold;
        color: #4caf50;
        text-align: center;
        margin: 10px 0;
    }

    .stButton>button {
        background: linear-gradient(90deg, #2e7d32 0%, #43a047 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        padding: 0.8rem !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
    }

    h1, h2, h3 { color: #81c784 !important; }
    
    /* Progress Customization */
    .stProgress > div > div > div > div { background-color: #4caf50; }
    </style>
    """, unsafe_allow_html=True)

# ==================== Core Functions ====================
def prepare_arabic_text(text: str) -> str:
    # Essential for fixing "###" and reversed words
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

@st.cache_resource(show_spinner=False)
def load_whisper_model(size):
    # Optimize for CPU (Streamlit Cloud)
    return whisper.load_model(size, device="cpu")

def transcribe_audio(path, size):
    model = load_whisper_model(size)
    # fp16=False is mandatory for CPU execution
    result = model.transcribe(path, language="ar", word_timestamps=True, fp16=False)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})
    return words

def fetch_pexels_video(query, api_key):
    headers = {"Authorization": api_key}
    params = {"query": query, "orientation": "portrait", "size": "large", "per_page": 1}
    r = requests.get(f"{PEXELS_API_BASE}/search", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    v_data = r.json().get("videos", [])
    if not v_data: return None
    for f in v_data[0]["video_files"]:
        if f.get("height", 0) >= 1280:
            url = f["link"]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            with requests.get(url, stream=True, timeout=60) as resp:
                for chunk in resp.iter_content(1024*1024): tmp.write(chunk)
            tmp.close()
            return tmp.name
    return None

def build_video_ultra(video_path, audio_path, words, font_size, out_path, status_placeholder):
    try:
        status_placeholder.info("🚀 جاري تهيئة الموارد...")
        audio = AudioFileClip(audio_path)
        bg = VideoFileClip(video_path).without_audio()
        
        # Perfect Duration Sync
        if bg.duration < audio.duration:
            loops = int(audio.duration // bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        bg = bg.subclipped(0, audio.duration).resized(height=VIDEO_H)
        
        # Center Cropping
        if bg.w > VIDEO_W:
            x_center = bg.w / 2
            bg = bg.cropped(x1=x_center - VIDEO_W / 2, x2=x_center + VIDEO_W / 2)
        else:
            bg = bg.resized(width=VIDEO_W)
            
        overlay = ColorClip(size=(VIDEO_W, 450), color=(0, 0, 0)).with_opacity(0.35)\
                    .with_duration(audio.duration).with_position(("center", int(VIDEO_H * 0.68)))

        status_placeholder.info("✍️ جاري معالجة النصوص العربية...")
        word_clips = []
        # Absolute path for the font is required on Linux
        full_font_path = os.path.abspath(FONT_FILENAME)
        
        for w in words:
            shaped = prepare_arabic_text(w["word"])
            try:
                # Optimized TextClip for Arabic
                t_clip = TextClip(
                    text=shaped, 
                    font=full_font_path, 
                    font_size=font_size, 
                    color="white",
                    stroke_color="black", 
                    stroke_width=1.5, 
                    method="label",
                    text_align="center"
                )
            except Exception as e:
                # Fallback if font path fails
                t_clip = TextClip(text=shaped, font_size=font_size, color="white", method="label")
                
            t_clip = t_clip.with_start(w["start"]).with_duration(max(w["end"] - w["start"], 0.15))\
                         .with_position(("center", VIDEO_H * 0.72))
            word_clips.append(t_clip)

        status_placeholder.info("🎬 جاري التصدير النهائي (خارق السرعة)...")
        final = CompositeVideoClip([bg, overlay, *word_clips], size=(VIDEO_W, VIDEO_H))
        final = final.with_audio(audio).with_duration(audio.duration)
        
        final.write_videofile(
            out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast", # Crucial for speed
            logger=None,
            threads=4,
            temp_audiofile=os.path.join(tempfile.gettempdir(), f"audio_{int(time.time())}.m4a"),
            remove_temp=True
        )
        return True
    finally:
        try: audio.close(); bg.close(); final.close()
        except: pass

# ==================== UI Setup ====================
with st.sidebar:
    st.markdown("## ⚡ التحكم الذكي")
    api_key = st.text_input("مفتاح Pexels", type="password", value=os.getenv("PEXELS_API_KEY", ""))
    video_query = st.text_input("موضوع البحث", value="peaceful clouds nature")
    font_size = st.slider("حجم الخط", 60, 180, 100)
    whisper_size = st.selectbox("دقة الذكاء الاصطناعي", ["tiny", "base"], index=0)
    
    st.divider()
    if check_ffmpeg():
        st.success("✅ النظام جاهز")
        os.environ["IMAGEIO_FFMPEG_EXE"] = check_ffmpeg()
    
    download_font()
    if os.path.exists(FONT_FILENAME): st.success("✅ الخط جاهز")

# ==================== Studio UI ====================
st.markdown('<div class="studio-header"><h1>🕋 استوديو القرآن الخارق</h1><p>الإصدار المستقر والأسرع للإنتاج عبر الإنترنت</p></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 إنتاج فيديو جديد", "📂 أرشيف الفيديوهات"])

with tab1:
    st.markdown('<div class="studio-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎵 1. رفع الصوت")
        aud_file = st.file_uploader("اختر ملف التلاوة", type=["mp3", "wav"])
        if aud_file:
            st.audio(aud_file)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t:
                t.write(aud_file.getvalue()); st.session_state['ap'] = t.name
    with c2:
        if aud_file:
            st.subheader("🔍 2. التحليل")
            if st.button("بدء تحليل الصوت"):
                with st.spinner("جاري التحليل..."):
                    st.session_state['words'] = transcribe_audio(st.session_state['ap'], whisper_size)
                    st.success("✅ اكتمل التحليل!")
    st.markdown('</div>', unsafe_allow_html=True)

    if 'words' in st.session_state:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.subheader("🎬 3. التصدير النهائي")
        mode = st.radio("خلفية الفيديو:", ["تلقائي من Pexels", "رفع يدوي"], horizontal=True)
        
        v_in = None
        if mode == "رفع يدوي":
            up_v = st.file_uploader("ارفع فيديو (MP4)", type=["mp4"])
            if up_v:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as t:
                    t.write(up_v.getvalue()); v_in = t.name

        if st.button("� ابدأ الإنتاج الآن"):
            if mode == "تلقائي من Pexels" and not api_key: st.error("أدخل مفتاح Pexels أولاً!")
            elif mode == "رفع يدوي" and not v_in: st.error("ارفع فيديو أولاً!")
            else:
                try:
                    sp = st.empty()
                    prog = st.progress(0)
                    
                    if mode == "تلقائي من Pexels":
                        sp.info("جاري جلب الفيديو...")
                        v_in = fetch_pexels_video(video_query, api_key)
                    
                    prog.progress(30)
                    out_name = f"Quran_Studio_{datetime.now().strftime('%M%S')}.mp4"
                    out_path = os.path.join(ARCHIVE_DIR, out_name)
                    
                    if build_video_ultra(v_in, st.session_state['ap'], st.session_state['words'], font_size, out_path, sp):
                        prog.progress(100)
                        st.balloons()
                        st.session_state['last_v'] = out_path
                except Exception as e:
                    st.error(f"خطأ: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    if 'last_v' in st.session_state:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.video(st.session_state['last_v'])
        with open(st.session_state['last_v'], "rb") as f:
            st.download_button("📥 تحميل الفيديو", f, os.path.basename(st.session_state['last_v']), "video/mp4")
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    vids = get_archive_list()
    if vids:
        for v in vids:
            with st.expander(f"🎬 فيديو: {v}"):
                st.video(os.path.join(ARCHIVE_DIR, v))
                with open(os.path.join(ARCHIVE_DIR, v), "rb") as f:
                    st.download_button("تحميل", f, v, "video/mp4", key=v)
    else: st.info("الأرشيف فارغ.")

st.markdown("<p style='text-align: center; color: #444; margin-top: 2rem;'>صُنع لخدمة القرآن الكريم ❤️</p>", unsafe_allow_html=True)
