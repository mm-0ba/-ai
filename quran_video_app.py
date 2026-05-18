import streamlit as st
import os
import whisper
import subprocess
import requests
import random
# الاستدعاء الصحيح والمتوافق مع الإصدارات الحديثة لـ moviepy
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip

# محاولة استدعاء مكتبات معالجة اللغة العربية لمنع مشكلة الحروف المقطوعة
try:
    from arabic_reshaper import reshape
except ImportError:
    def reshape(text): return text

try:
    from bidi.algorithm import get_display
except ImportError:
    def get_display(text): return text

# ==========================================
# 1. تهيئة إعدادات الصفحة وذاكرة الجلسة المستمرة (Session State)
# ==========================================
st.set_page_config(page_title="Quran Studio Ultra AI", page_icon="🕋", layout="wide")

# حفظ الحالة لمنع اختفاء البيانات عند تحديث الصفحة أو الضغط على الأزرار
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "words_data" not in st.session_state:
    st.session_state.words_data = None
if "transcribed" not in st.session_state:
    st.session_state.transcribed = False
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "🚀 إنتاج فيديو جديد"
if "pexels_video_url" not in st.session_state:
    st.session_state.pexels_video_url = None

# إنشاء المجلدات الأساسية لتخزين البيانات والخطوط
os.makedirs("produced_videos", exist_ok=True)
os.makedirs("font_Arabic", exist_ok=True)

# تصفيف شكل التطبيق بإضافة لمسات CSS سينمائية ناعمة
st.markdown("""
    <style>
    .main { background-color: #0d0e12; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    h1, h2, h3 { text-align: right; direction: rtl; }
    div.stHeadingContainer { text-align: right; }
    </style>
    """, unsafe_style_html=True)

# ترويسة التطبيق الرئيسية
st.title("🕋 استوديو القرآن الخارق Ultra AI")
st.subheader("الإصدار المستقر والأسرع للإنتاج الذكي عبر الإنترنت")

