import streamlit as st
import os
import whisper
import subprocess
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from arabic_reshaper import reshape
from bidi.algorithm import get_display

# ==========================================
# 1. إعدادات الصفحة وذاكرة الجلسة (Session State)
# ==========================================
st.set_page_config(page_title="استوديو القرآن الخارق", page_icon="🕋", layout="wide")

# منع التطبيق من إعادة تعيين البيانات عند التفاعل
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "words_data" not in st.session_state:
    st.session_state.words_data = None
if "transcribed" not in st.session_state:
    st.session_state.transcribed = False

# إنشاء المجلدات الأساسية إذا لم تكن موجودة
os.makedirs("produced_videos", exist_ok=True)
os.makedirs("font_Arabic", exist_ok=True)

st.title("🕋 استوديو القرآن الخارق Ultra AI")
st.subheader("الإصدار المستقر والأسرع للإنتاج عبر الإنترنت")
st.write("---")

# القائمة الجانبية للتحكم الذكي
st.sidebar.header("⚡ التحكم الذكي")
model_size = st.sidebar.selectbox("دقة الذكاء الاصطناعي", ["tiny", "base", "small"], index=0)
font_size = st.sidebar.slider("حجم الخط", 30, 100, 60)
text_color = st.sidebar.color_picker("لون الخط المتبع", "#FFFFFF")

# البحث عن الخط المتاح في مجلد font_Arabic
available_fonts = [f for f in os.listdir("font_Arabic") if f.endswith(('.ttf', '.otf'))]
if available_fonts:
    selected_font_file = st.sidebar.selectbox("اختر الخط العربي", available_fonts)
    font_path = os.path.join("font_Arabic", selected_font_file)
else:
    st.sidebar.warning("لم يتم العثور على خطوط في مجلد font_Arabic، سيتم استخدام الخط الافتراضي.")
    font_path = "Amiri" # خط احتياطي للنظام

