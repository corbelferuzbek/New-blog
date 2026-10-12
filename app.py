import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from werkzeug.utils import secure_filename

app = Flask(__name__)
@app.template_filter('kun')
def kun_filter(date_str):
    # Bu yerda sanani kerakli formatga o'tkazishingiz yoki shunchaki o'zini qaytarishingiz mumkin
    if not date_str:
        return ""
    # Misol uchun, sananing faqat sana qismini olish yoki formatlash
    return str(date_str).split("T")[0]
app.secret_key = os.environ.get("SECRET_KEY", "maxfiy-kalit-soz")

# Supabase ulanishini sozlash
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

BUCKET_NAME = "blog-files"  # Supabase Storage'dagi bucket nomi

# ==================== ASOSIY SAHIFLAR ====================

@app.route("/")
def index():
    # Supabase'dan postlarni olish
    try:
        response = supabase.table("posts").select("*").order("id", desc=True).execute()
        posts = response.data if response.data else []
    except Exception as e:
        print(f"Xatolik (posts): {e}")
        posts = []
    return render_template("index.html", posts=posts)

@app.route("/post/<int:post_id>")
def post(post_id):
    # Muayyan postni ID bo'yicha olish
    try:
        response = supabase.table("posts").select("*").eq("id", post_id).execute()
        posts = response.data
        if not posts:
            return render_template("404.html"), 404
        return render_template("post.html", post=posts[0])
    except Exception as e:
        print(f"Xatolik (post): {e}")
        return render_template("404.html"), 404


# ==================== ADMIN VA EDITOR ====================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        admin_user = os.environ.get("ADMIN_USER", "admin")
        admin_pass = os.environ.get("ADMIN_PASS", "parol")
        
        if username == admin_user and password == admin_pass:
            session["logged_in"] = True
            return redirect(url_for("admin"))
        else:
            flash("Login yoki parol xato!")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

@app.route("/admin")
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    try:
        response = supabase.table("posts").select("*").order("id", desc=True).execute()
        posts = response.data if response.data else []
    except Exception as e:
        posts = []
        
    return render_template("admin.html", posts=posts)

@app.route("/editor", methods=["GET", "POST"])
def editor():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        
        if title and content:
            try:
                supabase.table("posts").insert({"title": title, "content": content}).execute()
            except Exception as e:
                print(f"Post qo'shish xatoligi: {e}")
                
        return redirect(url_for("admin"))
        
    return render_template("editor.html")


# ==================== FAYLLAR VA SUPABASE STORAGE ====================

@app.route("/files")
def files_page():
    # Hamma (oddiy foydalanuvchilar ham) ko'rishi mumkin bo'lgan fayllar sahifasi
    files_list = []
    try:
        response = supabase.storage.from_(BUCKET_NAME).list()
        if response:
            for file in response:
                filename = file['name']
                # Supabase'dan faylning public havolasini olish
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
                files_list.append({
                    "name": filename,
                    "url": public_url,
                    "date": file.get('updated_at', '')
                })
    except Exception as e:
        print(f"Fayllarni olishda xatolik: {e}")
        
    return render_template("files.html", files=files_list)

@app.route("/admin/files", methods=["GET", "POST"])
def admin_files():
    # Fayl yuklash va boshqarish faqat admin uchun
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file_bytes = file.read()
            
            try:
                # Supabase Storage'ga yuklash
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=filename,
                    file=file_bytes,
                    file_options={"content-type": file.content_type, "upsert": "true"}
                )
            except Exception as e:
                print(f"Fayl yuklash xatoligi: {e}")
                
            return redirect(url_for("admin_files"))
            
    # Admin uchun fayllar ro'yxatini olish
    files_list = []
    try:
        response = supabase.storage.from_(BUCKET_NAME).list()
        if response:
            for file in response:
                filename = file['name']
                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(filename)
                files_list.append({
                    "name": filename,
                    "url": public_url,
                    "date": file.get('updated_at', '')
                })
    except Exception as e:
        print(f"Admin fayllarni olish xatoligi: {e}")
        
    return render_template("admin_files.html", files=files_list)

@app.route("/admin/files/delete/<filename>", methods=["POST"])
def delete_file(filename):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
        
    try:
        supabase.storage.from_(BUCKET_NAME).remove([filename])
    except Exception as e:
        print(f"Faylni o'chirish xatoligi: {e}")
        
    return redirect(url_for("admin_files"))


# ==================== ISHGA TUSHIRISH ====================

if __name__ == "__main__":
    app.run(debug=True)