# شريط التنقل العلوي المتكامل لتغيير الصفحات
tab_selection = st.radio(
    "تصفح الأقسام:",
    ["🚀 إنتاج فيديو جديد", "📁 أرشيف الفيديوهات المنتجة"],
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state.current_tab = tab_selection
st.write("---")

# ==========================================
# 2. القائمة الجانبية: التحكم الذكي والإعدادات بالكامل
# ==========================================
st.sidebar.header("⚡ التحكم الذكي")

# إدخال مفتاح Pexels للبحث التلقائي عن الخلفيات الملونة والمتحركة
pexels_key = st.sidebar.text_input("مفتاح Pexels API Key", type="password", help="أدخل مفتاح بيكسلز للحصول على فيديوهات تلقائية بجودة عالية")

st.sidebar.write("---")
st.sidebar.header("🎨 إعدادات الخط")

# التحكم بحجم ولون الخط
font_size = st.sidebar.slider("حجم الخط", 30, 120, 60)
text_color = st.sidebar.color_picker("لون الخط المتبع", "#FFFFFF")

# جلب الخطوط المرفوعة تلقائياً في مجلد font_Arabic
available_fonts = [f for f in os.listdir("font_Arabic") if f.endswith(('.ttf', '.otf'))]
if available_fonts:
    selected_font_file = st.sidebar.selectbox("اختر الخط العربي المرفوع", available_fonts)
    font_path = os.path.join("font_Arabic", selected_font_file)
    st.sidebar.success("🟢 تم العثور على خطوط مخصصة جاهزة")
else:
    st.sidebar.warning("⚠️ لم يتم العثور على خطوط في مجلد font_Arabic، سيتم استخدام الخط الافتراضي.")
    font_path = "Amiri"

st.sidebar.write("---")
st.sidebar.header("🎬 إعدادات الفيديو")

# التحكم بأبعاد الفيديو المطلوبة والتنقل التلقائي بين الطول والعرض
video_aspect = st.sidebar.selectbox("أبعاد الفيديو المطلوبة", ["(Portrait) 9:16 - تيك توك وشورتس", "(Landscape) 16:9 - يوتيوب وأفقي"])
model_size = st.sidebar.selectbox("دقة الذكاء الاصطناعي للمزامنة", ["tiny", "base", "small"], index=0)

# تحديد عرض وارتفاع أبعاد الفيديو بناءً على الاختيار
if "(Portrait)" in video_aspect:
    target_size = (1080, 1920)
else:
    target_size = (1920, 1080)

# ==========================================
# 3. دالات معالجة الصوت والذكاء الاصطناعي وجلب الفيديوهات
# ==========================================
def process_and_standardize_audio(uploaded_file):
    """تحويل ترميز الصوت إجبارياً لمنع خطأ الـ Tensor الأحمر على السيرفر"""
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
    """استخراج الكلمات بالتوقيت الدقيق باستخدام Whisper"""
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
    """البحث التلقائي عن فيديوهات طبيعية متحركة من Pexels وتحميلها"""
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5"
    try:
        response = requests.get(url, headers=headers).json()
        videos = response.get("videos", [])
        if videos:
            selected_video = random.choice(videos)
            # اختيار ملف الفيديو الأعلى جودة والمناسب
            video_files = selected_video.get("video_files", [])
            for vf in video_files:
                if vf.get("quality") == "hd" or "1080" in str(vf.get("width")):
                    return vf.get("link")
            return video_files[0].get("link")
    except Exception as e:
        st.error(f"فشل الاتصال بـ Pexels: {e}")
    return None

def format_arabic(text):
    return get_display(reshape(text))

# ==========================================
# 4. إدارة الواجهات والصفحات النشطة
# ==========================================
if st.session_state.current_tab == "📁 أرشيف الفيديوهات المنتجة":
    st.header("📁 أرشيف ومخزن الفيديوهات الجاهزة")
    all_videos = [v for v in os.listdir("produced_videos") if v.endswith(".mp4")]
    if all_videos:
        for vid in all_videos:
            with st.expander(f"🎬 فيديو مخرج: {vid}"):
                st.video(os.path.join("produced_videos", vid))
    else:
        st.info("لا توجد فيديوهات منتجة في الأرشيف حالياً، ابدأ بإنتاج أول فيديو الآن!")

else:
    # واجهة إنتاج فيديو جديد
    col1, col2 = st.columns(2)

    with col1:
        st.header("🎵 1. رفع الصوت والتحليل")
        uploaded_audio = st.file_uploader("اختر ملف التلاوة أو الصوت", type=["mp3", "wav", "m4a", "ogg"])
        
        if uploaded_audio:
            if st.button("بدء تحليل الصوت كلمة بكلمة", type="primary"):
                with st.spinner("جاري معالجة الصوت وحل مشاكل الترميز الذاتي..."):
                    st.session_state.audio_path = process_and_standardize_audio(uploaded_audio)
                
                with st.spinner("يقوم الذكاء الاصطناعي الآن بربط الكلمات بالتوقيت..."):
                    st.session_state.words_data = transcribe_voice(st.session_state.audio_path, model_size)
                    st.session_state.transcribed = True
                st.success("🟢 اكتمل تحليل ومزامنة الصوت بنجاح!")

    with col2:
        st.header("🔍 2. حالة المزامنة الذكية")
        if st.session_state.transcribed:
            st.metric(label="جاهزية المزامنة والتوقيت", value="100% جاهز")
            with st.expander("استعراض تفاصيل النصوص"):
                st.write(st.session_state.words_data)
        else:
            st.info("في انتظار رفع المقطع الصوتي والضغط على زر التحليل...")

    st.write("---")
    st.header("🎬 3. اختيار خلفية الفيديو والإنتاج السينمائي")
    
    # اختيار الخلفية: إما يدوي أو عبر Pexels تلقائياً
    bg_mode = st.radio("مصدر فيديو الخلفية:", ["رفع فيديو مخصص من جهازك", "البحث التلقائي عبر الذكاء الاصطناعي (Pexels)"], horizontal=True)
    
    bg_video_path = None
    
    if bg_mode == "رفع فيديو مخصص من جهازك":
        uploaded_video = st.file_uploader("ارفع فيديو الخلفية", type=["mp4", "mov", "avi"])
        if uploaded_video:
            bg_video_path = "temp_bg_video.mp4"
            with open(bg_video_path, "wb") as f:
                f.write(uploaded_video.getbuffer())
    else:
        search_query = st.text_input("موضوع البحث (مثال: peaceful clouds nature)", value="peaceful clouds nature")
        if pexels_key:
            if st.button("🔍 ابحث عن فيديو خلفية مناسب وحمله"):
                with st.spinner("جاري سحب أفضل فيديو متناسق ومتحرك من خوادم Pexels..."):
                    video_url = download_pexels_video(search_query, pexels_key)
                    if video_url:
                        st.session_state.pexels_video_url = video_url
                        st.success("🟢 تم العثور على فيديو مناسب وحفظه بنجاح!")
                    else:
                        st.error("لم نتمكن من العثور على فيديوهات بهذا العنوان، جرب كلمات أخرى.")
            if st.session_state.pexels_video_url:
                st.info("فيديو الخلفية المستهدف جاهز الآن للإنتاج.")
                bg_video_path = st.session_state.pexels_video_url
        else:
            st.warning("الرجاء إدخال مفتاح Pexels API Key في القائمة الجانبية لتتمكن من استخدام البحث التلقائي.")

    # زر الإنتاج النهائي الكبير الشامل
    if st.session_state.transcribed and bg_video_path:
        st.write("---")
        if st.button("🚀 البدء في دمج وإنتاج الفيديو السينمائي المحترف بالكامل", type="secondary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                status_text.text("مرحلة 1: جاري تهيئة وقص مسارات الصوت وفيديو الخلفية المختار...")
                audio_clip = AudioFileClip(st.session_state.audio_path)
                
                # فتح مقطع الفيديو سواء كان رابط إنترنت أو ملف محلي
                bg_clip = VideoFileClip(bg_video_path)
                
                # تعديل أبعاد الفيديو لتتناسب مع خيار تيك توك أو يوتيوب المختار في القائمة الجانبية
                bg_clip = bg_clip.resized(target_size)
                
                if bg_clip.duration < audio_clip.duration:
                    bg_clip = bg_clip.with_duration(audio_clip.duration)
                else:
                    bg_clip = bg_clip.with_subclip(0, audio_clip.duration)
                    
                progress_bar.progress(30)
                status_text.text("مرحلة 2: تطبيق تعتيم سينمائي تلقائي بنسبة 33% لإبراز الآيات والنصوص بشكل جذاب...")
                
                # تطبيق التعتيم المتوافق
                dark_overlay = ColorClip(size=bg_clip.size, color=(0, 0, 0)).with_duration(bg_clip.duration).with_opacity(0.33)
                faded_bg_clip = CompositeVideoClip([bg_clip, dark_overlay])
                
                progress_bar.progress(60)
                status_text.text("مرحلة 3: دمج النصوص القرآنية المزامنة وتطبيق تأثيرات التلاشي والظهور الناعم...")
                
                text_clips = []
                for item in st.session_state.words_data:
                    fixed_text = format_arabic(item["text"])
                    
                    # صياغة TextClip بالطريقة الجديدة والمستقرة لمنع الكراش
                    txt_clip = TextClip(
                        text=fixed_text, 
                        font=font_path, 
                        font_size=font_size, 
                        color=text_color,
                        size=(faded_bg_clip.w - 100, None)
                    )
                    
                    # المزامنة مع حركات التلاشي الصحيحة (crossfadein) المتوافقة تماماً
                    txt_clip = txt_clip.with_start(item["start"]).with_end(item["end"]).with_position(('center', 'center'))
                    txt_clip = txt_clip.crossfadein(0.15).crossfadeout(0.15)
                    text_clips.append(txt_clip)
                    
                final_video = CompositeVideoClip([faded_bg_clip] + text_clips).with_audio(audio_clip)
                
                progress_bar.progress(80)
                status_text.text("مرحلة 4: رندرة وتصدير الفيديو النهائي المجمع بأعلى صيغة توافقية...")
                
                # توليد اسم فريد لكل فيديو منتج للحفاظ عليه في الأرشيف
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
                status_text.text("🎉 اكتمل تصدير الفيديو والإنتاج بنجاح تام!")
                st.success("مبروك يا محمد! تم دمج الآيات وخلفيتك المفضلة بإنتاج متكامل!")
                
                # عرض الفيديو للمشاهدة والتحميل المباشر
                st.video(output_filename)
                with open(output_filename, "rb") as file:
                    st.download_button(
                        label="📥 تحميل ملف الفيديو بدقة عالية جاهز للنشر",
                        data=file,
                        file_name=f"Quran_Cinematic_{unique_id}.mp4",
                        mime="video/mp4"
                    )
                
                bg_clip.close()
                audio_clip.close()
                
            except Exception as e:
                st.error(f"توقف معالج الإنتاج بسبب الخطأ التالي: {str(e)}")
    else:
        if not st.session_state.transcribed:
            st.info("💡 نصيحة: بمجرد إتمام الخطوة رقم 1 (تحليل الصوت)، ستفتح لك بوابة خيارات تصدير الفيديو بالكامل هنا.")
