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
    page_title="Quran Studio AI | استوديو القرآن الاحترافي",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== Constants & Storage ====================
PEXELS_API_BASE = "https://api.pexels.com/videos"
VIDEO_W, VIDEO_H = 1080, 1920
AMIRI_FONT_URL = "https://github.com/googlefonts/amiri/raw/main/fonts/ttf/Amiri-Regular.ttf"
FONT_FILENAME = "Amiri-Regular.ttf"
ARCHIVE_DIR = "الفيديوهات_المنتجة"

# Ensure output directory exists safely
if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

# ==================== Helper Functions ====================
def check_ffmpeg(manual_path=None):
    if manual_path and os.path.exists(manual_path):
        return manual_path
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    common_roots = ["C:\\", "C:\\Program Files\\"]
    for root in common_roots:
        if not os.path.exists(root): continue
        try:
            for item in os.listdir(root):
                if item.lower().startswith("ffmpeg"):
                    p = os.path.join(root, item, "bin", "ffmpeg.exe")
                    if os.path.exists(p): return p
        except: pass
    return None

def download_font(url, dest):
    if not os.path.exists(dest):
        try:
            r = requests.get(url, timeout=30)
            with open(dest, 'wb') as f:
                f.write(r.content)
            return True
        except: return False
    return True

def get_archive_list():
    if not os.path.exists(ARCHIVE_DIR): return []
    files = [f for f in os.listdir(ARCHIVE_DIR) if f.lower().endswith('.mp4')]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(ARCHIVE_DIR, x)), reverse=True)
    return files

