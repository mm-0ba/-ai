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
FONTS_DIR = "fonts"
# Use English name for folder to avoid URL encoding issues on Cloud, but keep display Arabic
ARCHIVE_DIR = "produced_videos" 

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# ==================== Helper Functions ====================
def get_available_fonts():
    """Lists all fonts with extreme robust searching (local & recursive)"""
    # Start with default font
    fonts = { "الخط الافتراضي (Amiri)": FONT_FILENAME }
    
    # 1. First priority: Check the standard 'fonts' directory
    if os.path.exists(FONTS_DIR):
        try:
            for f in os.listdir(FONTS_DIR):
                if f.lower().endswith(('.ttf', '.otf')):
                    name = f.replace("ArbFONTS-", "").replace(".ttf", "").replace(".otf", "").replace("-", " ").replace("_", " ")
                    fonts[name] = os.path.abspath(os.path.join(FONTS_DIR, f))
        except: pass

    # 2. Secondary: Recursive search in all subdirectories just in case
    try:
        cwd = os.getcwd()
        for root, dirs, files in os.walk(cwd):
            if any(part.startswith('.') for part in root.split(os.sep)): continue
            if root == os.path.abspath(FONTS_DIR): continue # Already scanned
                
            for f in files:
                if f.lower().endswith(('.ttf', '.otf')):
                    if f == FONT_FILENAME: continue
                    name = f.replace("ArbFONTS-", "").replace(".ttf", "").replace(".otf", "").replace("-", " ").replace("_", " ")
                    full_path = os.path.abspath(os.path.join(root, f))
                    if name not in fonts:
                        fonts[name] = full_path
    except: pass
    
    return fonts
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

    /* Glassmorphism Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%) !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 700 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        width: 100%;
    }

    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(46, 125, 50, 0.4) !important;
        background: linear-gradient(135deg, #388e3c 0%, #2e7d32 100%) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
    }

    .stButton>button:active {
        transform: translateY(0px) !important;
    }

    /* Smart Progress Container */
    .progress-container {
        background: rgba(255,255,255,0.05);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.1);
        text-align: center;
        margin: 20px 0;
    }

    .percentage-display {
        font-size: 4rem;
        font-weight: 900;
        background: linear-gradient(to right, #4caf50, #81c784);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
        font-family: 'Cairo', sans-serif;
    }

    .status-text {
        font-size: 1.1rem;
        color: #81c784;
        margin-top: 10px;
    }

    .studio-header {

    h1, h2, h3 { color: #81c784 !important; }
    
    /* Progress Customization */
    .stProgress > div > div > div > div { background-color: #4caf50; }
    </style>
    """, unsafe_allow_html=True)

# ==================== Core Functions ====================
def update_smart_progress(placeholder, progress_bar, percentage, status_msg):
    """Displays a professional smart progress UI"""
    progress_bar.progress(percentage / 100)
    placeholder.markdown(f"""
        <div class="progress-container">
            <div class="percentage-display">{percentage}%</div>
            <div class="status-text">{status_msg}</div>
        </div>
    """, unsafe_allow_html=True)

class ProLogger:
    def __init__(self, placeholder, prog_bar, base_pct, span_pct, status_prefix):
        self.placeholder = placeholder
        self.prog_bar = prog_bar
        self.base_pct = base_pct
        self.span_pct = span_pct
        self.status_prefix = status_prefix

    def __call__(self, **kwargs):
        pass # Compatibility

    def callback(self, **kwargs):
        pass # Compatibility

    def message(self, msg): pass
    def start(self): pass
    def stop(self): pass
    
    def __getattr__(self, name):
        def method(*args, **kwargs):
            if name == "callback":
                try:
                    # MoviePy 2.x passes progress info here
                    if 'index' in kwargs and 'total' in kwargs:
                        p = int(kwargs['index'] / kwargs['total'] * self.span_pct)
                        current = min(self.base_pct + p, 99)
                        update_smart_progress(self.placeholder, self.prog_bar, current, self.status_prefix)
                except: pass
        return method

def prepare_arabic_text(text: str) -> str:
    # Essential for fixing "###" and reversed words
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

@st.cache_resource(show_spinner=False)
def load_whisper_model(size):
    # Optimize for CPU (Streamlit Cloud)
    return whisper.load_model(size, device="cpu")

def transcribe_audio(path, size):
    words = []
    try:
        model = load_whisper_model(size)
        # fp16=False is mandatory for CPU execution
        result = model.transcribe(path, language="ar", word_timestamps=True, fp16=False, verbose=False)
        
        if not result or not isinstance(result, dict):
            return []

        segments = result.get("segments", [])
        if segments:
            for seg in segments:
                if seg and "words" in seg:
                    for w in seg["words"]:
                        words.append({
                            "word": w.get("word", "").strip(), 
                            "start": w.get("start", 0), 
                            "end": w.get("end", 0)
                        })
        
        # Fallback to text split if no word timestamps
        if not words and result.get("text"):
            text = result["text"].split()
            try:
                audio_clip = AudioFileClip(path)
                duration = audio_clip.duration
                audio_clip.close()
                chunk_dur = duration / len(text) if text else 0
                for i, word in enumerate(text):
                    words.append({"word": word, "start": i * chunk_dur, "end": (i+1) * chunk_dur})
            except: pass
    except Exception as e:
        st.error(f"خطأ في التحليل الذكي: {e}")
            
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

def build_video_ultra(video_path, audio_path, words, font_size, out_path, sp_placeholder, prog_bar, selected_font_path):
    audio, bg, final = None, None, None
    try:
        if not video_path or not os.path.exists(video_path):
            raise ValueError("فشل في العثور على ملف الفيديو الخلفية.")
        if not audio_path or not os.path.exists(audio_path):
            raise ValueError("فشل في العثور على ملف الصوت.")
        if not words or not isinstance(words, list):
            raise ValueError("لم يتم تحليل كلمات الصوت بشكل صحيح.")

        update_smart_progress(sp_placeholder, prog_bar, 40, "🚀 جاري تهيئة الموارد الفنية...")
        audio = AudioFileClip(audio_path)
        bg = VideoFileClip(video_path).without_audio()
        
        # Perfect Duration Sync
        update_smart_progress(sp_placeholder, prog_bar, 45, "⏳ مطابقة زمن الفيديو مع التلاوة...")
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

        update_smart_progress(sp_placeholder, prog_bar, 55, "✍️ جاري معالجة النصوص والتشكيل العربي...")
        word_clips = []
        full_font_path = os.path.abspath(selected_font_path)
        if not os.path.exists(full_font_path):
            full_font_path = os.path.abspath(FONT_FILENAME)
        
        for w in words:
            if not isinstance(w, dict) or "word" not in w: continue
            shaped = prepare_arabic_text(w["word"])
            try:
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
                t_clip = t_clip.with_start(w.get("start", 0)).with_duration(max(w.get("end", 0) - w.get("start", 0), 0.15))\
                             .with_position(("center", VIDEO_H * 0.72))
                word_clips.append(t_clip)
            except: pass

        update_smart_progress(sp_placeholder, prog_bar, 65, "🎬 جاري الدمج النهائي (ذكاء خارق)...")
        
        valid_clips = [bg, overlay] + [c for c in word_clips if c is not None]
        if not valid_clips:
            raise ValueError("فشل في إنشاء مقاطع الفيديو.")

        final = CompositeVideoClip(valid_clips, size=(VIDEO_W, VIDEO_H))
        final = final.with_audio(audio).with_duration(audio.duration)
        
        update_smart_progress(sp_placeholder, prog_bar, 75, "⚙️ جاري التصدير النهائي... (قد يستغرق دقائق)")
        
        final.write_videofile(
            out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast",
            logger=None, # Set to None to avoid NoneType iterator issues
            threads=4,
            temp_audiofile=os.path.join(tempfile.gettempdir(), f"audio_{int(time.time())}.m4a"),
            remove_temp=True
        )
        update_smart_progress(sp_placeholder, prog_bar, 100, "✅ تم الإنتاج بنجاح!")
        return True
    except Exception as e:
        raise e
    finally:
        try:
            if audio: audio.close()
            if bg: bg.close()
            if final: final.close()
        except: pass

# ==================== UI Setup ====================
with st.sidebar:
    st.markdown("## ⚡ التحكم الذكي")
    api_key = st.text_input("مفتاح Pexels", type="password", value=os.getenv("PEXELS_API_KEY", ""))
    video_query = st.text_input("موضوع البحث", value="peaceful clouds nature")
    
    st.divider()
    st.markdown("### 🖋️ إعدادات الخط")
    available_fonts = get_available_fonts()
    
    # Debug: Show how many fonts were found
    if len(available_fonts) <= 1:
        st.warning("⚠️ لم يتم العثور على خطوط إضافية.")
        with st.expander("🤔 لماذا لا تظهر خطوطي؟"):
            st.write("""
            1. **تأكد من الرفع:** يجب رفع مجلد الخطوط بالكامل إلى GitHub.
            2. **اسم المجلد:** يفضل أن يكون اسم المجلد بسيطاً مثل `fonts` وبدون مسافات.
            3. **صيغة الملفات:** يجب أن تنتهي الخطوط بـ `.ttf` أو `.otf`.
            """)
    else:
        st.success(f"✅ تم العثور على {len(available_fonts)-1} خطوط إضافية.")

    font_choice = st.selectbox("اختر الخط العربي", options=list(available_fonts.keys()))
    selected_font_path = available_fonts[font_choice]
    
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
            if st.button("بدء تحليل الصوت الذكي"):
                sp_ana = st.empty()
                prog_ana = st.progress(0)
                update_smart_progress(sp_ana, prog_ana, 10, "🧠 جاري تحميل نموذج الذكاء الاصطناعي...")
                
                # Custom transcription with progress
                model = load_whisper_model(whisper_size)
                update_smart_progress(sp_ana, prog_ana, 30, "🎙️ جاري تحليل الكلمات ومزامنة التوقيت...")
                
                st.session_state['words'] = transcribe_audio(st.session_state['ap'], whisper_size)
                
                update_smart_progress(sp_ana, prog_ana, 100, "✅ اكتمل تحليل النص بنجاح!")
                st.success("✅ تم استخراج الكلمات بدقة!")
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

        if st.button("🎬 ابدأ الإنتاج الآن"):
            if mode == "تلقائي من Pexels" and not api_key: st.error("أدخل مفتاح Pexels أولاً!")
            elif mode == "رفع يدوي" and not v_in: st.error("ارفع فيديو أولاً!")
            else:
                try:
                    sp = st.empty()
                    prog = st.progress(0)
                    
                    if mode == "تلقائي من Pexels":
                        update_smart_progress(sp, prog, 10, "🌐 جاري البحث عن خلفية سينمائية...")
                        v_in = fetch_pexels_video(video_query, api_key)
                    
                    update_smart_progress(sp, prog, 35, "📥 جاري تحميل موارد الفيديو...")
                    out_name = f"Quran_Studio_{datetime.now().strftime('%M%S')}.mp4"
                    out_path = os.path.abspath(os.path.join(ARCHIVE_DIR, out_name))
                    
                    if build_video_ultra(v_in, st.session_state['ap'], st.session_state['words'], font_size, out_path, sp, prog, selected_font_path):
                        st.balloons()
                        st.session_state['last_v'] = out_path
                        st.rerun() # Refresh to show in archive
                except Exception as e:
                    st.error(f"خطأ في الإنتاج: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    if 'last_v' in st.session_state:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.subheader("🎉 تم إنتاج الفيديو الجديد!")
        st.video(st.session_state['last_v'])
        with open(st.session_state['last_v'], "rb") as f:
            st.download_button("📥 تحميل الفيديو", f, os.path.basename(st.session_state['last_v']), "video/mp4")
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    vids = get_archive_list()
    if vids:
        st.markdown(f"### 📂 تم العثور على ({len(vids)}) فيديوهات")
        for v in vids:
            with st.expander(f"🎬 {v}"):
                v_path = os.path.abspath(os.path.join(ARCHIVE_DIR, v))
                st.video(v_path)
                c1, c2 = st.columns(2)
                with c1:
                    with open(v_path, "rb") as f:
                        st.download_button("📥 تحميل", f, v, "video/mp4", key=f"dl_{v}")
                with c2:
                    if st.button("🗑️ حذف", key=f"del_{v}"):
                        os.remove(v_path)
                        st.rerun()
    else: st.info("الأرشيف فارغ حالياً. ابدأ بإنتاج أول فيديو لك!")

st.markdown("<p style='text-align: center; color: #444; margin-top: 2rem;'>صُنع لخدمة القرآن الكريم ❤️</p>", unsafe_allow_html=True)
