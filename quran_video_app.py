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
import concurrent.futures

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
def check_ffmpeg(manual_path=None):
    if manual_path and os.path.exists(manual_path): return manual_path
    if shutil.which("ffmpeg"): return shutil.which("ffmpeg")
    return None

def download_font(url, dest):
    if not os.path.exists(dest):
        try:
            r = requests.get(url, timeout=30)
            with open(dest, 'wb') as f: f.write(r.content)
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
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stApp { background: #0a0a0a; color: #ffffff; }

    /* Ultra Modern Header */
    .studio-header {
        background: linear-gradient(135deg, #1b5e20 0%, #000000 100%);
        padding: 4rem 2rem;
        border-radius: 0 0 50px 50px;
        text-align: center;
        border-bottom: 2px solid #2e7d32;
        margin-bottom: 3rem;
    }

    .studio-card {
        background: #1a1a1a;
        border-radius: 30px;
        padding: 2.5rem;
        border: 1px solid #333;
        margin-bottom: 2rem;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
    }

    /* Pro Progress Counter */
    .progress-container {
        text-align: center;
        padding: 20px;
        background: #222;
        border-radius: 20px;
        border: 1px solid #444;
        margin: 20px 0;
    }
    
    .percentage-text {
        font-size: 3rem;
        font-weight: bold;
        color: #4caf50;
        text-shadow: 0 0 20px rgba(76, 175, 80, 0.5);
    }

    /* Premium Buttons */
    .stButton>button {
        background: linear-gradient(45deg, #2e7d32, #66bb6a) !important;
        color: white !important;
        border-radius: 20px !important;
        padding: 1rem 3rem !important;
        font-size: 1.2rem !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 10px 30px rgba(46, 125, 50, 0.4) !important;
        width: 100%;
    }

    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 15px 40px rgba(46, 125, 50, 0.6) !important;
    }

    h1, h2, h3 { color: #81c784 !important; font-family: 'Amiri', serif !important; }
    
    /* Sidebar Dark Mode */
    [data-testid="stSidebar"] { background-color: #111; border-left: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# ==================== Core Functions ====================
def shape_arabic(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))

@st.cache_resource(show_spinner=False)
def load_whisper_model(size):
    return whisper.load_model(size)

def transcribe_audio(path, size):
    model = load_whisper_model(size)
    result = model.transcribe(path, language="ar", word_timestamps=True)
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})
    return words

def fetch_pexels_video(query, api_key):
    headers = {"Authorization": api_key}
    params = {"query": query, "orientation": "portrait", "size": "large", "per_page": 3}
    r = requests.get(f"{PEXELS_API_BASE}/search", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos: return None
    v = videos[0]
    for f in v["video_files"]:
        if f.get("height", 0) >= 1280:
            url = f["link"]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            with requests.get(url, stream=True, timeout=60) as resp:
                for chunk in resp.iter_content(1024*1024): tmp.write(chunk)
            tmp.close()
            return tmp.name
    return None

def build_video_ultra(video_path, audio_path, words, font_path, font_size, out_path, progress_callback):
    try:
        progress_callback(5, "تحميل الموارد...")
        audio = AudioFileClip(audio_path)
        bg = VideoFileClip(video_path).without_audio()
        
        progress_callback(15, "ضبط التوقيت والمزامنة...")
        if bg.duration < audio.duration:
            loops = int(audio.duration // bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        
        bg = bg.subclipped(0, audio.duration).resized(height=VIDEO_H)
        
        if bg.w > VIDEO_W:
            x_center = bg.w / 2
            bg = bg.cropped(x1=x_center - VIDEO_W / 2, x2=x_center + VIDEO_W / 2)
        else:
            bg = bg.resized(width=VIDEO_W)
            
        overlay = ColorClip(size=(VIDEO_W, 400), color=(0, 0, 0)).with_opacity(0.4)\
                    .with_duration(audio.duration).with_position(("center", int(VIDEO_H * 0.7)))

        progress_callback(30, "تجهيز النصوص العربية...")
        word_clips = []
        for w in words:
            shaped = shape_arabic(w["word"])
            try:
                t_clip = TextClip(text=shaped, font=font_path, font_size=font_size, color="white", 
                                stroke_color="black", stroke_width=2, method="label")
            except:
                t_clip = TextClip(text=shaped, font_size=font_size, color="white", method="label")
                
            t_clip = t_clip.with_start(w["start"]).with_duration(max(w["end"] - w["start"], 0.1))\
                         .with_position(("center", VIDEO_H * 0.75))
            word_clips.append(t_clip)

        progress_callback(50, "بدء المعالجة النهائية...")
        final = CompositeVideoClip([bg, overlay, *word_clips], size=(VIDEO_W, VIDEO_H))
        final = final.with_audio(audio).with_duration(audio.duration)
        
        # Ultra-Fast High-Efficiency Export
        final.write_videofile(
            out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast",
            logger=None,
            threads=8, # Use more threads
            temp_audiofile=os.path.join(tempfile.gettempdir(), "ultra-audio.m4a"),
            remove_temp=True
        )
        progress_callback(100, "اكتمل الإنتاج!")
    finally:
        try: audio.close()
        except: pass
        try: bg.close()
        except: pass
        try: final.close()
        except: pass

# ==================== UI Setup ====================
with st.sidebar:
    st.markdown("## ⚡ التحكم الخارق")
    api_key = st.text_input("مفتاح Pexels", type="password", value=os.getenv("PEXELS_API_KEY", ""))
    video_query = st.text_input("موضوع البحث", value="peaceful galaxy mountains")
    font_size = st.slider("حجم الخط", 50, 200, 95)
    whisper_size = st.selectbox("سرعة الذكاء الاصطناعي", ["tiny", "base", "small"], index=0)
    
    st.divider()
    ffmpeg_p = check_ffmpeg()
    if ffmpeg_p:
        st.success("✅ النظام متصل")
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_p
    
    if os.path.exists(FONT_FILENAME): st.success("✅ الخط جاهز")
    else: download_font(AMIRI_FONT_URL, FONT_FILENAME)

# ==================== Studio UI ====================
st.markdown('<div class="studio-header"><h1>🕋 استوديو القرآن الخارق</h1><p>أسرع وأقوى أداة في العالم لإنتاج فيديوهات القرآن بالذكاء الاصطناعي</p></div>', unsafe_allow_html=True)

t1, t2, t3 = st.tabs(["🚀 الإنتاج الفوري", "📂 المعرض الفاخر", "📖 الدليل المتقدم"])

with t1:
    st.markdown('<div class="studio-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🎵 1. رفع التلاوة")
        aud = st.file_uploader("ارفع الصوت الآن", type=["mp3", "wav"])
        if aud:
            st.audio(aud)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(aud.getvalue())
                st.session_state['aud'] = tmp.name
    with c2:
        if aud:
            st.subheader("🔍 2. تحليل الذكاء الاصطناعي")
            if st.button("تحليل فوري"):
                with st.spinner("جاري التحليل الخارق..."):
                    st.session_state['w'] = transcribe_audio(st.session_state['aud'], whisper_size)
                    st.success("✅ تم التحليل!")
    st.markdown('</div>', unsafe_allow_html=True)

    if 'w' in st.session_state:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.subheader("🎬 3. الإنتاج النهائي")
        source = st.radio("مصدر الفيديو:", ["تلقائي (Pexels)", "رفع يدوي"], horizontal=True)
        
        v_final = None
        if source == "تلقائي (Pexels)":
            if not api_key: st.warning("المفتاح مطلوب")
        else:
            up_v = st.file_uploader("ارفع فيديو الخلفية", type=["mp4"])
            if up_v:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_v:
                    tmp_v.write(up_v.getvalue())
                    v_final = tmp_v.name

        if st.button("🚀 بدء الإنتاج الخارق"):
            try:
                progress_container = st.empty()
                
                def update_progress(val, text):
                    progress_container.markdown(f"""
                    <div class="progress-container">
                        <div class="percentage-text">{val}%</div>
                        <div style="color: #888;">{text}</div>
                    </div>
                    """, unsafe_allow_html=True)

                if source == "تلقائي (Pexels)":
                    update_progress(10, "جاري جلب الفيديو من Pexels...")
                    v_final = fetch_pexels_video(video_query, api_key)
                
                name = f"Quran_Ultra_{datetime.now().strftime('%H%M%S')}.mp4"
                path = os.path.join(ARCHIVE_DIR, name)
                
                build_video_ultra(v_final, st.session_state['aud'], st.session_state['w'], FONT_FILENAME, font_size, path, update_progress)
                
                st.balloons()
                st.session_state['last'] = path
            except Exception as e:
                st.error(f"خطأ: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    if 'last' in st.session_state:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.video(st.session_state['last'])
        with open(st.session_state['last'], "rb") as f:
            st.download_button("📥 تحميل الفيديو فوراً", f, os.path.basename(st.session_state['last']), "video/mp4")
        st.markdown('</div>', unsafe_allow_html=True)

with t2:
    st.title("📂 المعرض الفاخر")
    vids = get_archive_list()
    if vids:
        for v in vids:
            with st.container():
                st.markdown('<div class="studio-card">', unsafe_allow_html=True)
                st.video(os.path.join(ARCHIVE_DIR, v))
                st.write(f"📄 {v}")
                st.markdown('</div>', unsafe_allow_html=True)

with t3:
    st.markdown('<div class="studio-card"><h3>📖 دليل الاستخدام الخارق</h3><p>هذا الإصدار مصمم للعمل بأقصى سرعة ممكنة عبر الإنترنت.</p></div>', unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #444;'>استوديو القرآن الخارق 🕋 صنع بكل فخر</p>", unsafe_allow_html=True)
