import os
import shutil
import threading
import json
import subprocess
import sys
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

        self.title("AI Image Classifier - Turbo Edition (GPU Optimized)")
        self.geometry("1100x950")

        self.target_dir = ""
        self.dest_dir = ""
        self.index_data = {}
        # Pour 8Go de VRAM, 3 workers est un excellent compromis
        self.max_workers = 3 
        self._thumb_refs = []

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.index_path = os.path.join(self.script_dir, "global_image_index.json")
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
        self.load_index()
        self.refresh_models_thread()

    def setup_ui(self):
        # --- SÉLECTEUR DE MODÈLE ---
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=15, padx=20, fill="x")
        self.model_var = ctk.StringVar(value="Chargement...")
        self.combo_models = ctk.CTkComboBox(self.model_frame, variable=self.model_var, width=250, state="disabled")
        self.combo_models.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(self.model_frame, text="🔄", width=40, command=self.refresh_models_thread).pack(side="left", padx=10)

        # --- DOSSIERS ---
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

        # --- ONGLETS ---
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        self.tab_sort = self.tabs.add("Tri Automatique")
        self.tab_search = self.tabs.add("Recherche")

        self.setup_sort_tab()
        self.setup_search_tab()

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.set(0)
        self.progress.pack(pady=10)

        self.lbl_status = ctk.CTkLabel(self, text="Prêt", font=("Arial", 11))
        self.lbl_status.pack()

    # ─────────────────────────────────────────────────────────
    # LOGIQUE OPTIMISÉE
    # ─────────────────────────────────────────────────────────

    def get_ai_thumb(self, original_path):
        """Miniature 224x224 : Standard pour les modèles de Vision (accélère le traitement)."""
        try:
            file_stats = os.stat(original_path)
            file_id = re.sub(r'[^a-zA-Z0-9]', '_', f"{os.path.basename(original_path)}_{file_stats.st_size}")
            thumb_path = os.path.join(self.global_cache_dir, f"thumb_{file_id}.jpg")
            if not os.path.exists(thumb_path):
                with Image.open(original_path) as img:
                    img.thumbnail((224, 224), Image.Resampling.LANCZOS)
                    img.convert("RGB").save(thumb_path, "JPEG", quality=70)
            return thumb_path
        except Exception as e:
            return original_path

    def _ollama_generate(self, prompt, thumb_path):
        with open(thumb_path, 'rb') as fh:
            img_bytes = fh.read()
        res = ollama.generate(model=self.model_var.get(), prompt=prompt, images=[img_bytes])
        return res.get('response', '') if isinstance(res, dict) else getattr(res, 'response', str(res))

    def process_single_image(self, orig_path, final_dest):
        """Analyse et déplace une image. Utilisé par le ThreadPoolExecutor."""
        fname = os.path.basename(orig_path)
        try:
            orig_size = os.stat(orig_path).st_size
            file_id = re.sub(r'[^a-zA-Z0-9]', '_', f"{fname}_{orig_size}")
            thumb = self.get_ai_thumb(orig_path)
            
            # Requête Combo (Catégorie + Description) pour gagner 50% de temps
            if self.rename_var.get():
                prompt = (f"Return ONLY a JSON object with: 'cat' (choose ONE from {self.categories}) "
                          f"and 'name' (5 words description for a filename, lowercase, no spaces).")
            else:
                prompt = f"Pick ONE category from {self.categories}. Reply with ONLY the category name."

            response = self._ollama_generate(prompt, thumb)
            
            cat = 'unknown'
            new_f = fname

            # Parsing de la réponse
            if "{" in response:
                try:
                    data = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group())
                    cat_raw = data.get('cat', '').lower()
                    for c in self.categories:
                        if c in cat_raw: cat = c; break
                    
                    if self.rename_var.get():
                        clean_name = re.sub(r'[^a-z0-9_]', '', data.get('name', '').lower().replace(" ", "_"))
                        if clean_name: new_f = f"{clean_name}{os.path.splitext(fname)[1]}"
                except:
                    pass
            else:
                for c in self.categories:
                    if c in response.lower(): cat = c; break

            # Gestion collision et déplacement
            dest_dir_cat = os.path.join(final_dest, cat)
            dest_path = os.path.join(dest_dir_cat, new_f)
            
            counter = 1
            base_n, ext_n = os.path.splitext(new_f)
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir_cat, f"{base_n}_{counter}{ext_n}")
                counter += 1

            shutil.move(orig_path, dest_path)
            
            return file_id, {
                "original_name": fname,
                "current_path": dest_path,
                "category": cat,
                "ai_description": response.strip(),
                "thumb_path": thumb,
            }
        except Exception as e:
            print(f"Error {fname}: {e}")
            return None, None

    def run_sorting(self):
        files = self.get_image_files()
        if not files:
            self.after(0, lambda: (self.lbl_status.configure(text="Aucun fichier"), self.btn_start.configure(state="normal")))
            return

        self.after(0, lambda: self.lbl_status.configure(text="Initialisation du cache..."))
        # Pré-génération rapide des miniatures
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as ex:
            list(ex.map(self.get_ai_thumb, files))

        final_dest = self.dest_dir if self.dest_dir else self.target_dir
        for cat in self.categories + ['unknown']:
            os.makedirs(os.path.join(final_dest, cat), exist_ok=True)

        total = len(files)
        # 3 workers = optimal pour GPU 8Go. Augmenter à 4 ou 5 si vous avez 12Go+ de VRAM.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.process_single_image, p, final_dest) for p in files]
            
            for i, future in enumerate(futures):
                f_id, data = future.result()
                if f_id: self.index_data[f_id] = data
                
                prog = (i + 1) / total
                self.after(0, lambda v=prog, n=i+1: (
                    self.progress.set(v),
                    self.lbl_status.configure(text=f"Analyse IA Parallèle : {n} / {total}")
                ))
                if (i+1) % 10 == 0: self.save_index()

        self.save_index()
        self.after(0, lambda: (self.btn_start.configure(state="normal"), 
                               self.lbl_status.configure(text="Tri terminé ✔", text_color="#2ecc71")))

    # ─────────────────────────────────────────────────────────
    # INTERFACE & UTILITAIRES (Inchangés mais intégrés)
    # ─────────────────────────────────────────────────────────

    def setup_sort_tab(self):
        self.rename_var = ctk.CTkCheckBox(self.tab_sort, text="Renommage intelligent (IA unique)")
        self.rename_var.pack(pady=5)
        f = ctk.CTkFrame(self.tab_sort, fg_color="transparent")
        f.pack(fill="x", padx=20)
        self.entry_cat = ctk.CTkEntry(f, placeholder_text="Ajouter une catégorie...")
        self.entry_cat.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f, text="+", width=40, command=self.add_category).pack(side="right")
        self.cat_scroll = ctk.CTkScrollableFrame(self.tab_sort, height=250)
        self.cat_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        for col in range(5): self.cat_scroll.columnconfigure(col, weight=1)
        self.update_category_chips()
        self.btn_start = ctk.CTkButton(self.tab_sort, text="Démarrer le Tri IA (Multi-GPU)", fg_color="#2ecc71", command=self.start_sorting_thread)
        self.btn_start.pack(pady=10)

    def start_sorting_thread(self):
        if not self.target_dir:
            messagebox.showwarning("Erreur", "Choisir source.")
            return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.run_sorting, daemon=True).start()

    def update_category_chips(self):
        for w in self.cat_scroll.winfo_children(): w.destroy()
        r, c = 0, 0
        for cat in self.categories:
            chip = ctk.CTkFrame(self.cat_scroll, fg_color="#34495e", corner_radius=10)
            chip.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            ctk.CTkLabel(chip, text=cat, font=("Arial", 11)).pack(side="left", padx=5)
            ctk.CTkButton(chip, text="×", width=15, height=15, fg_color="transparent", command=lambda n=cat: self.remove_category(n)).pack(side="right")
            c += 1
            if c > 4: c = 0; r += 1

    def add_category(self):
        cat = self.entry_cat.get().strip().lower()
        if cat and cat not in self.categories:
            self.categories.append(cat); self.update_category_chips(); self.entry_cat.delete(0, 'end')

    def remove_category(self, name):
        if name in self.categories: self.categories.remove(name); self.update_category_chips()

    def browse_source(self):
        p = filedialog.askdirectory()
        if p: self.target_dir = p; self.lbl_status_source.configure(text=p)

    def browse_dest(self):
        p = filedialog.askdirectory()
        if p: self.dest_dir = p; self.lbl_status_dest.configure(text=p)

    def setup_search_tab(self):
        top_frame = ctk.CTkFrame(self.tab_search, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=10)
        self.search_entry = ctk.CTkEntry(top_frame, placeholder_text="Rechercher...", font=("Arial", 13))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(top_frame, text="🔍", command=self.run_search, width=60).pack(side="right")
        self.lbl_search_count = ctk.CTkLabel(self.tab_search, text="")
        self.lbl_search_count.pack()
        self.search_scroll = ctk.CTkScrollableFrame(self.tab_search)
        self.search_scroll.pack(fill="both", expand=True, padx=10, pady=5)
        for col in range(5): self.search_scroll.columnconfigure(col, weight=1)

    def run_search(self):
        query = self.search_entry.get().strip().lower()
        for w in self.search_scroll.winfo_children(): w.destroy()
        self._thumb_refs.clear()
        results = [d for d in self.index_data.values() if query in str(d).lower()]
        self.lbl_search_count.configure(text=f"{len(results)} résultat(s)")
        COLS = 5
        for idx, data in enumerate(results):
            card = ctk.CTkFrame(self.search_scroll, fg_color="#2c3e50")
            card.grid(row=idx//COLS, column=idx%COLS, padx=5, pady=5, sticky="nsew")
            try:
                img = Image.open(data.get("thumb_path")).resize((100, 100))
                ph = ImageTk.PhotoImage(img); self._thumb_refs.append(ph)
                ctk.CTkLabel(card, image=ph, text="").pack()
            except: pass
            ctk.CTkLabel(card, text=data.get("category"), font=("Arial", 9, "bold")).pack()
            ctk.CTkButton(card, text="📂", width=30, command=lambda p=data.get("current_path"): self.reveal_file(p)).pack()

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

    def load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f: self.index_data = json.load(f)
            except: self.index_data = {}

    def save_index(self):
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f: json.dump(self.index_data, f, indent=4, ensure_ascii=False)
        except: pass

    def refresh_models_thread(self):
        threading.Thread(target=self._fetch_models, daemon=True).start()

    def _fetch_models(self):
        try:
            m = ollama.list()
            names = [getattr(model, 'model', None) or getattr(model, 'name', None) for model in m.models] if hasattr(m, 'models') else [x.get('name') for x in m.get('models', [])]
            self.after(0, lambda: self.combo_models.configure(values=names, state="normal"))
            if names: self.after(0, lambda: self.model_var.set(names[0]))
        except:
            self.after(0, lambda: self.model_var.set("Ollama non détecté"))

    def clear_cache(self):
        if messagebox.askyesno("Cache", "Vider les miniatures ?"):
            shutil.rmtree(self.global_cache_dir, ignore_errors=True)
            os.makedirs(self.global_cache_dir, exist_ok=True)

if __name__ == "__main__":
    app = ImageSorterApp()
    app.mainloop()

