import os
import re
import tempfile
import requests
import streamlit as st
import whisper
import arabic_reshaper
from bidi.algorithm import get_display
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip, concatenate_videoclips
import moviepy.video.fx as vfx
import shutil
import time
import subprocess
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
AMIRI_FONT_URL = "https://github.com/googlefonts/amiri/raw/main/fonts/ttf/Amiri-Regular.ttf"
FONT_FILENAME = "Amiri-Regular.ttf"
FONTS_DIR = "fonts"
ARCHIVE_DIR = "produced_videos"

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# ==================== Session State Initialization ====================
if 'transcription_done' not in st.session_state:
    st.session_state['transcription_done'] = False
if 'words' not in st.session_state:
    st.session_state['words'] = []
if 'last_v' not in st.session_state:
    st.session_state['last_v'] = None
if 'audio_path' not in st.session_state:
    st.session_state['audio_path'] = None

# ==================== Helper Functions ====================
def get_available_fonts():
    """Lists all fonts with extreme robust searching (local & recursive)"""
    fonts = { "الخط الافتراضي (Amiri)": FONT_FILENAME }
    if os.path.exists(FONTS_DIR):
        try:
            for f in os.listdir(FONTS_DIR):
                if f.lower().endswith(('.ttf', '.otf')):
                    name = f.replace("ArbFONTS-", "").replace(".ttf", "").replace(".otf", "").replace("-", " ").replace("_", " ")
                    fonts[name] = os.path.abspath(os.path.join(FONTS_DIR, f))
        except: pass
    try:
        cwd = os.getcwd()
        for root, dirs, files in os.walk(cwd):
            if any(part.startswith('.') for part in root.split(os.sep)): continue
            if root == os.path.abspath(FONTS_DIR): continue
            for f in files:
                if f.lower().endswith(('.ttf', '.otf')):
                    if f == FONT_FILENAME: continue
                    name = f.replace("ArbFONTS-", "").replace(".ttf", "").replace(".otf", "").replace("-", " ").replace("_", " ")
                    full_path = os.path.abspath(os.path.join(root, f))
                    if name not in fonts: fonts[name] = full_path
    except: pass
    return fonts

