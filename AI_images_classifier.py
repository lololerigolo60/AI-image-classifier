import os
import shutil
import threading
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import ollama
import re
from concurrent.futures import ThreadPoolExecutor

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ImageSorterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Image Classifier - Turbo Edition")
        self.geometry("1000x950")

        self.target_dir = ""
        self.dest_dir = "" 
        self.index_data = {} 
        self.found_images = [] 
        # Détection automatique du nombre de cœurs CPU pour le multithreading
        self.max_workers = os.cpu_count() or 4 

        self.categories = [
            "realism", "comics", "manga", "painting", "watercolor",
            "sport", "urban city", "retro and vintage", "sketch", "portrait",
            "landscape", "architecture", "interior", "fauna", "flora",
            "space", "vehicles", "cyberpunk", "fantasy", "science fiction",
            "steampunk", "horror", "abstract", "minimalism", "caricatures"
        ]

        # --- UI Layout ---
        self.grid_columnconfigure(0, weight=1)

        # --- MODEL BLOCK (Logic inchangée) ---
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=15, padx=20, fill="x")
        ctk.CTkLabel(self.model_frame, text="Ollama Model:", font=("Arial", 12, "bold")).pack(side="left", padx=10)

        self.model_var = ctk.StringVar(value="Loading models...")
        self.combo_models = ctk.CTkComboBox(self.model_frame, variable=self.model_var, width=250, state="disabled")
        self.combo_models.pack(side="left", padx=5, fill="x", expand=True)

        self.btn_refresh = ctk.CTkButton(self.model_frame, text="🔄", width=40, command=self.refresh_models_thread)
        self.btn_refresh.pack(side="left", padx=10)

        # --- DIRECTORY MANAGEMENT ---
        self.dir_frame = ctk.CTkFrame(self)
        self.dir_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkButton(self.dir_frame, text="Source Folder", command=self.browse_source).grid(row=0, column=0, padx=10, pady=5)
        self.lbl_status_source = ctk.CTkLabel(self.dir_frame, text="Not selected", font=("Arial", 10, "italic"))
        self.lbl_status_source.grid(row=0, column=1, sticky="w")

        ctk.CTkButton(self.dir_frame, text="Destination Folder", command=self.browse_dest).grid(row=1, column=0, padx=10, pady=5)
        self.lbl_status_dest = ctk.CTkLabel(self.dir_frame, text="Default: source", font=("Arial", 10, "italic"))
        self.lbl_status_dest.grid(row=1, column=1, sticky="w")

        self.recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.dir_frame, text="Include subfolders", variable=self.recursive_var).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        
        ctk.CTkButton(self.dir_frame, text="Clear AI Cache", fg_color="#c0392b", hover_color="#962d22", command=self.clear_cache).grid(row=2, column=1, padx=10, pady=5, sticky="e")

        # --- TAB SYSTEM ---
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab_sort = self.tabs.add("Automatic Sorting")
        self.tab_search = self.tabs.add("Keyword Search")

        self.setup_sort_tab()
        self.setup_search_tab()

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Ready", font=("Arial", 11))
        self.lbl_status.pack()

        self.refresh_models_thread()

    # --- OPTIMISATION MINIATURES & MULTITHREADING ---
    def get_ai_thumb(self, original_path):
        """Crée ou récupère une miniature pour l'IA (Thread-safe)"""
        if not self.target_dir: return original_path
        try:
            cache_dir = os.path.join(self.target_dir, ".cache_ai")
            if not os.path.exists(cache_dir): os.makedirs(cache_dir)

            file_id = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(original_path))
            thumb_path = os.path.join(cache_dir, f"ai_thumb_{file_id}.jpg")

            if not os.path.exists(thumb_path):
                with Image.open(original_path) as img:
                    img.thumbnail((384, 384), Image.Resampling.LANCZOS)
                    img.convert("RGB").save(thumb_path, "JPEG", quality=75)
            return thumb_path
        except:
            return original_path

    def pre_generate_all_thumbs(self, files):
        """Utilise ThreadPoolExecutor pour créer toutes les miniatures en parallèle."""
        self.lbl_status.configure(text=f"Optimization: Generating thumbnails ({self.max_workers} threads)...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            list(executor.map(self.get_ai_thumb, files))

    def clear_cache(self):
        if not self.target_dir: return
        cache_dir = os.path.join(self.target_dir, ".cache_ai")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            messagebox.showinfo("Cache", "AI Cache cleared.")

    # --- GESTION DES FICHIERS ---
    def get_image_files(self):
        extensions = ('.png', '.jpg', '.jpeg')
        file_list = []
        if not self.target_dir or not os.path.exists(self.target_dir): return []
        
        if self.recursive_var.get():
            for root, dirs, files in os.walk(self.target_dir):
                if ".cache_ai" in root: continue
                for f in files:
                    if f.lower().endswith(extensions):
                        file_list.append(os.path.join(root, f))
        else:
            file_list = [os.path.join(self.target_dir, f) for f in os.listdir(self.target_dir) 
                         if f.lower().endswith(extensions)]
        return file_list

    # --- LOGIQUE OLLAMA MODÈLES ---
    def refresh_models_thread(self):
        self.btn_refresh.configure(state="disabled")
        self.combo_models.configure(state="disabled")
        self.model_var.set("Loading models...")
        threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        try:
            models_info = ollama.list()
            models_list = (models_info.get('models', []) if isinstance(models_info, dict) else getattr(models_info, 'models', []))
            names = []
            for m in models_list:
                if isinstance(m, dict): name = m.get('name') or m.get('model', '')
                else: name = getattr(m, 'name', None) or getattr(m, 'model', '')
                if name: names.append(name)
            self.after(0, self._update_model_ui, names, None)
        except Exception as e:
            self.after(0, self._update_model_ui, [], str(e))

    def _update_model_ui(self, names, error):
        self.btn_refresh.configure(state="normal")
        if error or not names:
            self.lbl_status.configure(text=f"Error or No models", text_color="red")
            self.combo_models.configure(state="normal")
            return
        self.combo_models.configure(values=names, state="normal")
        selected = next((n for n in names if any(k in n.lower() for k in ["llava", "moondream", "qwen-vl"])), names[0])
        self.model_var.set(selected)
        self.lbl_status.configure(text=f"{len(names)} model(s) found", text_color="green")

    # --- INTERFACE ET ACTIONS ---
    def setup_sort_tab(self):
        self.rename_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.tab_sort, text="Smart rename via AI", variable=self.rename_var).pack(pady=10)
        self.entry_frame = ctk.CTkFrame(self.tab_sort, fg_color="transparent")
        self.entry_frame.pack(fill="x", padx=20, pady=5)
        self.entry_cat = ctk.CTkEntry(self.entry_frame, placeholder_text="New category...")
        self.entry_cat.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(self.entry_frame, text="Add", width=80, command=self.add_category).pack(side="right")
        
        self.listbox_cats = ctk.CTkTextbox(self.tab_sort, height=180, cursor="hand2")
        self.listbox_cats.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Réactivation du double-clic
        self.listbox_cats.bind("<Double-Button-1>", self.on_double_click)
        
        self.update_listbox()
        self.btn_start = ctk.CTkButton(self.tab_sort, text="Start Sorting", fg_color="#2ecc71", command=self.start_sorting_thread)
        self.btn_start.pack(pady=15)

    def on_double_click(self, event):
        try:
            line_idx = self.listbox_cats.index(f"@{event.x},{event.y}").split('.')[0]
            cat_name = self.listbox_cats.get(f"{line_idx}.0", f"{line_idx}.end").strip()
            if cat_name in self.categories:
                self.categories.remove(cat_name)
                self.update_listbox()
        except: pass

    def update_listbox(self):
        self.listbox_cats.configure(state="normal")
        self.listbox_cats.delete("1.0", "end")
        for cat in self.categories: self.listbox_cats.insert("end", f"{cat}\n")
        self.listbox_cats.configure(state="disabled")

    def add_category(self):
        cat = self.entry_cat.get().strip().lower()
        if cat and cat not in self.categories:
            self.categories.append(cat); self.update_listbox(); self.entry_cat.delete(0, 'end')

    def setup_search_tab(self):
        f = ctk.CTkFrame(self.tab_search); f.pack(fill="x", padx=10, pady=10)
        self.entry_query = ctk.CTkEntry(f, placeholder_text="Keywords...")
        self.entry_query.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f, text="Search", width=80, command=self.run_search).pack(side="left", padx=2)
        ctk.CTkButton(f, text="Index", width=80, command=self.start_indexing_thread).pack(side="left", padx=2)
        self.search_scroll = ctk.CTkScrollableFrame(self.tab_search, label_text="Results")
        self.search_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.search_scroll.columnconfigure((0,1,2,3), weight=1)

    # --- PERSISTANCE INDEX ---
    def load_index(self):
        idx_path = os.path.join(self.target_dir, "image_index.json")
        if os.path.exists(idx_path):
            with open(idx_path, 'r', encoding='utf-8') as f: self.index_data = json.load(f)

    def save_index(self):
        if not self.target_dir: return
        idx_path = os.path.join(self.target_dir, "image_index.json")
        with open(idx_path, 'w', encoding='utf-8') as f: json.dump(self.index_data, f, indent=4)

    # --- PROCESSUS INDEXATION ---
    def start_indexing_thread(self):
        if not self.target_dir: return
        threading.Thread(target=self.run_indexing, daemon=True).start()

    def run_indexing(self):
        files = self.get_image_files()
        self.pre_generate_all_thumbs(files)
        
        for i, p in enumerate(files):
            f_name = os.path.basename(p)
            if f_name not in self.index_data:
                self.lbl_status.configure(text=f"AI Analysis: {f_name}")
                thumb = self.get_ai_thumb(p)
                try:
                    res = ollama.generate(model=self.model_var.get(), prompt="Describe image in 10 words", images=[thumb])
                    self.index_data[f_name] = res['response'].lower()
                except: continue
            self.progress.set((i+1)/len(files))
        self.save_index()
        self.lbl_status.configure(text="Indexing complete", text_color="green")

    # --- PROCESSUS TRI ---
    def start_sorting_thread(self):
        if not self.target_dir: return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.run_sorting, daemon=True).start()

    def run_sorting(self):
        final_dest = self.dest_dir if self.dest_dir else self.target_dir
        for cat in self.categories + ['unknown']: os.makedirs(os.path.join(final_dest, cat), exist_ok=True)
        
        files = self.get_image_files()
        self.pre_generate_all_thumbs(files)

        for i, p in enumerate(files):
            f_name = os.path.basename(p)
            self.lbl_status.configure(text=f"Sorting: {f_name}")
            thumb = self.get_ai_thumb(p)
            
            try:
                # Classification
                res = ollama.generate(model=self.model_var.get(), prompt=f"Pick ONE category: {self.categories}", images=[thumb])
                cat = 'unknown'
                for c in self.categories:
                    if c in res['response'].lower(): cat = c; break
                
                # Renommage intelligent
                new_f = f_name
                if self.rename_var.get():
                    r_res = ollama.generate(model=self.model_var.get(), prompt="5 words description no punctuation", images=[thumb])
                    clean = re.sub(r'[^a-z0-9_]', '', r_res['response'].lower().replace(" ","_"))[:50]
                    new_f = f"{clean}{os.path.splitext(f_name)[1]}"

                shutil.move(p, os.path.join(final_dest, cat, new_f))
            except: pass
            self.progress.set((i+1)/len(files))
        
        self.btn_start.configure(state="normal")
        self.lbl_status.configure(text="Sorting complete")

    def run_search(self):
        q = self.entry_query.get().lower()
        for w in self.search_scroll.winfo_children(): w.destroy()
        self.found_images = []
        r, c = 0, 0
        for f_name, desc in self.index_data.items():
            if q in desc or q in f_name.lower():
                files = self.get_image_files()
                path = next((p for p in files if os.path.basename(p) == f_name), None)
                if path:
                    self.display_thumb(path, r, c)
                    c += 1
                    if c > 3: c = 0; r += 1

    def display_thumb(self, path, r, c):
        try:
            f = ctk.CTkFrame(self.search_scroll)
            f.grid(row=r, column=c, padx=5, pady=5)
            img = Image.open(path); img.thumbnail((120, 120))
            tk_img = ImageTk.PhotoImage(img)
            l = ctk.CTkLabel(f, image=tk_img, text=""); l.image = tk_img; l.pack()
            v = ctk.BooleanVar()
            ctk.CTkCheckBox(f, text=os.path.basename(path)[:12], variable=v).pack()
            self.found_images.append((path, v))
        except: pass

    def browse_source(self):
        p = filedialog.askdirectory()
        if p: self.target_dir = p; self.lbl_status_source.configure(text=p); self.load_index()

    def browse_dest(self):
        p = filedialog.askdirectory()
        if p: self.dest_dir = p; self.lbl_status_dest.configure(text=p)

if __name__ == "__main__":
    app = ImageSorterApp()
    app.mainloop()
