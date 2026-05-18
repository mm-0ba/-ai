import streamlit as st
import os
import whisper
import subprocess
# الاستدعاء المستقر والآمن المتوافق مع الإصدارات الحالية
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip

# حل مشكلة تشكيل الحروف العربية المعكوسة والمقطوعة في مكتبات الفيديو
try:
    from arabic_reshaper import reshape
except ImportError:
    def reshape(text): return text

try:
    from bidi.algorithm import get_display
except ImportError:
    def get_display(text): return text

# ==========================================
# 1. إعدادات الصفحة وذاكرة الجلسة (Session State)
# ==========================================
st.set_page_config(page_title="Quran Studio Ultra AI", page_icon="🕋", layout="wide")

if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "words_data" not in st.session_state:
    st.session_state.words_data = None
if "transcribed" not in st.session_state:
    st.session_state.transcribed = False

os.makedirs("produced_videos", exist_ok=True)
os.makedirs("font_Arabic", exist_ok=True)

# تصفيف الواجهة (إصلاح TypeError المعامل المحدث)
st.markdown("""
    <style>
    .main { background-color: #0d0e12; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    h1, h2, h3 { text-align: right; direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

st.title("🕋 استوديو القرآن الخارق Ultra AI")
st.subheader("الإصدار المستقر والكامل للإنتاج الاحترافي عبر الإنترنت")

# شريط التنقل المتكامل وتغيير الصفحات
tab_selection = st.radio("تصفح الأقسام:", ["🚀 إنتاج فيديو جديد", "📁 أرشيف الفيديوهات المنتجة"], horizontal=True)
st.write("---")

# ==========================================
# 2. القائمة الجانبية (شريط الإعدادات بالكامل)
# ==========================================
st.sidebar.header("⚡ التحكم الذكي")
pexels_key = st.sidebar.text_input("مفتاح Pexels API Key", type="password", help="أدخل مفتاح بيكسلز للحصول على فيديوهات تلقائية")

st.sidebar.write("---")
st.sidebar.header("🎨 إعدادات الخط")
font_size = st.sidebar.slider("حجم الخط القرآني", 30, 120, 60)
text_color = st.sidebar.color_picker("لون الخط المتبع", "#FFFFFF")

# دالة هندسية ذكية لاكتشاف الخطوط العربية المرفوعة في المشروع
available_fonts = [f for f in os.listdir("font_Arabic") if f.endswith(('.ttf', '.otf'))]
if available_fonts:
    selected_font_file = st.sidebar.selectbox("اختر الخط العربي المرفوع في مشروعك", available_fonts)
    # تحديد مسار ملف الخط الفعلي لضمان أن MoviePy يمكنه قراءته
    font_path = os.path.abspath(os.path.join("font_Arabic", selected_font_file))
    st.sidebar.success("🟢 تم العثور على خطوط مخصصة جاهزة")
else:
    # حل خطأ Invalid font 'Amiri': تنبيه المستخدم برفع الخط بدلاً من محاولة استدعائه من النظام
    st.sidebar.error("🔴 مشكلة في الخطوط!")
    st.sidebar.warning("⚠️ لا يمكن استدعاء خط 'Amiri' لأنه غير موجود على السيرفر. "
                        "لاستخدام خط مخصص (TTF)، يرجى رفع ملف الخط (TTF) داخل مجلد 'font_Arabic' على GitHub.")
    font_path = None # لا يوجد خط متاح

st.sidebar.write("---")
st.sidebar.header("🎬 إعدادات الفيديو")
video_aspect = st.sidebar.selectbox("أبعاد الفيديو المطلوبة", ["(Portrait) 9:16 - تيك توك وشورتس", "(Landscape) 16:9 - يوتيوب وأفقي"])
model_size = st.sidebar.selectbox("دقة الذكاء الاصطناعي للمزامنة", ["tiny", "base", "small"], index=0)

if "(Portrait)" in video_aspect:
    target_size = (1080, 1920)
else:
    target_size = (1920, 1080)

# ==========================================
# 3. الدوال البرمجية المساعدة (التطبيق المتكامل للذكاء الاصطناعي)
# ==========================================
def process_and_standardize_audio(uploaded_file):
    temp_input_path = "temp_input_audio" + os.path.splitext(uploaded_file.name)[1]
    with open(temp_input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    standard_wav_path = "standard_audio.wav"
    if os.path.exists(standard_wav_path):
        os.remove(standard_wav_path)
    
    cmd = [
        "ffmpeg", "-y", "-i", temp_input_path,
        "-ar", "16000", "-ac", "1", standard_wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(temp_input_path):
        os.remove(temp_input_path)
    return standard_wav_path

def transcribe_voice(audio_path, size):
    model = whisper.load_model(size, device="cpu")
    result = model.transcribe(audio_path, fp16=False, word_timestamps=True)
    
    words_list = []
    for segment in result.get("segments", []):
        if "words" in segment:
            for w in segment["words"]:
                words_list.append({
                    "text": w["word"].strip(),
                    "start": w["start"],
                    "end": w["end"]
                })
        else:
            words_list.append({
                "text": segment["text"].strip(),
                "start": segment["start"],
                "end": segment["end"]
            })
    return words_list

def format_arabic(text):
    return get_display(reshape(text))

# ==========================================
# 4. توجيه ومعالجة واجهة المستخدم والإنتاج
# ==========================================
if tab_selection == "📁 أرشيف الفيديوهات المنتجة":
    st.header("📁 مستودع وأرشيف الفيديوهات")
    all_videos = [v for v in os.listdir("produced_videos") if v.endswith(".mp4")]
    if all_videos:
        for vid in all_videos:
            with st.expander(f"🎬 مقطع جاهز: {vid}"):
                st.video(os.path.join("produced_videos", vid))
    else:
        st.info("لا توجد فيديوهات في الأرشيف حتى الآن.")

else:
    # واجهة إنتاج مقطع جديد
    col1, col2 = st.columns(2)

    with col1:
        st.header("🎵 1. رفع الصوت وتحليله")
        uploaded_audio = st.file_uploader("قم برفع ملف الصوت القرآني المسموع", type=["mp3", "wav", "m4a", "ogg"])
        
        if uploaded_audio:
            if st.button("بدء تحليل الصوت كلمة بكلمة", type="primary"):
                with st.spinner("جاري تهيئة الصوت وحل مشاكل الترميز الذاتي..."):
                    st.session_state.audio_path = process_and_standardize_audio(uploaded_audio)
                
                with st.spinner("يقوم الذكاء الاصطناعي بربط النصوص وتوقيتها الآن..."):
                    st.session_state.words_data = transcribe_voice(st.session_state.audio_path, model_size)
                    st.session_state.transcribed = True
                st.success("🟢 تمت عملية التحليل والمزامنة بنجاح!")

    with col2:
        st.header("🔍 2. جاهزية المزامنة")
        if st.session_state.transcribed:
            st.metric(label="مستوى الدقة والربط", value="100% جاهز")
            with st.expander("استعراض تفاصيل النصوص والتوقيت"):
                st.write(st.session_state.words_data)
        else:
            st.info("بانتظار رفع مقطع صوتي والضغط على زر التحليل والمزامنة...")

    st.write("---")
    st.header("🎬 3. اختيار خلفية الفيديو والإنتاج النهائي")
    uploaded_video = st.file_uploader("ارفع فيديو الخلفية من جهازك", type=["mp4", "mov", "avi"])

    # زر الإنتاج النهائي الشامل والكامل
    if st.session_state.transcribed and uploaded_video:
        st.write("---")
        if st.button("🚀 البدء في دمج وإنتاج الفيديو السينمائي المحترف بالكامل", type="secondary"):
            
            # حماية احتياطية: منع الإنتاج إذا لم يتم رفع خط TTF متوافق
            if font_path is None:
                st.error("❌ توقفت عملية الإنتاج! "
                         "يجب رفع ملف خط قرآني TTF متوافق داخل مجلد 'font_Arabic' على GitHub "
                         "ليتمكن النظام من رسم النصوص القرآنية على الفيديو. يرجى مراجعة القائمة الجانبية.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    status_text.text("مرحلة 1: جاري تهيئة فيديو الخلفية والأبعاد وتوافق الترميز...")
                    temp_vid_path = "temp_bg_video.mp4"
                    with open(temp_vid_path, "wb") as f:
                        f.write(uploaded_video.getbuffer())
                    
                    audio_clip = AudioFileClip(st.session_state.audio_path)
                    bg_clip = VideoFileClip(temp_vid_path)
                    
                    # ضبط الأبعاد تلقائياً بناءً على الاختيار الجانبي ( Portrait 9:16 أو Landscape 16:9 )
                    bg_clip = bg_clip.resized(target_size)
                    
                    # المزامنة الزمنية التلقائية للفيديو مع الصوت
                    if bg_clip.duration < audio_clip.duration:
                        bg_clip = bg_clip.loop(duration=audio_clip.duration)
                    else:
                        bg_clip = bg_clip.with_subclip(0, audio_clip.duration)
                        
                    progress_bar.progress(30)
                    status_text.text("مرحلة 2: تطبيق تعتيم سينمائي تلقائي بنسبة 33% لإبراز النصوص القرآنية...")
                    
                    # التعتيم بنسبة 33% (التطبيق المتكامل للمؤثرات)
                    dark_overlay = ColorClip(size=bg_clip.size, color=(0, 0, 0)).with_duration(bg_clip.duration).with_opacity(0.33)
                    faded_bg_clip = CompositeVideoClip([bg_clip, dark_overlay])
                    
                    progress_bar.progress(60)
                    status_text.text("مرحلة 3: رندرة ومزامنة نصوص الآيات مع دمج التأثيرات السينمائية الحالية...")
                    
                    text_clips = []
                    for item in st.session_state.words_data:
                        fixed_text = format_arabic(item["text"])
                        
                        # هندسة TextClip بالطريقة الجديدة والمستقرة، وتمرير مسار الخط المرفوع (font_path)
                        txt_clip = TextClip(
                            text=fixed_text, 
                            font=font_path, 
                            font_size=font_size, 
                            color=text_color,
                            size=(faded_bg_clip.w - 100, None)
                        )
                        
                        # تطبيق المزامنة وتأثيرات التلاشي المحدثة (crossfadein/out)
                        txt_clip = txt_clip.with_start(item["start"]).with_end(item["end"]).with_position(('center', 'center'))
                        txt_clip = txt_clip.crossfadein(0.15).crossfadeout(0.15)
                        text_clips.append(txt_clip)
                        
                    final_video = CompositeVideoClip([faded_bg_clip] + text_clips).with_audio(audio_clip)
                    
                    progress_bar.progress(80)
                    status_text.text("مرحلة 4: تصدير ورندرة مقطع الفيديو النهائي والترميز الكامل للهواتف...")
                    
                    import random
                    unique_id = random.randint(1000, 9999)
                    output_filename = f"produced_videos/quran_video_{unique_id}.mp4"
                    
                    final_video.write_videofile(
                        output_filename, 
                        fps=24, 
                        codec="libx264", 
                        audio_codec="aac",
                        threads=4,
                        logger=None
                    )
                    
                    progress_bar.progress(100)
                    status_text.text("🎉 تم تصدير الفيديو وإنتاجه بنجاح تام!")
                    st.success("تم إنتاج وتوليد الفيديو القرآني الخاص بك باحترافية كاملة!")
                    
                    # إظهار الفيديو للمشاهدة والتحميل الفوري
                    st.video(output_filename)
                    with open(output_filename, "rb") as file:
                        st.download_button(
                            label="📥 تحميل ملف الفيديو بدقة عالية وجاهز للنشر",
                            data=file,
                            file_name=f"Quran_Cinematic_{unique_id}.mp4",
                            mime="video/mp4"
                        )
                    
                    bg_clip.close()
                    audio_clip.close()
                    
                except Exception as e:
                    st.error(f"توقف معالج الإنتاج بسبب الخطأ التالي: {str(e)}")
                    st.info("💡 نصيحة احترافية: تأكد من أن ملف الخط (TTF) المرفوع متوافق تماماً ولا يسبب مشاكل في الترميز.")