# ==========================================
# 2. دالات معالجة الصوت والنصوص (الذكاء الاصطناعي)
# ==========================================
def process_and_standardize_audio(uploaded_file):
    """تحويل الصوت إجبارياً باستخدام ffmpeg النظام مباشرة لتفادي مشاكل توافقية بايثون 3.14"""
    temp_input_path = "temp_input_audio" + os.path.splitext(uploaded_file.name)[1]
    with open(temp_input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    standard_wav_path = "standard_audio.wav"
    if os.path.exists(standard_wav_path):
        os.remove(standard_wav_path)
    
    # استدعاء أمر ffmpeg من النظام مباشرة (آمن ومستقر 100%)
    cmd = [
        "ffmpeg", "-y", "-i", temp_input_path,
        "-ar", "16000", "-ac", "1", standard_wav_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # تنظيف الملف المؤقت الأصلي
    if os.path.exists(temp_input_path):
        os.remove(temp_input_path)
    return standard_wav_path

def transcribe_voice(audio_path, size):
    """تحليل الصوت واستخراج الكلمات مع التوقيت الدقيق لكل كلمة"""
    model = whisper.load_model(size, device="cpu")
    # إجبار fp16=False لأن سيرفر Streamlit يعتمد على الـ CPU
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
    """إصلاح مشكلة الحروف المقطوعة والمعكوسة في مكتبات الفيديو"""
    reshaped_text = reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# ==========================================
# 3. واجهة المستخدم والتفاعل (Streamlit UI)
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.header("🎵 1. رفع الصوت")
    uploaded_audio = st.file_uploader("اختر ملف التلاوة (MP3, WAV, M4A, etc.)", type=["mp3", "wav", "m4a", "ogg"])
    
    if uploaded_audio:
        if st.button("بدء تحليل الصوت كلمة بكلمة", type="primary"):
            with st.spinner("جاري تهيئة وترميز الصوت بدقة سينمائية..."):
                st.session_state.audio_path = process_and_standardize_audio(uploaded_audio)
            
            with st.spinner("ذكاء الـ Whisper يقوم بمزامنة الكلمات الآن..."):
                st.session_state.words_data = transcribe_voice(st.session_state.audio_path, model_size)
                st.session_state.transcribed = True
            st.success("اكتمل تحليل النص والمزامنة بنجاح!")

with col2:
    st.header("🔍 2. التحليل الذكي للآيات")
    if st.session_state.transcribed:
        st.metric(label="حالة المزامنة", value="100% جاهز")
        with st.expander("عرض الكلمات المستخرجة وتوقيتها"):
            st.write(st.session_state.words_data)
    else:
        st.info("انتظار رفع الصوت والتحليل...")

st.write("---")
st.header("🎬 3. إعداد الفيديو والتصدير النهائي")

uploaded_video = st.file_uploader("ارفع فيديو الخلفية من جهازك", type=["mp4", "mov", "avi"])

if st.session_state.transcribed and uploaded_video:
    if st.button("🚀 البدء في إنتاج الفيديو السينمائي المحترف"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("مرحلة 1: جاري معالجة فيديو الخلفية وضبط الأبعاد...")
            temp_vid_path = "temp_bg_video.mp4"
            with open(temp_vid_path, "wb") as f:
                f.write(uploaded_video.getbuffer())
            
            progress_bar.progress(25)
            
            audio_clip = AudioFileClip(st.session_state.audio_path)
            bg_clip = VideoFileClip(temp_vid_path)
            
            if bg_clip.duration < audio_clip.duration:
                bg_clip = bg_clip.loop(duration=audio_clip.duration)
            else:
                bg_clip = bg_clip.subclip(0, audio_clip.duration)
                
            progress_bar.progress(50)
            status_text.text("مرحلة 2: تطبيق تعتيم سينمائي بنسبة 33% لحماية ووضوح النص...")
            
            # تطبيق التعتيم بنسبة 33% عبر طبقة سوداء شفافة تبرز النص القرآني
            dark_overlay = ColorClip(size=bg_clip.size, color=(0, 0, 0)).set_duration(bg_clip.duration).set_opacity(0.33)
            faded_bg_clip = CompositeVideoClip([bg_clip, dark_overlay])
            
            progress_bar.progress(70)
            status_text.text("مرحلة 3: دمج النصوص القرآنية وتطبيق تأثيرات التلاشي (Fade)...")
            
            text_clips = []
            for item in st.session_state.words_data:
                fixed_text = format_arabic(item["text"])
                
                txt_clip = TextClip(
                    fixed_text, 
                    fontsize=font_size, 
                    color=text_color, 
                    font=font_path,
                    method='caption',
                    size=(faded_bg_clip.w - 100, None)
                )
                
                txt_clip = txt_clip.set_start(item["start"]).set_end(item["end"]).set_position(('center', 'center'))
                # تطبيق تأثير تلاشي ناعم عند الدخول والخروج (0.15 ثانية) لمظهر سينمائي مريح
                txt_clip = txt_clip.crossfadein(0.15).crossfadeout(0.15)
                text_clips.append(txt_clip)
                
            final_video = CompositeVideoClip([faded_bg_clip] + text_clips).set_audio(audio_clip)
            
            progress_bar.progress(85)
            status_text.text("مرحلة 4: تصدير ملف الفيديو النهائي بأعلى دقة سينمائية...")
            
            output_filename = "produced_videos/quran_final_master.mp4"
            final_video.write_videofile(
                output_filename, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac",
                threads=4,
                logger=None
            )
            
            progress_bar.progress(100)
            status_text.text("🎉 تم الإنتاج بنجاح واكتمال العمل!")
            st.success("تم توليد الفيديو القرآني بنجاح واحترافية متناهية!")
            
            with open(output_filename, "rb") as file:
                st.download_button(
                    label="📥 تحميل الفيديو القرآني النهائي بدقة HD",
                    data=file,
                    file_name="Quran_Cinematic_Video.mp4",
                    mime="video/mp4"
                )
                
            bg_clip.close()
            audio_clip.close()
            if os.path.exists(temp_vid_path):
                os.remove(temp_vid_path)
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء الإنتاج والتصدير: {str(e)}")
else:
    if not st.session_state.transcribed:
        st.warning("رجاءً قم بتحليل ملف الصوت أولاً من الخطوة رقم 1.")
    if not uploaded_video:
        st.warning("رجاءً ارفع فيديو الخلفية لتتمكن من الدمج والإنتاج.")