# ==================== Premium UI Styling ====================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Vazirmatn:wght@100;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Vazirmatn', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stApp {
        background: #ffffff;
    }

    /* Studio Layout */
    .studio-header {
        background: linear-gradient(90deg, #1b5e20 0%, #2e7d32 100%);
        padding: 2.5rem;
        border-radius: 0 0 30px 30px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }

    .studio-card {
        background: #ffffff;
        border-radius: 24px;
        padding: 2rem;
        box-shadow: 0 4px 25px rgba(0,0,0,0.05);
        border: 1px solid #f0f2f5;
        margin-bottom: 2rem;
    }

    .step-indicator {
        background: #e8f5e9;
        color: #2e7d32;
        padding: 6px 16px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.9rem;
        display: inline-block;
        margin-bottom: 1rem;
    }

    /* Custom Buttons */
    .stButton>button {
        background: #2e7d32 !important;
        color: white !important;
        border-radius: 14px !important;
        padding: 0.8rem 2rem !important;
        font-weight: 600 !important;
        border: none !important;
        transition: 0.3s ease !important;
        width: 100%;
    }

    .stButton>button:hover {
        background: #1b5e20 !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(46, 125, 50, 0.25);
    }

    /* Sidebar Customization */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-left: 1px solid #e2e8f0;
    }

    /* Gallery Grid */
    .video-grid-item {
        background: #fff;
        border-radius: 15px;
        padding: 10px;
        border: 1px solid #eee;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== Core Logic ====================
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
    params = {"query": query, "orientation": "portrait", "size": "large", "per_page": 5}
    r = requests.get(f"{PEXELS_API_BASE}/search", headers=headers, params=params, timeout=15)
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos: raise RuntimeError("لم يتم العثور على فيديوهات مناسبة في Pexels")
    for v in videos:
        for f in v["video_files"]:
            if f.get("height", 0) >= 1280:
                url = f["link"]
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                with requests.get(url, stream=True, timeout=60) as resp:
                    for chunk in resp.iter_content(1024*1024): tmp.write(chunk)
                tmp.close()
                return tmp.name
    return None

def build_video(video_path, audio_path, words, font_path, font_size, out_path):
    try:
        audio = AudioFileClip(audio_path)
        bg = VideoFileClip(video_path).without_audio()
        
        # Perfect Sync: Loop if shorter, trim if longer
        if bg.duration < audio.duration:
            loops = int(audio.duration // bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        
        # Trim exactly to audio length
        bg = bg.subclipped(0, audio.duration).resized(height=VIDEO_H)
        
        if bg.w > VIDEO_W:
            x_center = bg.w / 2
            bg = bg.cropped(x1=x_center - VIDEO_W / 2, x2=x_center + VIDEO_W / 2)
        else:
            bg = bg.resized(width=VIDEO_W)
            
        overlay = ColorClip(size=(VIDEO_W, 400), color=(0, 0, 0)).with_opacity(0.5)\
                    .with_duration(audio.duration).with_position(("center", int(VIDEO_H * 0.7)))

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

        final = CompositeVideoClip([bg, overlay, *word_clips], size=(VIDEO_W, VIDEO_H))
        final = final.with_audio(audio).with_duration(audio.duration)
        
        # High-Speed Export
        final.write_videofile(
            out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            preset="ultrafast",
            logger=None,
            temp_audiofile=os.path.join(tempfile.gettempdir(), "temp-audio.m4a"),
            remove_temp=True
        )
    finally:
        # Cleanup
        try: audio.close()
        except: pass
        try: bg.close()
        except: pass
        try: final.close()
        except: pass

# ==================== Sidebar Setup ====================
with st.sidebar:
    st.markdown("### 🛠️ لوحة التحكم")
    
    with st.expander("🔑 إعدادات الـ API", expanded=True):
        api_key = st.text_input("مفتاح Pexels", type="password", value=os.getenv("PEXELS_API_KEY", ""))
        st.markdown("[احصل على مفتاحك مجاناً](https://www.pexels.com/api/new/)")
    
    with st.expander("🎨 التنسيق البصري"):
        video_query = st.text_input("موضوع البحث", value="peaceful nature clouds")
        font_size = st.slider("حجم الخط", 40, 150, 85)
    
    with st.expander("⚙️ النظام والذكاء الاصطناعي"):
        whisper_size = st.selectbox("دقة Whisper", ["tiny", "base", "small"], index=1)
        manual_ffmpeg = st.text_input("مسار FFmpeg", placeholder="C:\\ffmpeg\\bin\\ffmpeg.exe")
    
    st.divider()
    ffmpeg_p = check_ffmpeg(manual_ffmpeg)
    if ffmpeg_p:
        st.success("✅ النظام جاهز")
        ffmpeg_dir = os.path.dirname(ffmpeg_p)
        if ffmpeg_dir not in os.environ["PATH"]:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
        os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_p
    else: st.error("❌ FFmpeg مفقود")
    
    if os.path.exists(FONT_FILENAME): st.success("✅ الخط جاهز")
    else:
        if st.button("📥 تحميل الخط العربي"):
            download_font(AMIRI_FONT_URL, FONT_FILENAME)
            st.rerun()

# ==================== Main Studio UI ====================
st.markdown('<div class="studio-header"><h1>🕌 استوديو القرآن الاحترافي</h1><p>حوّل التلاوات العطرة إلى فيديوهات سينمائية مذهلة</p></div>', unsafe_allow_html=True)

tab_create, tab_archive, tab_guide = st.tabs(["🚀 ابدأ الإنتاج", "📂 الأرشيف والمعرض", "📖 كيف يعمل؟"])

with tab_create:
    col_input, col_process = st.columns([1, 1])
    
    with col_input:
        st.markdown('<div class="studio-card"><span class="step-indicator">خطوة 1</span><h3>🎵 اختيار التلاوة</h3>', unsafe_allow_html=True)
        audio_file = st.file_uploader("ارفع ملف الصوت (MP3 / WAV)", type=["mp3", "wav"])
        if audio_file:
            st.audio(audio_file)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_file.getvalue())
                st.session_state['audio_path'] = tmp.name
        st.markdown('</div>', unsafe_allow_html=True)

    with col_process:
        if audio_file:
            st.markdown('<div class="studio-card"><span class="step-indicator">خطوة 2</span><h3>🔍 معالجة الذكاء الاصطناعي</h3>', unsafe_allow_html=True)
            if st.button("تحليل الصوت واستخراج الكلمات"):
                with st.spinner("جاري تحليل التلاوة بدقة..."):
                    st.session_state['words'] = transcribe_audio(st.session_state['audio_path'], whisper_size)
                    st.success("✅ تم استخراج الكلمات بنجاح!")
            
            if 'words' in st.session_state:
                with st.expander("مراجعة النص المستخرج"):
                    st.write(" ".join([w['word'] for w in st.session_state['words']]))
            st.markdown('</div>', unsafe_allow_html=True)

    if 'words' in st.session_state:
        st.markdown('<div class="studio-card"><span class="step-indicator">خطوة 3</span><h3>🎬 اللمسة النهائية والإنتاج</h3>', unsafe_allow_html=True)
        
        source_mode = st.radio("مصدر خلفية الفيديو:", ["البحث التلقائي (Pexels)", "رفع فيديو يدوي"], horizontal=True)
        
        final_v_path = None
        if source_mode == "البحث التلقائي (Pexels)":
            if not api_key: st.warning("يرجى إدخال مفتاح Pexels في لوحة التحكم")
        else:
            up_v = st.file_uploader("اختر فيديو الخلفية (MP4)", type=["mp4"])
            if up_v:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_v:
                    tmp_v.write(up_v.getvalue())
                    final_v_path = tmp_v.name
                st.success("✅ تم رفع الفيديو بنجاح")

        if st.button("🔥 إنتاج وحفظ الفيديو الآن"):
            try:
                if source_mode == "البحث التلقائي (Pexels)" and not api_key: st.error("المفتاح مطلوب!")
                elif source_mode == "رفع فيديو يدوي" and not final_v_path: st.error("ارفع فيديو أولاً!")
                else:
                    msg_box = st.empty()
                    prog_bar = st.progress(0)
                    
                    if source_mode == "البحث التلقائي (Pexels)":
                        msg_box.info("جاري جلب أفضل خلفية سينمائية من Pexels...")
                        final_v_path = fetch_pexels_video(video_query, api_key)
                    
                    prog_bar.progress(30)
                    msg_box.info("جاري مطابقة الزمن ودمج النصوص...")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    save_name = f"Quran_Studio_{timestamp}.mp4"
                    save_full_path = os.path.join(ARCHIVE_DIR, save_name)
                    
                    build_video(final_v_path, st.session_state['audio_path'], st.session_state['words'], FONT_FILENAME, font_size, save_full_path)
                    
                    prog_bar.progress(100)
                    msg_box.success(f"✅ تم الإنتاج بنجاح!")
                    st.balloons()
                    st.session_state['latest_prod'] = save_full_path
            except Exception as e:
                st.error(f"❌ حدث خطأ غير متوقع: {str(e)}")
        st.markdown('</div>', unsafe_allow_html=True)

    if 'latest_prod' in st.session_state:
        st.markdown('<div class="studio-card"><h3>📺 معاينة الفيديو المنتج</h3>', unsafe_allow_html=True)
        st.video(st.session_state['latest_prod'])
        with open(st.session_state['latest_prod'], "rb") as f:
            st.download_button("📥 تحميل الفيديو فوراً", f, os.path.basename(st.session_state['latest_prod']), "video/mp4")
        st.markdown('</div>', unsafe_allow_html=True)

with tab_archive:
    st.title("📂 أرشيف إنتاجاتك")
    archive_files = get_archive_list()
    
    if not archive_files:
        st.info("لا توجد فيديوهات في الأرشيف بعد.")
    else:
        cols = st.columns(3)
        for i, vid in enumerate(archive_files):
            with cols[i % 3]:
                st.markdown(f'<div class="video-grid-item"><b>{vid[:20]}...</b></div>', unsafe_allow_html=True)
                st.video(os.path.join(ARCHIVE_DIR, vid))
                with open(os.path.join(ARCHIVE_DIR, vid), "rb") as f:
                    st.download_button(f"📥 تحميل", f, vid, "video/mp4", key=f"dl_{vid}")
                st.divider()

with tab_guide:
    st.markdown("""
    <div class="studio-card">
    <h3>📖 دليل استخدام استوديو القرآن</h3>
    <p>تم تصميم هذا الاستوديو ليعمل بالكامل عبر الإنترنت دون الحاجة لفتح أي شاشة سوداء على جهازك.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<p style='text-align: center; color: #666; margin-top: 3rem;'>صُنع بكل إخلاص لخدمة كتاب الله ❤️</p>", unsafe_allow_html=True)
