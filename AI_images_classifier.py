import os
import shutil
import threading
import json
import subprocess
import sys
import sqlite3
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import ollama
import re
from concurrent.futures import ThreadPoolExecutor

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- GESTIONNAIRE DE BASE DE DONNÉES ---
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_table()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS image_index (
                    file_id TEXT PRIMARY KEY,
                    original_name TEXT,
                    current_path TEXT,
                    category TEXT,
                    ai_description TEXT,
                    thumb_path TEXT
                )
            """)
            conn.commit()

    def upsert_image(self, file_id, data):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO image_index 
                (file_id, original_name, current_path, category, ai_description, thumb_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file_id, data['original_name'], data['current_path'], 
                  data['category'], str(data['ai_description']), data['thumb_path']))
            conn.commit()

    def get_all(self):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM image_index")
            return [dict(row) for row in cursor.fetchall()]

    def search(self, terms):
        if not terms:
            return self.get_all()
        
        query = "SELECT * FROM image_index WHERE "
        conditions = []
        params = []
        for term in terms:
            conditions.append("(original_name LIKE ? OR category LIKE ? OR ai_description LIKE ?)")
            t = f"%{term}%"
            params.extend([t, t, t])
        
        query += " AND ".join(conditions)
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_path(self, old_path, new_path):
        with self._get_connection() as conn:
            conn.execute("UPDATE image_index SET current_path = ? WHERE current_path = ?", (new_path, old_path))
            conn.commit()

    def delete_by_path(self, path):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM image_index WHERE current_path = ?", (path,))
            conn.commit()

class ImageSorterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Image Classifier - SQLite Edition")
        self.geometry("1100x950")

        self.target_dir = ""
        self.dest_dir = ""
        self.max_workers = 3 
        self._thumb_refs = []
        self.selected_files = set() 
        self.current_search_vars = {}
        
        self.thumb_size = 150 
        self.current_page = 0
        self.results_per_page = 50
        self.all_search_results = []

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(self.script_dir, "image_index.db")
        self.db = DatabaseManager(self.db_path)
        
        self.global_cache_dir = os.path.join(self.script_dir, "ai_cache_thumbnails")
        os.makedirs(self.global_cache_dir, exist_ok=True)

        self.categories = [
            "realism", "comics", "manga", "painting", "watercolor",
            "sport", "urban city", "retro and vintage", "sketch", "portrait",
            "landscape", "architecture", "interior", "fauna", "flora",
            "space", "vehicles", "cyberpunk", "fantasy", "science fiction",
            "steampunk", "horror", "abstract", "minimalism", "caricatures"
        ]

        self.grid_columnconfigure(0, weight=1)
        self.setup_ui()
        self.refresh_models_thread()

    # --- MÉTHODES UI ---
    def setup_ui(self):
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=15, padx=20, fill="x")
        self.model_var = ctk.StringVar(value="Chargement...")
        self.combo_models = ctk.CTkComboBox(self.model_frame, variable=self.model_var, width=250, state="disabled")
        self.combo_models.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(self.model_frame, text="🔄", width=40, command=self.refresh_models_thread).pack(side="left", padx=10)

        self.dir_frame = ctk.CTkFrame(self)
        self.dir_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkButton(self.dir_frame, text="Dossier Source", command=self.browse_source, width=150).grid(row=0, column=0, padx=10, pady=5)
        self.lbl_status_source = ctk.CTkLabel(self.dir_frame, text="Non sélectionné", font=("Arial", 10, "italic"))
        self.lbl_status_source.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(self.dir_frame, text="Dossier Destination", command=self.browse_dest, width=150).grid(row=1, column=0, padx=10, pady=5)
        self.lbl_status_dest = ctk.CTkLabel(self.dir_frame, text="Par défaut : source", font=("Arial", 10, "italic"))
        self.lbl_status_dest.grid(row=1, column=1, sticky="w")

        self.recursive_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.dir_frame, text="Inclure sous-dossiers", variable=self.recursive_var).grid(row=2, column=0, padx=10, pady=5)
        ctk.CTkButton(self.dir_frame, text="Purger Cache", fg_color="#c0392b", command=self.clear_cache).grid(row=2, column=1, padx=10, pady=5, sticky="e")

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab_sort = self.tabs.add("Tri Automatique")
        self.tab_search = self.tabs.add("Recherche & Gestion")

        self.setup_sort_tab()
        self.setup_search_tab()

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.set(0)
        self.progress.pack(pady=10)
        self.lbl_status = ctk.CTkLabel(self, text="Prêt", font=("Arial", 11))
        self.lbl_status.pack()

    # --- NOUVELLE FONCTION : APERÇU GRAND FORMAT ---
    def show_full_preview(self, data):
        image_path = data.get("current_path")
        preview_win = ctk.CTkToplevel(self)
        preview_win.title(f"Détails : {os.path.basename(image_path)}")
        preview_win.geometry("1000x750")
        preview_win.attributes("-topmost", True)

        main_container = ctk.CTkFrame(preview_win)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Panneau Gauche : Image
        left_panel = ctk.CTkFrame(main_container, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=True, padx=5)

        try:
            with Image.open(image_path) as img:
                orig_w, orig_h = img.size
                ratio = min(1000 / orig_w, 1000 / orig_h, 1.0)
                display_w, display_h = int(orig_w * ratio), int(orig_h * ratio)
                img_resized = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img_resized)
                
                lbl_img = ctk.CTkLabel(left_panel, image=photo, text="")
                lbl_img.image = photo
                lbl_img.pack(expand=True)
                ctk.CTkLabel(left_panel, text=f"Résolution réelle : {orig_w} x {orig_h} px", font=("Arial", 12, "bold")).pack(pady=10)
        except Exception as e:
            ctk.CTkLabel(left_panel, text=f"Erreur d'ouverture : {e}").pack()

        # Panneau Droit : Infos DB & Actions
        right_panel = ctk.CTkFrame(main_container, width=380)
        right_panel.pack(side="right", fill="both", padx=5)
        right_panel.pack_propagate(False)

        ctk.CTkLabel(right_panel, text="Description en Base (IA)", font=("Arial", 14, "bold")).pack(pady=10)
        
        desc_text = ctk.CTkTextbox(right_panel, height=300, wrap="word")
        desc_text.insert("0.0", data.get("ai_description", "Aucune donnée"))
        desc_text.configure(state="disabled")
        desc_text.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(right_panel, text=f"Catégorie : {data.get('category')}", font=("Arial", 12)).pack(anchor="w", padx=10, pady=10)

        # Action de régénération
        btn_reprocess = ctk.CTkButton(
            right_panel, 
            text="Régénérer via l'IA 🔄", 
            fg_color="#e67e22",
            command=lambda: self.reprocess_single_from_preview(data, preview_win)
        )
        btn_reprocess.pack(pady=20, padx=10, side="bottom")

    def reprocess_single_from_preview(self, old_data, window):
        dest_base = self.dest_dir if self.dest_dir else self.target_dir
        self.lbl_status.configure(text="Régénération individuelle...", text_color="#e67e22")
        
        def task():
            f_id, new_data = self.process_single_image(old_data['current_path'], dest_base)
            if f_id:
                self.db.upsert_image(f_id, new_data)
                self.after(0, lambda: (window.destroy(), self.run_search(), messagebox.showinfo("Succès", "Image mise à jour avec succès")))
            else:
                self.after(0, lambda: messagebox.showerror("Erreur", "L'IA n'a pas pu traiter l'image"))

        threading.Thread(target=task, daemon=True).start()

    # --- LOGIQUE DE TRAITEMENT ---
    def get_ai_thumb(self, original_path):
        try:
            file_stats = os.stat(original_path)
            file_id = re.sub(r'[^a-zA-Z0-9]', '_', f"{os.path.basename(original_path)}_{file_stats.st_size}")
            thumb_path = os.path.join(self.global_cache_dir, f"thumb_{file_id}.jpg")
            if not os.path.exists(thumb_path):
                with Image.open(original_path) as img:
                    img.thumbnail((336, 336), Image.Resampling.LANCZOS)
                    img.convert("RGB").save(thumb_path, "JPEG", quality=70)
            return thumb_path
        except: return original_path

    def _ollama_generate(self, prompt, thumb_path):
        with open(thumb_path, 'rb') as fh:
            img_bytes = fh.read()
        res = ollama.generate(model=self.model_var.get(), prompt=prompt, images=[img_bytes])
        return res.get('response', '') if isinstance(res, dict) else getattr(res, 'response', str(res))

    def process_single_image(self, orig_path, final_dest):
        fname = os.path.basename(orig_path)
        try:
            orig_size = os.stat(orig_path).st_size
            file_id = re.sub(r'[^a-zA-Z0-9]', '_', f"{fname}_{orig_size}")
            thumb = self.get_ai_thumb(orig_path)
            
            prompt = (
                f"Analyze this image and return ONLY a JSON object with these fields:\n"
                f"1. 'cat': Pick ONE category from {self.categories}.\n"
                f"2. 'name': A 5-word file name (lowercase, underscores, no spaces).\n"
                f"3. 'desc': A detailed list of the 4 to 5 most important visual elements."
            )

            response = self._ollama_generate(prompt, thumb)
            cat, new_f, detailed_desc = 'unknown', fname, response.strip()

            if "{" in response:
                try:
                    data = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group())
                    cat_raw = data.get('cat', '').lower()
                    for c in self.categories:
                        if c in cat_raw: cat = c; break
                    detailed_desc = str(data.get('desc', response))
                    if self.rename_var.get():
                        clean_name = re.sub(r'[^a-z0-9_]', '', data.get('name', '').lower().replace(" ", "_"))
                        if clean_name: new_f = f"{clean_name}{os.path.splitext(fname)[1]}"
                except: pass

            dest_dir_cat = os.path.join(final_dest, cat)
            os.makedirs(dest_dir_cat, exist_ok=True) # Assure que le dossier de catégorie existe
            dest_path = os.path.join(dest_dir_cat, new_f)
            counter = 1
            base_n, ext_n = os.path.splitext(new_f)
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir_cat, f"{base_n}_{counter}{ext_n}")
                counter += 1

            shutil.move(orig_path, dest_path)
            return file_id, {"original_name": fname, "current_path": dest_path, "category": cat, "ai_description": detailed_desc, "thumb_path": thumb}
        except: return None, None

    def run_sorting(self):
        files = self.get_image_files()
        if not files:
            self.after(0, lambda: (self.lbl_status.configure(text="Aucun fichier"), self.btn_start.configure(state="normal")))
            return
        
        final_dest = self.dest_dir if self.dest_dir else self.target_dir
        for cat in self.categories + ['unknown']: os.makedirs(os.path.join(final_dest, cat), exist_ok=True)

        total = len(files)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.process_single_image, p, final_dest) for p in files]
            for i, future in enumerate(futures):
                f_id, data = future.result()
                if f_id: 
                    self.db.upsert_image(f_id, data)
                
                prog = (i + 1) / total
                self.after(0, lambda v=prog, n=i+1: (self.progress.set(v), self.lbl_status.configure(text=f"Analyse IA : {n} / {total}")))

        self.after(0, lambda: (self.btn_start.configure(state="normal"), self.lbl_status.configure(text="Tri terminé ✔", text_color="#2ecc71")))

    def run_search(self):
        query_text = self.search_entry.get().strip().lower()
        search_terms = query_text.split()
        self.all_search_results = self.db.search(search_terms)
        self.current_page = 0
        self.display_page()

    # --- MODIFICATION DE L'AFFICHAGE DE LA PAGE (IMAGE CLIQUABLE) ---
    def display_page(self):
        for w in self.search_scroll.winfo_children(): w.destroy()
        self._thumb_refs.clear()
        self.current_search_vars = {}
        if not self.all_search_results:
            ctk.CTkLabel(self.search_scroll, text="Aucun résultat").pack(pady=20)
            return
        
        total_items = len(self.all_search_results)
        total_pages = (total_items - 1) // self.results_per_page + 1
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        start = self.current_page * self.results_per_page
        end = start + self.results_per_page
        page_items = self.all_search_results[start:end]

        ctrl_frame = ctk.CTkFrame(self.search_scroll, fg_color="transparent")
        ctrl_frame.pack(fill="x", pady=10)
        ctk.CTkButton(ctrl_frame, text="<", width=40, state="normal" if self.current_page > 0 else "disabled", command=self.prev_page).pack(side="left", padx=5)
        self.page_input = ctk.CTkEntry(ctrl_frame, width=45)
        self.page_input.insert(0, str(self.current_page + 1))
        self.page_input.pack(side="left", padx=2)
        self.page_input.bind("<Return>", lambda e: self.go_to_page())
        ctk.CTkLabel(ctrl_frame, text=f"/ {total_pages} ({total_items} images)").pack(side="left", padx=5)
        ctk.CTkButton(ctrl_frame, text=">", width=40, state="normal" if end < total_items else "disabled", command=self.next_page).pack(side="left", padx=5)

        grid_container = ctk.CTkFrame(self.search_scroll, fg_color="transparent")
        grid_container.pack(fill="both", expand=True)
        cols = max(1, (self.winfo_width() - 80) // (self.thumb_size + 20))
        for col in range(cols): grid_container.columnconfigure(col, weight=1)

        for idx, data in enumerate(page_items):
            path = data.get("current_path")
            if not path or not os.path.exists(path): continue
            card = ctk.CTkFrame(grid_container, fg_color="#2c3e50")
            card.grid(row=idx // cols, column=idx % cols, padx=5, pady=5, sticky="nsew")
            
            var = ctk.BooleanVar(value=path in self.selected_files)
            self.current_search_vars[path] = var
            ctk.CTkCheckBox(card, text="", variable=var, width=20, command=lambda p=path, v=var: self.toggle_selection(p, v)).pack(anchor="ne", padx=5)
            
            try:
                img = Image.open(data.get("thumb_path"))
                img.thumbnail((self.thumb_size, self.thumb_size), Image.Resampling.LANCZOS)
                ph = ImageTk.PhotoImage(img)
                self._thumb_refs.append(ph)
                
                # Image avec bind pour l'aperçu
                lbl_img = ctk.CTkLabel(card, image=ph, text="", cursor="hand2")
                lbl_img.pack(pady=2)
                lbl_img.bind("<Button-1>", lambda e, d=data: self.show_full_preview(d))
            except: 
                ctk.CTkLabel(card, text="Erreur Image").pack()

            if self.thumb_size > 100: ctk.CTkLabel(card, text=data.get("category"), font=("Arial", 9, "bold")).pack()
            ctk.CTkButton(card, text="📂", width=30, command=lambda p=path: self.reveal_file(p)).pack(pady=2)

    # --- ACTIONS DE GROUPE ---
    def bulk_action(self, mode):
        if not self.selected_files: return
        target = filedialog.askdirectory()
        if not target: return
        
        success = 0
        files_to_process = list(self.selected_files)
        
        for path in files_to_process:
            try:
                dest = os.path.join(target, os.path.basename(path))
                if mode == "copy": 
                    shutil.copy2(path, dest)
                else:
                    shutil.move(path, dest)
                    self.db.update_path(path, dest)
                success += 1
            except: pass
            
        self.selected_files.clear()
        messagebox.showinfo("OK", f"{success} fichiers traités.")
        self.lbl_select_count.configure(text="0 sélectionné(s)")
        self.run_search()

    def bulk_delete(self):
        if not self.selected_files: return
        if not messagebox.askyesno("Confirmation", f"Supprimer définitivement {len(self.selected_files)} fichiers ?"): return
        
        success = 0
        for path in list(self.selected_files):
            try:
                if os.path.exists(path):
                    os.remove(path)
                    self.db.delete_by_path(path)
                    success += 1
            except: pass
            
        self.selected_files.clear()
        messagebox.showinfo("OK", f"{success} fichiers supprimés.")
        self.lbl_select_count.configure(text="0 sélectionné(s)")
        self.run_search()

    # --- SETUP TABS & UI HELPERS ---
    def setup_search_tab(self):
        top_frame = ctk.CTkFrame(self.tab_search, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=10)
        self.search_entry = ctk.CTkEntry(top_frame, placeholder_text="Rechercher...", font=("Arial", 13))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.run_search())
        ctk.CTkButton(top_frame, text="🔍", command=self.run_search, width=50).pack(side="left", padx=2)
        self.btn_toggle_all = ctk.CTkButton(top_frame, text="✅ Tout", command=self.select_all_search, width=60, fg_color="#34495e")
        self.btn_toggle_all.pack(side="left", padx=2)

        size_frame = ctk.CTkFrame(self.tab_search, fg_color="transparent")
        size_frame.pack(fill="x", padx=20, pady=0)
        ctk.CTkLabel(size_frame, text="Taille miniatures :", font=("Arial", 11)).pack(side="left", padx=5)
        self.size_slider = ctk.CTkSlider(size_frame, from_=80, to=400, number_of_steps=10, command=self.update_thumb_size)
        self.size_slider.set(self.thumb_size)
        self.size_slider.pack(side="left", padx=5)

        self.action_frame = ctk.CTkFrame(self.tab_search, height=40)
        self.action_frame.pack(fill="x", padx=20, pady=5)
        self.lbl_select_count = ctk.CTkLabel(self.action_frame, text="0 sélectionné(s)")
        self.lbl_select_count.pack(side="left", padx=10)
        ctk.CTkButton(self.action_frame, text="Supprimer", command=self.bulk_delete, fg_color="#c0392b", width=100).pack(side="right", padx=5)
        ctk.CTkButton(self.action_frame, text="Déplacer vers...", command=lambda: self.bulk_action("move"), fg_color="#e67e22", width=120).pack(side="right", padx=5)
        ctk.CTkButton(self.action_frame, text="Copier vers...", command=lambda: self.bulk_action("copy"), fg_color="#3498db", width=120).pack(side="right", padx=5)

        self.search_scroll = ctk.CTkScrollableFrame(self.tab_search)
        self.search_scroll.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_sort_tab(self):
        self.rename_var = ctk.CTkCheckBox(self.tab_sort, text="Renommage intelligent (IA unique)")
        self.rename_var.pack(pady=5)
        f = ctk.CTkFrame(self.tab_sort, fg_color="transparent")
        f.pack(fill="x", padx=20)
        self.entry_cat = ctk.CTkEntry(f, placeholder_text="Ajouter catégorie...")
        self.entry_cat.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f, text="+", width=40, command=self.add_category).pack(side="right")
        self.cat_scroll = ctk.CTkScrollableFrame(self.tab_sort, height=250)
        self.cat_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        for col in range(5): self.cat_scroll.columnconfigure(col, weight=1)
        self.update_category_chips()
        self.btn_start = ctk.CTkButton(self.tab_sort, text="Démarrer le Tri IA (Turbo GPU)", fg_color="#2ecc71", command=self.start_sorting_thread)
        self.btn_start.pack(pady=10)

    def next_page(self): self.current_page += 1; self.display_page()
    def prev_page(self): self.current_page -= 1; self.display_page()
    def go_to_page(self):
        try:
            val = int(self.page_input.get()) - 1
            if 0 <= val < (len(self.all_search_results)-1)//self.results_per_page + 1:
                self.current_page = val
                self.display_page()
        except: pass

    def update_thumb_size(self, value):
        self.thumb_size = int(value)
        if self.all_search_results: self.display_page()

    def toggle_selection(self, path, var):
        if var.get(): self.selected_files.add(path)
        else: self.selected_files.discard(path)
        self.lbl_select_count.configure(text=f"{len(self.selected_files)} sélectionné(s)")

    def select_all_search(self):
        any_unselected = any(not var.get() for var in self.current_search_vars.values())
        for path, var in self.current_search_vars.items():
            var.set(any_unselected)
            if any_unselected: self.selected_files.add(path)
            else: self.selected_files.discard(path)
        self.lbl_select_count.configure(text=f"{len(self.selected_files)} sélectionné(s)")

    def start_sorting_thread(self):
        if not self.target_dir: return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.run_sorting, daemon=True).start()

    def update_category_chips(self):
        for w in self.cat_scroll.winfo_children(): w.destroy()
        r, c = 0, 0
        for cat in self.categories:
            chip = ctk.CTkFrame(self.cat_scroll, fg_color="#34495e", corner_radius=10)
            chip.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            ctk.CTkLabel(chip, text=cat, font=("Arial", 11)).pack(side="left", padx=5)
            ctk.CTkButton(chip, text="×", width=15, height=15, fg_color="transparent", command=lambda n=cat: (self.categories.remove(n), self.update_category_chips())).pack(side="right")
            c += 1
            if c > 4: c = 0; r += 1

    def add_category(self):
        cat = self.entry_cat.get().strip().lower()
        if cat and cat not in self.categories: self.categories.append(cat); self.update_category_chips(); self.entry_cat.delete(0, 'end')

    def browse_source(self):
        p = filedialog.askdirectory()
        if p: self.target_dir = p; self.lbl_status_source.configure(text=p)

    def browse_dest(self):
        p = filedialog.askdirectory()
        if p: self.dest_dir = p; self.lbl_status_dest.configure(text=p)

    def reveal_file(self, path):
        if sys.platform == "win32": subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else: subprocess.Popen(["open", "-R", path] if sys.platform == "darwin" else ["xdg-open", os.path.dirname(path)])

    def get_image_files(self):
        exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')
        file_list = []
        if not self.target_dir: return []
        for root, _, files in os.walk(self.target_dir):
            if "ai_cache_thumbnails" in root: continue
            for f in files:
                if f.lower().endswith(exts): file_list.append(os.path.join(root, f))
            if not self.recursive_var.get(): break
        return file_list

    def refresh_models_thread(self): threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        try:
            m = ollama.list()
            names = [getattr(model, 'model', None) or getattr(model, 'name', None) for model in m.models] if hasattr(m, 'models') else [x.get('name') for x in m.get('models', [])]
            self.after(0, lambda: self.combo_models.configure(values=names, state="normal"))
            if names: self.after(0, lambda: self.model_var.set(names[0]))
        except: self.after(0, lambda: self.model_var.set("Ollama non détecté"))

    def clear_cache(self):
        if messagebox.askyesno("Cache", "Vider les miniatures ?"):
            shutil.rmtree(self.global_cache_dir, ignore_errors=True)
            os.makedirs(self.global_cache_dir, exist_ok=True)

if __name__ == "__main__":
    app = ImageSorterApp()
    app.mainloop()