def check_ffmpeg():
    if shutil.which("ffmpeg"): return shutil.which("ffmpeg")
    common = ["C:\\ffmpeg\\bin\\ffmpeg.exe", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
    for p in common:
        if os.path.exists(p): return p
    return None

def convert_audio_for_whisper(input_path):
    """Converts audio to a standard WAV format to fix Tensor 0 elements error"""
    output_path = tempfile.mktemp(suffix=".wav")
    try:
        # Standardize to 16kHz, Mono, WAV
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-ar', '16000', '-ac', '1', '-vn',
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path
    except Exception as e:
        st.error(f"خطأ في تحويل ملف الصوت: {e}")
        return input_path

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
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; direction: rtl; text-align: right; }
    .stApp { background: #050505; color: #ffffff; }
    .stButton>button {
        background: linear-gradient(135deg, #2e7d32 0%, #1b5e20 100%) !important;
        color: white !important; border-radius: 12px !important; padding: 12px 24px !important;
        font-weight: 700 !important; border: 1px solid rgba(255,255,255,0.1) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important; transition: all 0.3s ease !important;
        width: 100%;
    }
    .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 20px rgba(46, 125, 50, 0.4) !important; }
    .progress-container { background: rgba(255,255,255,0.05); border-radius: 20px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); text-align: center; margin: 20px 0; }
    .percentage-display { font-size: 4rem; font-weight: 900; background: linear-gradient(to right, #4caf50, #81c784); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; }
    .status-text { font-size: 1.1rem; color: #81c784; margin-top: 10px; }
    .studio-header { background: linear-gradient(180deg, #1b5e20 0%, #050505 100%); padding: 3rem 1rem; border-radius: 0 0 40px 40px; text-align: center; border-bottom: 1px solid #2e7d32; margin-bottom: 2rem; }
    .studio-card { background: #0f0f0f; border-radius: 25px; padding: 1.5rem; border: 1px solid #1e1e1e; margin-bottom: 1.5rem; }
    h1, h2, h3 { color: #81c784 !important; }
    .stProgress > div > div > div > div { background-color: #4caf50; }
    </style>
    """, unsafe_allow_html=True)

# ==================== Core Functions ====================
def update_smart_progress(placeholder, progress_bar, percentage, status_msg):
    progress_bar.progress(percentage / 100)
    placeholder.markdown(f"""
        <div class="progress-container">
            <div class="percentage-display">{percentage}%</div>
            <div class="status-text">{status_msg}</div>
        </div>
    """, unsafe_allow_html=True)

def prepare_arabic_text(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

@st.cache_resource(show_spinner=False)
def load_whisper_model(size):
    return whisper.load_model(size, device="cpu")

def transcribe_audio_logic(path, size):
    words = []
    try:
        # Step 1: Force conversion to standard WAV
        std_audio_path = convert_audio_for_whisper(path)
        
        # Step 2: Load model and transcribe with fp16=False
        model = load_whisper_model(size)
        result = model.transcribe(std_audio_path, language="ar", word_timestamps=True, fp16=False, verbose=False)
        
        if not result or not isinstance(result, dict): return []
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
        
        # Cleanup temp audio
        if std_audio_path != path:
            try: os.remove(std_audio_path)
            except: pass
            
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

def build_video_ultra(video_path, audio_path, words, font_size, out_path, sp_placeholder, prog_bar, selected_font_path, aspect_ratio):
    audio, bg, final = None, None, None
    try:
        if not video_path or not os.path.exists(video_path): raise ValueError("فشل في العثور على ملف الفيديو الخلفية.")
        if not audio_path or not os.path.exists(audio_path): raise ValueError("فشل في العثور على ملف الصوت.")
        if not words or not isinstance(words, list): raise ValueError("لم يتم تحليل كلمات الصوت بشكل صحيح.")

        update_smart_progress(sp_placeholder, prog_bar, 40, "🚀 جاري تهيئة الموارد الفنية...")
        
        # Target Dimensions
        if aspect_ratio == "9:16 (Portrait)": target_w, target_h = 1080, 1920
        else: target_w, target_h = 1920, 1080

        audio = AudioFileClip(audio_path)
        bg = VideoFileClip(video_path).without_audio()
        
        # Dimming (33% darkness)
        bg = bg.fx(vfx.colorx, 0.67)
        
        # Perfect Duration Sync
        update_smart_progress(sp_placeholder, prog_bar, 45, "⏳ مطابقة زمن الفيديو مع التلاوة...")
        if bg.duration < audio.duration:
            loops = int(audio.duration // bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        bg = bg.subclipped(0, audio.duration)

        # Smart Resize & Crop
        update_smart_progress(sp_placeholder, prog_bar, 50, "📐 ضبط مقاسات الشاشة والتغطية...")
        bg_aspect = bg.w / bg.h
        target_aspect = target_w / target_h
        
        if bg_aspect > target_aspect:
            bg = bg.resized(height=target_h)
            x_center = bg.w / 2
            bg = bg.cropped(x1=x_center - target_w / 2, x2=x_center + target_w / 2)
        else:
            bg = bg.resized(width=target_w)
            y_center = bg.h / 2
            bg = bg.cropped(y1=y_center - target_h / 2, y2=y_center + target_h / 2)

        update_smart_progress(sp_placeholder, prog_bar, 55, "✍️ جاري معالجة النصوص وتأثيرات الظهور...")
        word_clips = []
        full_font_path = os.path.abspath(selected_font_path)
        if not os.path.exists(full_font_path): full_font_path = os.path.abspath(FONT_FILENAME)
        
        for w in words:
            if not isinstance(w, dict) or "word" not in w: continue
            shaped = prepare_arabic_text(w["word"])
            try:
                t_clip = TextClip(
                    text=shaped, font=full_font_path, font_size=font_size, 
                    color="white", stroke_color="black", stroke_width=1.5, 
                    method="label", text_align="center"
                )
                start_t = w.get("start", 0)
                dur = max(w.get("end", 0) - start_t, 0.2)
                
                # Cinematic Fade In/Out
                t_clip = t_clip.with_start(start_t).with_duration(dur)\
                             .with_position(("center", target_h * 0.75))\
                             .with_fadein(0.2).with_fadeout(0.2)
                word_clips.append(t_clip)
            except: pass

        update_smart_progress(sp_placeholder, prog_bar, 65, "🎬 جاري الدمج النهائي (ذكاء خارق)...")
        valid_clips = [bg] + [c for c in word_clips if c is not None]
        final = CompositeVideoClip(valid_clips, size=(target_w, target_h))
        final = final.with_audio(audio).with_duration(audio.duration)
        
        update_smart_progress(sp_placeholder, prog_bar, 75, "⚙️ جاري التصدير النهائي... (قد يستغرق دقائق)")
        final.write_videofile(
            out_path, fps=24, codec="libx264", audio_codec="aac", 
            preset="ultrafast", logger=None, threads=4,
            temp_audiofile=os.path.join(tempfile.gettempdir(), f"audio_{int(time.time())}.m4a"),
            remove_temp=True
        )
        update_smart_progress(sp_placeholder, prog_bar, 100, "✅ تم الإنتاج بنجاح!")
        return True
    except Exception as e: raise e
    finally:
        try:
            if audio: audio.close()
            if bg: bg.close()
            if final: final.close()
        except: pass

# ==================== Sidebar Setup ====================
with st.sidebar:
    st.markdown("## ⚡ التحكم الذكي")
    api_key = st.text_input("مفتاح Pexels", type="password", value=os.getenv("PEXELS_API_KEY", ""))
    video_query = st.text_input("موضوع البحث", value="peaceful nature clouds")
    
    st.divider()
    st.markdown("### 🖋️ إعدادات الخط")
    available_fonts = get_available_fonts()
    if len(available_fonts) <= 1:
        st.warning("⚠️ لم يتم العثور على خطوط إضافية.")
    font_choice = st.selectbox("اختر الخط العربي", options=list(available_fonts.keys()))
    selected_font_path = available_fonts[font_choice]
    font_size = st.slider("حجم الخط", 60, 250, 120)
    
    st.divider()
    st.markdown("### 🎬 إعدادات الفيديو")
    aspect_ratio = st.selectbox("أبعاد الفيديو", ["9:16 (Portrait)", "16:9 (Landscape)"])
    whisper_size = st.selectbox("دقة الذكاء الاصطناعي", ["tiny", "base"], index=0)
    
    st.divider()
    if check_ffmpeg(): st.success("✅ النظام جاهز (FFmpeg)")
    download_font()
    if os.path.exists(FONT_FILENAME): st.success("✅ الخط الافتراضي جاهز")

# ==================== Studio UI ====================
st.markdown('<div class="studio-header"><h1>🕋 استوديو القرآن الخارق</h1><p>الإصدار السينمائي المطور | دمج الذكاء الاصطناعي والجماليات</p></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 إنتاج فيديو سينمائي", "📂 أرشيف الفيديوهات"])

with tab1:
    st.markdown('<div class="studio-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎵 1. رفع الصوت")
        aud_file = st.file_uploader("اختر ملف التلاوة", type=["mp3", "wav", "m4a", "ogg"])
        if aud_file:
            # Check if this is a new file
            if st.session_state.get('last_uploaded_name') != aud_file.name:
                st.session_state['transcription_done'] = False
                st.session_state['words'] = []
                st.session_state['last_v'] = None
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{aud_file.name}") as t:
                    t.write(aud_file.getvalue())
                    st.session_state['audio_path'] = t.name
                st.session_state['last_uploaded_name'] = aud_file.name
            
            st.audio(aud_file)
            
    with c2:
        if aud_file:
            st.subheader("🔍 2. التحليل الذكي")
            # Persistent analysis button status
            if not st.session_state['transcription_done']:
                if st.button("بدء تحليل الصوت كلمة بكلمة"):
                    sp_ana = st.empty(); prog_ana = st.progress(0)
                    update_smart_progress(sp_ana, prog_ana, 10, "🧠 تحويل الصوت وتحميل Whisper...")
                    st.session_state['words'] = transcribe_audio_logic(st.session_state['audio_path'], whisper_size)
                    st.session_state['transcription_done'] = True
                    st.rerun()
            else:
                st.success(f"✅ تم تحليل ({len(st.session_state['words'])}) كلمة بنجاح!")
                if st.button("🔄 إعادة التحليل"):
                    st.session_state['transcription_done'] = False
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state['transcription_done']:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.subheader("🎬 3. التصدير النهائي")
        mode = st.radio("خلفية الفيديو:", ["تلقائي من Pexels", "رفع يدوي"], horizontal=True)
        v_in = None
        if mode == "رفع يدوي":
            up_v = st.file_uploader("ارفع فيديو (MP4)", type=["mp4"])
            if up_v:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as t:
                    t.write(up_v.getvalue()); v_in = t.name

        if st.button("🎬 ابدأ الإنتاج السينمائي الآن"):
            if mode == "تلقائي من Pexels" and not api_key: st.error("أدخل مفتاح Pexels أولاً!")
            elif mode == "رفع يدوي" and not v_in: st.error("ارفع فيديو أولاً!")
            else:
                try:
                    sp = st.empty(); prog = st.progress(0)
                    if mode == "تلقائي من Pexels":
                        update_smart_progress(sp, prog, 10, "🌐 جلب خلفية سينمائية من Pexels...")
                        v_in = fetch_pexels_video(video_query, api_key)
                    
                    update_smart_progress(sp, prog, 35, "📥 جاري تحميل الموارد...")
                    out_name = f"Quran_Studio_{datetime.now().strftime('%M%S')}.mp4"
                    out_path = os.path.abspath(os.path.join(ARCHIVE_DIR, out_name))
                    
                    if build_video_ultra(v_in, st.session_state['audio_path'], st.session_state['words'], font_size, out_path, sp, prog, selected_font_path, aspect_ratio):
                        st.balloons()
                        st.session_state['last_v'] = out_path
                        st.rerun()
                except Exception as e: st.error(f"خطأ في الإنتاج: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state['last_v']:
        st.markdown('<div class="studio-card">', unsafe_allow_html=True)
        st.subheader("🎉 تم الإنتاج بنجاح!")
        st.video(st.session_state['last_v'])
        with open(st.session_state['last_v'], "rb") as f:
            st.download_button("📥 تحميل الفيديو السينمائي", f, os.path.basename(st.session_state['last_v']), "video/mp4")
        st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    vids = get_archive_list()
    if vids:
        st.markdown(f"### 📂 الأرشيف ({len(vids)}) فيديوهات")
        for v in vids:
            with st.expander(f"🎬 {v}"):
                v_path = os.path.abspath(os.path.join(ARCHIVE_DIR, v))
                st.video(v_path)
                c1, c2 = st.columns(2)
                with c1:
                    with open(v_path, "rb") as f: st.download_button("📥 تحميل", f, v, "video/mp4", key=f"dl_{v}")
                with c2:
                    if st.button("🗑️ حذف", key=f"del_{v}"):
                        os.remove(v_path); st.rerun()
    else: st.info("الأرشيف فارغ حالياً.")

st.markdown("<p style='text-align: center; color: #444; margin-top: 2rem;'>صُنع لخدمة القرآن الكريم ❤️</p>", unsafe_allow_html=True)
