import streamlit as st
import os
import whisper
import subprocess
import requests
import random
# الاستدعاء المتوافق والمستقر مع إدارات MoviePy الحالية
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip

# حل مشكلة تشكيل الحروف العربية المعكوسة والمقطوعة
try:
    from arabic_reshaper import reshape
except ImportError:
    def reshape(text): return text

try:
    from bidi.algorithm import get_display
except ImportError:
    def get_display(text): return text

# ==========================================
# 1. إعدادات الصفحة وحفظ بيانات الجلسة (Session State)
# ==========================================
st.set_page_config(page_title="Quran Studio Ultra AI", page_icon="🕋", layout="wide")

if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "words_data" not in st.session_state:
    st.session_state.words_data = None
if "transcribed" not in st.session_state:
    st.session_state.transcribed = False
if "pexels_video_url" not in st.session_state:
    st.session_state.pexels_video_url = None

# تعريف المجلدات والمسارات الثابتة بناءً على هيكلة مشروعك
ARCHIVE_DIR = "produced_videos"
FONTS_DIR = "font_Arabic"

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

# تعديل كود الـ CSS وتغيير المعامل إلى الاسم الصحيح والمستقر منعاً للـ TypeError
st.markdown("""
    <style>
    .main { background-color: #0d0e12; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    h1, h2, h3 { text-align: right; direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

st.title("🕋 استوديو القرآن الخارق Ultra AI")
st.subheader("الإصدار المستقر والكامل للإنتاج التلقائي عبر الإنترنت")

# أزرار التنقل الرئيسية والتطبيق المتكامل للتحكم بالصفحات
tab_selection = st.radio("تصفح الأقسام:", ["🚀 إنتاج فيديو جديد", "📁 أرشيف الفيديوهات المنتجة"], horizontal=True)
st.write("---")

# ==========================================
# 2. القائمة الجانبية (شريط الإعدادات المتكامل)
# ==========================================
st.sidebar.header("⚡ التحكم الذكي")
pexels_key = st.sidebar.text_input("مفتاح Pexels API Key", type="password", help="أدخل مفتاح بيكسلز للحصول على خلفيات تلقائية")

st.sidebar.write("---")
st.sidebar.header("🎨 إعدادات الخط")
font_size = st.sidebar.slider("حجم الخط القرآني", 30, 120, 60)
text_color = st.sidebar.color_picker("لون الخط المتبع", "#FFFFFF")

# دالة ذكية للبحث التلقائي عن الخطوط العربية داخل مجلد النظام الخاص بك
def get_available_fonts():
    fonts = {"الخط الافتراضي (Amiri)": "Amiri"}
    if os.path.exists(FONTS_DIR):
        for f in os.listdir(FONTS_DIR):
            if f.endswith(('.ttf', '.otf')):
                fonts[f] = os.path.join(FONTS_DIR, f)
    return fonts

all_fonts = get_available_fonts()
selected_font_label = st.sidebar.selectbox("اختر الخط العربي المتاح", list(all_fonts.keys()))
font_path = all_fonts[selected_font_label]

st.sidebar.write("---")
st.sidebar.header("🎬 إعدادات الفيديو")
video_aspect = st.sidebar.selectbox("أبعاد الفيديو المطلوبة", ["(Portrait) 9:16 - تيك توك وشورتس", "(Landscape) 16:9 - يوتيوب وأفقي"])
model_size = st.sidebar.selectbox("دقة الذكاء الاصطناعي للمزامنة", ["tiny", "base", "small"], index=0)

if "(Portrait)" in video_aspect:
    target_size = (1080, 1920)
else:
    target_size = (1920, 1080)

# ==========================================
# 3. الدوال البرمجية المساعدة (الصوت، المزامنة، وجلب الخلفيات)
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

def download_pexels_video(query, api_key):
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=3"
    try:
        response = requests.get(url, headers=headers).json()
        videos = response.get("videos", [])
        if videos:
            selected_video = random.choice(videos)
            video_files = selected_video.get("video_files", [])
            for vf in video_files:
                if vf.get("quality") == "hd" or "1080" in str(vf.get("width")):
                    return vf.get("link")
            return video_files[0].get("link")
    except Exception as e:
        st.error(f"حدث خطأ أثناء الاتصال بخوادم Pexels: {e}")
    return None

def format_arabic(text):
    return get_display(reshape(text))

# ==========================================
# 4. معالجة وتوجيه واجهة المستخدم والصفحات
# ==========================================
if tab_selection == "📁 أرشيف الفيديوهات المنتجة":
    st.header("📁 مستودع الفيديوهات المخزنة")
    all_videos = [v for v in os.listdir(ARCHIVE_DIR) if v.endswith(".mp4")] if os.path.exists(ARCHIVE_DIR) else []
    if all_videos:
        for vid in all_videos:
            with st.expander(f"🎬 مقطع جاهز: {vid}"):
                st.video(os.path.join(ARCHIVE_DIR, vid))
    else:
        st.info("لم يتم تصدير أو العثور على أي مقاطع فيديو في الأرشيف حتى الآن.")

else:
    # صفحة إنتاج وتوليد المقاطع
    col1, col2 = st.columns(2)

    with col1:
        st.header("🎵 1. رفع مقطع الصوت")
        uploaded_audio = st.file_uploader("قم برفع ملف التلاوة الصوتية", type=["mp3", "wav", "m4a", "ogg"])
        
        if uploaded_audio:
            if st.button("بدء تحليل الصوت كلمة بكلمة", type="primary"):
                with st.spinner("جاري تهيئة الصوت وحل مشاكل الترميز الذاتي..."):
                    st.session_state.audio_path = process_and_standardize_audio(uploaded_audio)
                
                with st.spinner("يقوم الذكاء الاصطناعي بربط ومزامنة النصوص الآن..."):
                    st.session_state.words_data = transcribe_voice(st.session_state.audio_path, model_size)
                    st.session_state.transcribed = True
                st.success("🟢 تمت عملية المزامنة بنجاح كامل!")

    with col2:
        st.header("🔍 2. حالة المزامنة الذكية")
        if st.session_state.transcribed:
            st.metric(label="مستوى الجاهزية والربط", value="100% جاهز للدمج")
            with st.expander("استعراض تفاصيل النصوص والتوقيت الزمني"):
                st.write(st.session_state.words_data)
        else:
            st.info("بانتظار رفع الملف الصوتي والضغط على زر التحليل والمزامنة...")

    st.write("---")
    st.header("🎬 3. اختيار خلفية الفيديو والإنتاج النهائي")
    
    bg_mode = st.radio("حدد نوع ومصدر خلفية الفيديو:", ["رفع فيديو مخصص من جهازك", "سحب تلقائي من خوادم الذكاء الاصطناعي (Pexels)"], horizontal=True)
    bg_video_path = None
    
    if bg_mode == "رفع فيديو مخصص من جهازك":
        uploaded_video = st.file_uploader("اختر فيديو الخلفية السينمائي", type=["mp4", "mov", "avi"])
        if uploaded_video:
            bg_video_path = "temp_bg_video.mp4"
            with open(bg_video_path, "wb") as f:
                f.write(uploaded_video.getbuffer())
    else:
        search_query = st.text_input("اكتب موضوع البحث بالإنجليزية (مثال: islamic mosque, abstract dark clouds)", value="peaceful nature")
        if pexels_key:
            if st.button("🔍 ابحث عن فيديو خلفية مناسب وحمله تلقائياً"):
                with st.spinner("جاري جلب واختيار أفضل خلفية متحركة تناسب تلاوتك من Pexels..."):
                    video_url = download_pexels_video(search_query, pexels_key)
                    if video_url:
                        st.session_state.pexels_video_url = video_url
                        st.success("🟢 تم اختيار الفيديو بنجاح وهو جاهز للتجميع الآن!")
                    else:
                        st.error("لم نتمكن من جلب فيديوهات، حاول مراجعة المفتاح أو تغيير نص البحث.")
            if st.session_state.pexels_video_url:
                st.info("الخلفية المسحوبة من الإنترنت جاهزة ومثبتة للدمج الآن.")
                bg_video_path = st.session_state.pexels_video_url
        else:
            st.warning("لاستخدام ميزة السحب والبحث التلقائي، يرجى كتابة مفتاح API Key الخاص بموقع Pexels في القائمة الجانبية.")

    # زر معالجة ورندرة الفيديو السينمائي الكبير الشامل
    if st.session_state.transcribed and bg_video_path:
        st.write("---")
        if st.button("🚀 البدء في دمج وإنتاج الفيديو السينمائي المحترف بالكامل", type="secondary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("مرحلة 1: جاري ضبط وتجهيز الفيديو الخلفي والأبعاد المحددة...")
                audio_clip = AudioFileClip(st.session_state.audio_path)
                bg_clip = VideoFileClip(bg_video_path)
                
                # تغيير الحجم والأبعاد ديناميكياً لتناسب أبعاد التيك توك أو اليوتيوب المختارة
                bg_clip = bg_clip.resized(target_size)
                
                if bg_clip.duration < audio_clip.duration:
                    bg_clip = bg_clip.with_duration(audio_clip.duration)
                else:
                    bg_clip = bg_clip.with_subclip(0, audio_clip.duration)
                    
                progress_bar.progress(30)
                status_text.text("مرحلة 2: تطبيق طبقة التعتيم السينمائي التلقائي بنسبة 33% لإبراز النصوص...")
                
                dark_overlay = ColorClip(size=bg_clip.size, color=(0, 0, 0)).with_duration(bg_clip.duration).with_opacity(0.33)
                faded_bg_clip = CompositeVideoClip([bg_clip, dark_overlay])
                
                progress_bar.progress(60)
                status_text.text("مرحلة 3: رندرة ومزامنة نصوص الآيات مع دمج التأثيرات المحدثة الحالية...")
                
                text_clips = []
                for item in st.session_state.words_data:
                    fixed_text = format_arabic(item["text"])
                    
                    txt_clip = TextClip(
                        text=fixed_text, 
                        font=font_path, 
                        font_size=font_size, 
                        color=text_color,
                        size=(faded_bg_clip.w - 100, None)
                    )
                    
                    # الربط الزمني الدقيق لكل كلمة
                    txt_clip = txt_clip.with_start(item["start"]).with_end(item["end"]).with_position(('center', 'center'))
                    
                    # معالجة تأثيرات الحركة التلاشية المستقرة لتجنب أي خطأ برمي
                    try:
                        txt_clip = txt_clip.crossfadein(0.15).crossfadeout(0.15)
                    except AttributeError:
                        pass  # الاحتفاظ بالحالة في حال عدم دعم النسخة للتلاشي بشكل مباشر
                        
                    text_clips.append(txt_clip)
                    
                final_video = CompositeVideoClip([faded_bg_clip] + text_clips).with_audio(audio_clip)
                
                progress_bar.progress(80)
                status_text.text("مرحلة 4: تصدير ورندرة مقطع الفيديو النهائي والترميز التلقائي للهواتف...")
                
                unique_id = random.randint(1000, 9999)
                output_filename = os.path.join(ARCHIVE_DIR, f"quran_video_{unique_id}.mp4")
                
                final_video.write_videofile(
                    output_filename, 
                    fps=24, 
                    codec="libx264", 
                    audio_codec="aac",
                    threads=4,
                    logger=None
                )
                
                progress_bar.progress(100)
                status_text.text("🎉 اكتمل تصدير وإنتاج الفيديو بنجاح تام!")
                st.success("تم إنتاج وتوليد الفيديو القرآني الخاص بك باحترافية كاملة!")
                
                # إظهار الفيديو للمشاهدة والتحميل الفوري
                st.video(output_filename)
                with open(output_filename, "rb") as file:
                    st.download_button(
                        label="📥 تحميل ملف الفيديو بدقة عالية وجاهز للنشر الفوري",
                        data=file,
                        file_name=f"Quran_Cinematic_{unique_id}.mp4",
                        mime="video/mp4"
                    )
                
                bg_clip.close()
                audio_clip.close()
                
            except Exception as e:
                st.error(f"توقفت عملية التصدير بسبب الخطأ التالي: {str(e)}")
    else:
        if not st.session_state.transcribed:
            st.info("💡 تلميح: عند إتمام الخطوة الأولى (رفع الصوت وتحليله)، سيفتح لك نظام تصدير الفيديو والتحكم الشامل هنا مباشرة.")
